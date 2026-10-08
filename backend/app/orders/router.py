from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import AccountReceivable, ConsumptionHistory, Customer, InventoryBalance, InventoryMovement, Order, OrderItem, Partner, PartnerProduct, Prediction, PredictionEvaluation, Product, User
from app.database.session import get_db
from app.database.idempotency import lock_idempotency_key
from app.orders.schemas import OrderCreate, OrderRecord, OrderStatusUpdate
from app.inventory.locking import lock_product_balances

router = APIRouter(prefix='/orders', tags=['orders'])
ALLOWED_STATUSES = {'NEW', 'CONFIRMED', 'PREPARING', 'READY', 'DELIVERED', 'CANCELLED'}
VALID_ORDER_TRANSITIONS = {
    'NEW': {'NEW', 'CONFIRMED', 'CANCELLED'},
    'CONFIRMED': {'CONFIRMED', 'PREPARING', 'CANCELLED'},
    'PREPARING': {'PREPARING', 'READY', 'CANCELLED'},
    'READY': {'READY', 'DELIVERED', 'CANCELLED'},
    'DELIVERED': {'DELIVERED', 'CANCELLED'},
    'CANCELLED': {'CANCELLED'},
}


def detailed_order(order: Order, db: Session) -> dict:
    return {**{key: getattr(order, key) for key in ('id', 'customer_id', 'ordered_at', 'status', 'subtotal', 'total', 'notes', 'source', 'external_id')}, 'items': list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))}


def validate_order_transition(current_status: str, next_status: str) -> None:
    if current_status == next_status:
        return
    allowed = VALID_ORDER_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise HTTPException(status_code=422, detail=f'Invalid order status transition from {current_status} to {next_status}.')


def is_fulfilled_website_import(payload: OrderCreate) -> bool:
    """Website imports may arrive fulfilled; the external ID makes retries idempotent."""
    return payload.source == 'SITE_PUBLICO' and bool(payload.external_id) and payload.status == 'DELIVERED'


def revert_order_stock(order: Order, actor_id: str, db: Session) -> None:
    if not order.stock_committed:
        return
    lines = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
    balances = lock_product_balances(db, [line.product_id for line in lines])
    for line in lines:
        balances[line.product_id].quantity += line.quantity
        existing_reversal = db.scalar(
            select(InventoryMovement)
            .where(
                InventoryMovement.order_id == order.id,
                InventoryMovement.product_id == line.product_id,
                InventoryMovement.reason == 'ORDER_CANCELLATION',
            )
            .limit(1)
        )
        if existing_reversal is None:
            db.add(InventoryMovement(product_id=line.product_id, movement_type='IN', quantity=line.quantity, reason='ORDER_CANCELLATION', order_id=order.id, created_by=actor_id))
    for consumption in db.scalars(select(ConsumptionHistory).where(ConsumptionHistory.order_id == order.id)):
        if not consumption.voided:
            consumption.voided = True
    order.stock_committed = False


@router.get('', response_model=list[OrderRecord])
def list_orders(_: User = Depends(require_permission('orders:read')), db: Session = Depends(get_db)):
    orders = list(db.scalars(select(Order).order_by(Order.ordered_at.desc())))
    return [detailed_order(order, db) for order in orders]


@router.get('/{order_id}', response_model=OrderRecord)
def get_order(order_id: str, _: User = Depends(require_permission('orders:read')), db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail='Order not found.')
    return detailed_order(order, db)


@router.post('', response_model=OrderRecord, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, actor: User = Depends(require_permission('orders:create')), db: Session = Depends(get_db)):
    if payload.external_id:
        lock_idempotency_key(db, f'order:{payload.source}', payload.external_id)
        existing = db.scalar(select(Order).where(Order.source == payload.source, Order.external_id == payload.external_id))
        if existing:
            if existing.customer_id != payload.customer_id:
                raise HTTPException(status_code=409, detail='External order ID is already linked to a different customer.')
            return detailed_order(existing, db)
    customer = db.get(Customer, payload.customer_id)
    if not customer or customer.status != 'ACTIVE':
        raise HTTPException(status_code=422, detail='Active customer not found.')
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail='Invalid order status.')
    if payload.status not in {'NEW', 'CONFIRMED'} and not is_fulfilled_website_import(payload):
        raise HTTPException(status_code=422, detail='Invalid order status transition from NEW to {status}.'.format(status=payload.status))
    product_items: list[tuple[Product, object]] = []
    for item in payload.items:
        product = db.get(Product, item.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=422, detail=f'Active product {item.product_id} not found.')
        product_items.append((product, item))
    subtotal = sum((product.current_price * item.quantity for product, item in product_items), Decimal('0'))
    order = Order(customer_id=customer.id, ordered_at=payload.ordered_at, status=payload.status, subtotal=subtotal, total=subtotal, notes=payload.notes, responsible_id=actor.id, source=payload.source, external_id=payload.external_id)
    db.add(order)
    db.flush()
    for product, item in product_items:
        line_subtotal = product.current_price * item.quantity
        db.add(OrderItem(order_id=order.id, product_id=product.id, product_name_snapshot=product.name, unit_price_snapshot=product.current_price, quantity=item.quantity, subtotal=line_subtotal))
    if payload.status in {'CONFIRMED', 'PREPARING', 'READY', 'DELIVERED'}:
        commit_stock(order, product_items, actor.id, db)
        record_partner_consumption(order, product_items, actor.id, db)
    db.add(AccountReceivable(
        customer_id=customer.id,
        description=f'Pedido {order.id}',
        amount=order.total,
        due_at=order.ordered_at,
        status='PENDING',
        reference_id=order.id,
        notes=order.notes,
        created_by=actor.id,
    ))
    audit(db, actor.id, 'orders.create', 'order', order.id, {'to': order.status, 'customer_id': customer.id, 'total': str(subtotal), 'source': order.source, 'external_id': order.external_id})
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if payload.external_id:
            existing = db.scalar(select(Order).where(Order.source == payload.source, Order.external_id == payload.external_id))
            if existing:
                if existing.customer_id != payload.customer_id:
                    raise HTTPException(status_code=409, detail='External order ID is already linked to a different customer.') from error
                return detailed_order(existing, db)
        raise
    db.refresh(order)
    return detailed_order(order, db)


def commit_stock(order: Order, items: list[tuple[Product, object]], actor_id: str, db: Session) -> None:
    try:
        balances = lock_product_balances(db, [product.id for product, _ in items])
    except ValueError as error:
        raise HTTPException(status_code=409, detail='An order product no longer exists.') from error
    for product, item in items:
        if balances[product.id].quantity < item.quantity:
            raise HTTPException(status_code=409, detail=f'Insufficient stock for product {product.name}.')
    for product, item in items:
        balance = balances[product.id]
        balance.quantity -= item.quantity
        db.add(InventoryMovement(product_id=product.id, movement_type='OUT', quantity=item.quantity, reason='ORDER_CONFIRMATION', order_id=order.id, created_by=actor_id, occurred_at=order.ordered_at))
    order.stock_committed = True


def record_partner_consumption(order: Order, items: list[tuple[Product, object]], actor_id: str, db: Session) -> None:
    partner = db.scalar(select(Partner).where(Partner.customer_id == order.customer_id, Partner.status == 'ACTIVE'))
    if not partner:
        return
    quantities: dict[str, Decimal] = {}
    products: dict[str, Product] = {}
    for product, item in items:
        products[product.id] = product
        quantities[product.id] = quantities.get(product.id, Decimal('0')) + Decimal(item.quantity)
    for product_id, quantity in quantities.items():
        product = products[product_id]
        previous = db.scalar(select(ConsumptionHistory).where(ConsumptionHistory.partner_id == partner.id, ConsumptionHistory.product_id == product.id, ConsumptionHistory.voided.is_(False)).order_by(ConsumptionHistory.purchased_at.desc()).limit(1))
        interval = max(0, (order.ordered_at.date() - previous.purchased_at.date()).days) if previous else None
        db.add(ConsumptionHistory(partner_id=partner.id, customer_id=order.customer_id, product_id=product.id, order_id=order.id, quantity=quantity, purchased_at=order.ordered_at, unit_price=product.current_price, unit_cost=product.current_cost, source=order.source, interval_since_previous_days=interval))
        prior = list(db.scalars(select(Prediction).where(
            Prediction.partner_id == partner.id, Prediction.product_id == product.id,
        ).order_by(Prediction.generated_at.desc())))
        evaluated_ids = set(db.scalars(select(PredictionEvaluation.prediction_id).where(
            PredictionEvaluation.prediction_id.in_([prediction.id for prediction in prior])
        ))) if prior else set()
        actual_at = order.ordered_at.replace(tzinfo=timezone.utc) if order.ordered_at.tzinfo is None else order.ordered_at
        forecast = next((prediction for prediction in prior if prediction.id not in evaluated_ids and
            (prediction.generated_at.replace(tzinfo=timezone.utc) if prediction.generated_at.tzinfo is None else prediction.generated_at) < actual_at), None)
        if forecast:
            actual_quantity = quantity
            predicted_quantity = forecast.payload.get('recommended_quantity')
            absolute_error = abs(actual_quantity - Decimal(str(predicted_quantity))) if predicted_quantity is not None else None
            db.add(PredictionEvaluation(prediction_id=forecast.id, actual_value=actual_quantity,
                actual_at=order.ordered_at, absolute_error=absolute_error))
        tracking = db.get(PartnerProduct, {'partner_id': partner.id, 'product_id': product.id})
        if tracking:
            tracking.last_seen_at = order.ordered_at
        else:
            db.add(PartnerProduct(partner_id=partner.id, product_id=product.id, first_seen_at=order.ordered_at, last_seen_at=order.ordered_at))


@router.patch('/{order_id}/status', response_model=OrderRecord)
def update_order_status(order_id: str, payload: OrderStatusUpdate, actor: User = Depends(require_permission('orders:update_status')), db: Session = Depends(get_db)):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail='Invalid order status.')
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise HTTPException(status_code=404, detail='Order not found.')
    previous = order.status
    if previous == payload.status:
        db.refresh(order)
        return detailed_order(order, db)
    validate_order_transition(previous, payload.status)
    if payload.status in {'CONFIRMED', 'PREPARING', 'READY', 'DELIVERED'} and not order.stock_committed:
        lines = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
        pairs = [(db.get(Product, line.product_id), line) for line in lines]
        if any(product is None for product, _ in pairs):
            raise HTTPException(status_code=409, detail='An order product no longer exists.')
        commit_stock(order, pairs, actor.id, db)
        record_partner_consumption(order, pairs, actor.id, db)
    account = None
    if payload.status == 'CANCELLED':
        account = db.scalar(select(AccountReceivable).where(AccountReceivable.reference_id == order.id).with_for_update())
        if account and account.status == 'RECEIVED' and not account.refunded_at:
            raise HTTPException(status_code=409, detail='Refund the received amount before cancelling this order.')
    order.status = payload.status
    if payload.status == 'CANCELLED':
        revert_order_stock(order, actor.id, db)
        if account and account.status != 'CANCELLED':
            previous_account_status = account.status
            account.status = 'CANCELLED'
            account.notes = (account.notes or '') + ' | Pedido cancelado.'
            audit(db, actor.id, 'finance.receivable.update', 'account_receivable', account.id, {'from': previous_account_status, 'to': 'CANCELLED', 'order_id': order.id})
    audit(db, actor.id, 'orders.status_change', 'order', order.id, {'from': previous, 'to': payload.status})
    db.commit()
    db.refresh(order)
    return detailed_order(order, db)
