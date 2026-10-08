from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import AccountPayable, CostHistory, InventoryMovement, Product, Purchase, PurchaseItem, Supplier, SupplierProduct, User
from app.database.session import get_db
from app.purchases.schemas import PurchaseCreate, PurchaseRecord
from app.pricing.calculations import margin, markup
from app.database.idempotency import lock_idempotency_key
from app.inventory.locking import lock_product_balances

router = APIRouter(prefix='/purchases', tags=['purchases'])


def serialize(purchase: Purchase, db: Session) -> dict:
    return {key: getattr(purchase, key) for key in ('id', 'supplier_id', 'purchased_at', 'document_number', 'observations', 'products_value', 'discount_total', 'freight', 'other_costs', 'total', 'status')} | {'items': list(db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id)))}


@router.get('', response_model=list[PurchaseRecord])
def list_purchases(_: User = Depends(require_permission('purchases:read')), db: Session = Depends(get_db)):
    return [serialize(purchase, db) for purchase in db.scalars(select(Purchase).order_by(Purchase.purchased_at.desc()))]


@router.post('', response_model=PurchaseRecord, status_code=status.HTTP_201_CREATED)
def create_purchase(payload: PurchaseCreate, actor: User = Depends(require_permission('purchases:create')), db: Session = Depends(get_db)):
    if payload.idempotency_key:
        lock_idempotency_key(db, 'purchase', payload.idempotency_key)
        existing = db.scalar(select(Purchase).where(Purchase.idempotency_key == payload.idempotency_key))
        if existing:
            return serialize(existing, db)
    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=422, detail='Active supplier not found.')
    products: list[tuple[Product, object]] = []
    for item in payload.items:
        product = db.get(Product, item.product_id)
        if not product:
            raise HTTPException(status_code=422, detail=f'Product {item.product_id} not found.')
        products.append((product, item))
    try:
        balances = lock_product_balances(db, [product.id for product, _ in products])
    except ValueError as error:
        raise HTTPException(status_code=422, detail='One or more purchase products no longer exist.') from error
    currency = Decimal('0.01')
    gross_item_values = [(item.quantity * item.unit_cost).quantize(currency, rounding=ROUND_HALF_UP) for item in payload.items]
    net_item_values = [gross - item.discount for gross, item in zip(gross_item_values, payload.items)]
    products_value = sum(gross_item_values, Decimal('0'))
    discount_total = sum((item.discount for item in payload.items), Decimal('0')).quantize(currency, rounding=ROUND_HALF_UP)
    net_products_value = sum(net_item_values, Decimal('0'))
    total = (net_products_value + payload.freight + payload.other_costs).quantize(currency, rounding=ROUND_HALF_UP)
    purchase = Purchase(supplier_id=supplier.id, purchased_at=payload.purchased_at, document_number=payload.document_number, observations=payload.observations, products_value=products_value, discount_total=discount_total, freight=payload.freight, other_costs=payload.other_costs, total=total, created_by=actor.id, idempotency_key=payload.idempotency_key)
    db.add(purchase)
    db.flush()
    total_quantity = sum((item.quantity for item in payload.items), Decimal('0'))
    supplier_product_ids = set(db.scalars(select(SupplierProduct.product_id).where(SupplierProduct.supplier_id == supplier.id)))
    product_cost_totals: dict[str, tuple[Decimal, Decimal]] = {}
    allocation_precision = Decimal('0.0001')
    freight_allocated = Decimal('0')
    other_costs_allocated = Decimal('0')
    for index, (product, item) in enumerate(products):
        item_value = net_item_values[index]
        if net_products_value > 0:
            allocation_ratio = item_value / net_products_value
        else:
            allocation_ratio = item.quantity / total_quantity
        if index == len(products) - 1:
            freight_share = payload.freight.quantize(allocation_precision) - freight_allocated
            other_share = payload.other_costs.quantize(allocation_precision) - other_costs_allocated
        else:
            freight_share = (payload.freight * allocation_ratio).quantize(allocation_precision, rounding=ROUND_HALF_UP)
            other_share = (payload.other_costs * allocation_ratio).quantize(allocation_precision, rounding=ROUND_HALF_UP)
        freight_allocated += freight_share
        other_costs_allocated += other_share
        real_unit_cost = ((item_value + freight_share + other_share) / item.quantity).quantize(allocation_precision, rounding=ROUND_HALF_UP)
        db.add(PurchaseItem(purchase_id=purchase.id, product_id=product.id, quantity=item.quantity, unit_cost=item.unit_cost, discount=item.discount, description=item.description, freight_share=freight_share, other_cost_share=other_share, real_unit_cost=real_unit_cost))
        if product.id not in supplier_product_ids:
            db.add(SupplierProduct(supplier_id=supplier.id, product_id=product.id))
            supplier_product_ids.add(product.id)
        balance = balances[product.id]
        balance.quantity += item.quantity
        db.add(InventoryMovement(product_id=product.id, movement_type='IN', quantity=item.quantity, reason='PURCHASE_RECEIPT', purchase_id=purchase.id, created_by=actor.id, occurred_at=payload.purchased_at))
        quantity_total, cost_total = product_cost_totals.get(product.id, (Decimal('0'), Decimal('0')))
        product_cost_totals[product.id] = (quantity_total + item.quantity, cost_total + real_unit_cost * item.quantity)
    for product_id, (quantity_total, cost_total) in product_cost_totals.items():
        product = db.get(Product, product_id)
        if not product:
            continue
        previous_cost = product.current_cost
        weighted_real_cost = (cost_total / quantity_total).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        product.current_cost = weighted_real_cost
        product.margin_percent = margin(product.current_price, weighted_real_cost)
        product.markup_percent = markup(product.current_price, weighted_real_cost)
        db.add(CostHistory(product_id=product.id, purchase_id=purchase.id, previous_cost=previous_cost, new_cost=weighted_real_cost, changed_by=actor.id))
    db.add(AccountPayable(
        supplier_id=supplier.id,
        description=f'Compra {purchase.document_number or purchase.id}',
        amount=total,
        due_at=payload.purchased_at,
        status='PENDING',
        reference_id=purchase.id,
        notes=payload.observations,
        created_by=actor.id,
    ))
    audit(db, actor.id, 'purchases.create', 'purchase', purchase.id, {'from': None, 'to': purchase.status, 'supplier_id': supplier.id, 'total': str(total), 'idempotency_key': purchase.idempotency_key})
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if payload.idempotency_key:
            existing = db.scalar(select(Purchase).where(Purchase.idempotency_key == payload.idempotency_key))
            if existing:
                return serialize(existing, db)
        raise HTTPException(status_code=409, detail='Purchase was already registered or conflicts with an existing record.') from error
    db.refresh(purchase)
    return serialize(purchase, db)


@router.post('/{purchase_id}/cancel', response_model=PurchaseRecord)
def cancel_purchase(purchase_id: str, actor: User = Depends(require_permission('purchases:cancel')), db: Session = Depends(get_db)):
    purchase = db.scalar(select(Purchase).where(Purchase.id == purchase_id).with_for_update())
    if not purchase:
        raise HTTPException(status_code=404, detail='Purchase not found.')
    if purchase.status == 'CANCELLED':
        return serialize(purchase, db)
    if purchase.status != 'APPROVED':
        raise HTTPException(status_code=409, detail='Only a received purchase can be cancelled.')

    items = list(db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id).order_by(PurchaseItem.product_id)))
    quantities: dict[str, Decimal] = {}
    for item in items:
        quantities[item.product_id] = quantities.get(item.product_id, Decimal('0')) + item.quantity
    try:
        balances = lock_product_balances(db, list(quantities))
    except ValueError as error:
        raise HTTPException(status_code=409, detail='A purchase product no longer exists.') from error

    payable = db.scalar(select(AccountPayable).where(AccountPayable.reference_id == purchase.id).with_for_update())
    if payable and payable.status == 'PAID' and not payable.refunded_at:
        raise HTTPException(status_code=409, detail='Refund the settled payable before cancelling this purchase.')

    for product_id, quantity in quantities.items():
        if balances[product_id].quantity < quantity:
            raise HTTPException(status_code=409, detail='Purchase stock has already been consumed; cancellation would make inventory inconsistent.')
        later_movement = db.scalar(select(InventoryMovement.id).where(
            InventoryMovement.product_id == product_id,
            InventoryMovement.purchase_id != purchase.id,
            InventoryMovement.occurred_at >= purchase.purchased_at,
        ).limit(1))
        own_cost = db.scalar(select(CostHistory).where(CostHistory.purchase_id == purchase.id, CostHistory.product_id == product_id))
        later_cost = db.scalar(select(CostHistory.id).where(
            CostHistory.product_id == product_id,
            CostHistory.changed_at > own_cost.changed_at,
        ).limit(1)) if own_cost else None
        if later_movement or later_cost:
            raise HTTPException(status_code=409, detail='A later inventory or cost movement exists; this purchase cannot be safely reversed.')

    for product_id, quantity in quantities.items():
        balances[product_id].quantity -= quantity
        db.add(InventoryMovement(product_id=product_id, movement_type='OUT', quantity=quantity, reason='PURCHASE_CANCELLATION', purchase_id=purchase.id, created_by=actor.id, occurred_at=datetime.now(timezone.utc)))
        own_cost = db.scalar(select(CostHistory).where(CostHistory.purchase_id == purchase.id, CostHistory.product_id == product_id))
        product = db.get(Product, product_id)
        if own_cost and product:
            product.current_cost = own_cost.previous_cost
            product.margin_percent = margin(product.current_price, product.current_cost)
            product.markup_percent = markup(product.current_price, product.current_cost)

    if payable and payable.status != 'CANCELLED':
        previous_payable_status = payable.status
        payable.status = 'CANCELLED'
        audit(db, actor.id, 'finance.payable.update', 'account_payable', payable.id, {'from': previous_payable_status, 'to': 'CANCELLED', 'purchase_id': purchase.id})
    previous_status = purchase.status
    purchase.status = 'CANCELLED'
    audit(db, actor.id, 'purchases.cancel', 'purchase', purchase.id, {'from': previous_status, 'to': 'CANCELLED'})
    db.commit()
    db.refresh(purchase)
    return serialize(purchase, db)
