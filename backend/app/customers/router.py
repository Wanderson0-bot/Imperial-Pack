import re
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import mean
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import Customer, CustomerAddress, Order, OrderItem, Product, ProductCategory, User
from app.database.session import get_db
from app.customers.schemas import CustomerCreate, CustomerRecord, CustomerUpdate
from app.orders.states import REALIZED_ORDER_STATUSES
from app.database.idempotency import lock_idempotency_key

router = APIRouter(prefix='/customers', tags=['customers'])


def phone_key(value: str | None) -> str | None:
    digits = re.sub(r'\D', '', value or '')
    return digits or None


def ensure_unique(db: Session, email: str | None, phone: str | None, origin: str, external_id: str | None, exclude_id: str | None = None) -> None:
    if email and db.scalar(select(Customer.id).where(Customer.email == email.lower(), Customer.id != (exclude_id or ''))):
        raise HTTPException(status_code=409, detail='Customer email is already registered.')
    if external_id and db.scalar(select(Customer.id).where(Customer.origin == origin, Customer.external_id == external_id, Customer.id != (exclude_id or ''))):
        raise HTTPException(status_code=409, detail='External customer ID is already registered for this origin.')
    normalized = phone_key(phone)
    if normalized:
        for existing in db.scalars(select(Customer).where(Customer.id != (exclude_id or ''))):
            if phone_key(existing.phone) == normalized:
                raise HTTPException(status_code=409, detail='Customer phone is already registered.')


def commit_customer(db: Session, payload: CustomerCreate, customer: Customer) -> Customer:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if payload.external_id:
            existing = db.scalar(select(Customer).where(Customer.origin == payload.origin, Customer.external_id == payload.external_id))
            if existing:
                if payload.email and existing.email and str(payload.email).lower() != existing.email.lower():
                    raise HTTPException(status_code=409, detail='External customer ID is linked to a different email.') from error
                if payload.phone and existing.phone and phone_key(payload.phone) != phone_key(existing.phone):
                    raise HTTPException(status_code=409, detail='External customer ID is linked to a different phone.') from error
                return existing
        raise HTTPException(status_code=409, detail='Customer identity is already registered.') from error
    db.refresh(customer)
    return customer


def customer_record(db: Session, customer: Customer, metrics: tuple[int, Decimal, datetime | None] | None = None) -> dict:
    result = CustomerRecord.model_validate(customer).model_dump()
    address = db.scalar(select(CustomerAddress).where(CustomerAddress.customer_id == customer.id).order_by(CustomerAddress.created_at).limit(1))
    result['address'] = address
    if metrics is not None:
        count, total, last_purchase = metrics
        result.update(orders=count, total_spent=total, average_ticket=total / count if count else 0, last_purchase=last_purchase)
    return result


def customer_history_summary(db: Session, customer_id: str, start: datetime | None = None, end: datetime | None = None, product_id: str | None = None, category_id: str | None = None) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found.')

    statement = select(Order).where(Order.customer_id == customer_id, Order.status.in_(REALIZED_ORDER_STATUSES))
    if start is not None:
        statement = statement.where(Order.ordered_at >= start)
    if end is not None:
        statement = statement.where(Order.ordered_at <= end)
    orders = list(db.scalars(statement.order_by(Order.ordered_at.asc())))

    if not orders:
        return {
            'customer_id': customer_id,
            'status': 'insufficient_data',
            'message': 'Não há histórico suficiente para uma estimativa confiável.',
            'orders': 0,
            'first_purchase': None,
            'last_purchase': None,
            'total_items': Decimal('0'),
            'total_spent': Decimal('0'),
            'average_ticket': Decimal('0'),
            'average_interval_days': None,
            'frequency': None,
            'product_summary': {},
            'category_summary': {},
        }

    order_ids = [order.id for order in orders]
    items = list(db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)).order_by(OrderItem.order_id.asc())))
    if product_id is not None:
        items = [item for item in items if item.product_id == product_id]
    if category_id is not None:
        category_product_ids = [product.id for product in db.scalars(select(Product).where(Product.category_id == category_id))]
        items = [item for item in items if item.product_id in category_product_ids]

    product_summary: dict[str, dict] = {}
    category_summary: dict[str, dict] = {}
    total_items = sum((item.quantity for item in items), Decimal('0'))
    total_spent = sum((order.total for order in orders), Decimal('0'))

    for item in items:
        product = db.get(Product, item.product_id)
        if product is None:
            continue
        entry = product_summary.setdefault(item.product_id, {'product_id': item.product_id, 'product_name': product.name, 'quantity': Decimal('0'), 'value': Decimal('0'), 'orders': set()})
        entry['quantity'] += item.quantity
        entry['value'] += item.subtotal
        entry['orders'].add(item.order_id)

        category_id_value = product.category_id or 'uncategorized'
        category_entry = category_summary.setdefault(category_id_value, {'category_id': category_id_value, 'category_name': (db.get(ProductCategory, category_id_value).name if db.get(ProductCategory, category_id_value) else 'Sem categoria'), 'quantity': Decimal('0'), 'value': Decimal('0'), 'orders': set()})
        category_entry['quantity'] += item.quantity
        category_entry['value'] += item.subtotal
        category_entry['orders'].add(item.order_id)

    product_summary_output = {}
    for product_key, payload in product_summary.items():
        product_summary_output[product_key] = {
            'product_id': payload['product_id'],
            'product_name': payload['product_name'],
            'quantity': payload['quantity'],
            'value': payload['value'],
            'orders_count': len(payload['orders']),
            'last_purchase': max((order.ordered_at for order in orders if order.id in payload['orders']), default=None),
        }

    category_summary_output = {}
    for category_key, payload in category_summary.items():
        category_summary_output[str(category_key)] = {
            'category_id': payload['category_id'],
            'category_name': payload['category_name'],
            'quantity': payload['quantity'],
            'value': payload['value'],
            'orders_count': len(payload['orders']),
        }

    intervals = [(current.ordered_at.date() - previous.ordered_at.date()).days for previous, current in zip(orders, orders[1:])]
    average_interval = mean(intervals) if intervals else None
    frequency = None if not intervals else {'average_days': average_interval, 'intervals': intervals}

    summary = {
        'customer_id': customer_id,
        'status': 'ready' if len(orders) >= 2 and average_interval is not None else 'insufficient_data',
        'message': 'Histórico suficiente para estimativa confiável.' if len(orders) >= 2 and average_interval is not None else 'Não há histórico suficiente para uma estimativa confiável.',
        'orders': len(orders),
        'first_purchase': orders[0].ordered_at,
        'last_purchase': orders[-1].ordered_at,
        'total_items': total_items,
        'total_spent': total_spent,
        'average_ticket': (total_spent / Decimal(len(orders))) if orders else Decimal('0'),
        'average_interval_days': Decimal(str(average_interval)) if isinstance(average_interval, float) else average_interval,
        'frequency': frequency,
        'product_summary': product_summary_output,
        'category_summary': category_summary_output,
    }
    if len(orders) < 2:
        summary['status'] = 'insufficient_data'
        summary['message'] = 'Não há histórico suficiente para uma estimativa confiável.'
    return summary


def customer_replenishment_estimate(db: Session, customer_id: str, start: datetime | None = None, end: datetime | None = None, product_id: str | None = None, category_id: str | None = None) -> dict:
    history = customer_history_summary(db, customer_id, start=start, end=end, product_id=product_id, category_id=category_id)
    if history['status'] == 'insufficient_data' or history['orders'] < 2:
        return {
            'customer_id': customer_id,
            'status': 'insufficient_data',
            'message': 'Não há histórico suficiente para uma estimativa confiável.',
            'physical_stock_observed': False,
            'product_estimates': {},
            'next_replenishment_window': None,
        }

    filtered_orders = list(db.scalars(select(Order).where(Order.customer_id == customer_id, Order.status.in_(REALIZED_ORDER_STATUSES)).order_by(Order.ordered_at.asc())))
    if start is not None:
        filtered_orders = [order for order in filtered_orders if order.ordered_at >= start]
    if end is not None:
        filtered_orders = [order for order in filtered_orders if order.ordered_at <= end]

    order_items = list(db.scalars(select(OrderItem).where(OrderItem.order_id.in_([order.id for order in filtered_orders])).order_by(OrderItem.order_id.asc())))
    if product_id is not None:
        order_items = [item for item in order_items if item.product_id == product_id]
    if category_id is not None:
        category_product_ids = [product.id for product in db.scalars(select(Product).where(Product.category_id == category_id))]
        order_items = [item for item in order_items if item.product_id in category_product_ids]

    product_estimates = {}
    by_product: dict[str, list[OrderItem]] = {}
    for item in order_items:
        by_product.setdefault(item.product_id, []).append(item)

    for product_key, product_items in by_product.items():
        product_order_ids = {item.order_id for item in product_items}
        product_orders = [order for order in filtered_orders if order.id in product_order_ids]
        product_orders = sorted(product_orders, key=lambda order: order.ordered_at)
        if len(product_orders) < 2:
            continue
        intervals = [(current.ordered_at.date() - previous.ordered_at.date()).days for previous, current in zip(product_orders, product_orders[1:])]
        if not intervals:
            continue
        avg_interval = mean(intervals)
        avg_quantity = sum((item.quantity for item in product_items), Decimal('0')) / Decimal(len(product_items))
        last_order = product_orders[-1]
        next_window_start = last_order.ordered_at + timedelta(days=round(avg_interval))
        product_estimates[product_key] = {
            'product_id': product_key,
            'product_name': db.get(Product, product_key).name if db.get(Product, product_key) else 'Produto',
            'last_purchase': last_order.ordered_at,
            'last_quantity': sum((item.quantity for item in product_items if item.order_id == last_order.id), Decimal('0')),
            'average_interval_days': Decimal(str(avg_interval)) if isinstance(avg_interval, float) else avg_interval,
            'average_quantity_per_purchase': avg_quantity,
            'next_replenishment_window_start': next_window_start,
            'confidence': 'limited' if len(product_orders) < 3 else 'medium',
        }

    return {
        'customer_id': customer_id,
        'status': 'ready' if product_estimates else 'insufficient_data',
        'message': 'Estimativa baseada nos pedidos observados; o estoque físico do cliente não é observado.' if product_estimates else 'Não há histórico suficiente para uma estimativa confiável.',
        'physical_stock_observed': False,
        'product_estimates': product_estimates,
        'next_replenishment_window': max((item['next_replenishment_window_start'] for item in product_estimates.values()), default=None),
    }


@router.get('', response_model=list[CustomerRecord])
def list_customers(search: str | None = Query(default=None, min_length=1, max_length=100), _: User = Depends(require_permission('customers:read')), db: Session = Depends(get_db)):
    statement = select(Customer)
    if search and search.strip():
        term = f'%{search.strip()}%'
        statement = statement.where(Customer.name.ilike(term) | Customer.establishment.ilike(term) | Customer.email.ilike(term) | Customer.phone.ilike(term))
    customers = list(db.scalars(statement.order_by(Customer.name)))
    totals = db.execute(
        select(Order.customer_id, func.count(Order.id), func.coalesce(func.sum(Order.total), 0), func.max(Order.ordered_at))
        .where(Order.status.in_(REALIZED_ORDER_STATUSES))
        .group_by(Order.customer_id)
    ).all()
    summaries = {customer_id: (count, total, last_purchase) for customer_id, count, total, last_purchase in totals}
    records = []
    for customer in customers:
        count, total, last_purchase = summaries.get(customer.id, (0, 0, None))
        records.append(customer_record(db, customer, (count, total, last_purchase)))
    return records


@router.post('', response_model=CustomerRecord, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, actor: User = Depends(require_permission('customers:create')), db: Session = Depends(get_db)):
    if payload.origin not in {'INTERNAL', 'SITE_PUBLICO'}:
        raise HTTPException(status_code=422, detail='Invalid customer origin.')
    if payload.external_id:
        lock_idempotency_key(db, f'customer:{payload.origin}', payload.external_id)
        existing = db.scalar(select(Customer).where(Customer.origin == payload.origin, Customer.external_id == payload.external_id))
        if existing:
            if payload.email and existing.email and str(payload.email).lower() != existing.email.lower():
                raise HTTPException(status_code=409, detail='External customer ID is linked to a different email.')
            if payload.phone and existing.phone and phone_key(payload.phone) != phone_key(existing.phone):
                raise HTTPException(status_code=409, detail='External customer ID is linked to a different phone.')
            return customer_record(db, existing)
    if payload.origin == 'SITE_PUBLICO':
        matches: dict[str, Customer] = {}
        if payload.email:
            match = db.scalar(select(Customer).where(func.lower(Customer.email) == str(payload.email).lower()))
            if match:
                matches[match.id] = match
        normalized_phone = phone_key(payload.phone)
        if normalized_phone:
            for customer in db.scalars(select(Customer).where(Customer.phone.is_not(None))):
                if phone_key(customer.phone) == normalized_phone:
                    matches[customer.id] = customer
        if len(matches) > 1:
            raise HTTPException(status_code=409, detail='Email and phone identify different existing customers.')
        if matches:
            existing = next(iter(matches.values()))
            if payload.email and existing.email and str(payload.email).lower() != existing.email.lower():
                raise HTTPException(status_code=409, detail='Customer identity conflicts with the existing email.')
            if payload.phone and existing.phone and phone_key(payload.phone) != phone_key(existing.phone):
                raise HTTPException(status_code=409, detail='Customer identity conflicts with the existing phone.')
            if payload.external_id:
                existing.external_id = payload.external_id
            for key, value in (('email', str(payload.email).lower() if payload.email else None), ('phone', normalized_phone), ('establishment', payload.establishment), ('city', payload.city), ('notes', payload.notes)):
                if getattr(existing, key) is None and value is not None:
                    setattr(existing, key, value)
            audit(db, actor.id, 'customers.external_link', 'customer', existing.id, {'origin': payload.origin})
            existing = commit_customer(db, payload, existing)
            return customer_record(db, existing)
    ensure_unique(db, str(payload.email).lower() if payload.email else None, payload.phone, payload.origin, payload.external_id)
    values = payload.model_dump(exclude={'address'})
    values.update(email=str(payload.email).lower() if payload.email else None, phone=phone_key(payload.phone), created_by=actor.id)
    customer = Customer(**values)
    db.add(customer)
    db.flush()
    if payload.address:
        db.add(CustomerAddress(customer_id=customer.id, **payload.address.model_dump()))
    audit(db, actor.id, 'customers.create', 'customer', customer.id, {'origin': customer.origin})
    customer = commit_customer(db, payload, customer)
    return customer_record(db, customer)


@router.get('/{customer_id}', response_model=CustomerRecord)
def get_customer(customer_id: str, _: User = Depends(require_permission('customers:read')), db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found.')
    return customer_record(db, customer)


@router.get('/{customer_id}/history')
def get_customer_history(customer_id: str, start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), product_id: str | None = Query(default=None), category_id: str | None = Query(default=None), _: User = Depends(require_permission('customers:read')), db: Session = Depends(get_db)):
    return customer_history_summary(db, customer_id, start=start, end=end, product_id=product_id, category_id=category_id)


@router.get('/{customer_id}/metrics')
def get_customer_metrics(customer_id: str, start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), product_id: str | None = Query(default=None), category_id: str | None = Query(default=None), _: User = Depends(require_permission('customers:read')), db: Session = Depends(get_db)):
    return customer_history_summary(db, customer_id, start=start, end=end, product_id=product_id, category_id=category_id)


@router.get('/{customer_id}/replenishment')
def get_customer_replenishment(customer_id: str, start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), product_id: str | None = Query(default=None), category_id: str | None = Query(default=None), _: User = Depends(require_permission('customers:read')), db: Session = Depends(get_db)):
    return customer_replenishment_estimate(db, customer_id, start=start, end=end, product_id=product_id, category_id=category_id)


@router.patch('/{customer_id}', response_model=CustomerRecord)
def update_customer(customer_id: str, payload: CustomerUpdate, actor: User = Depends(require_permission('customers:update')), db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found.')
    changes = payload.model_dump(exclude_unset=True)
    address_values = changes.pop('address', None)
    email = str(changes.get('email')).lower() if changes.get('email') else changes.get('email', customer.email)
    phone = changes.get('phone', customer.phone)
    external_id = changes.get('external_id', customer.external_id)
    ensure_unique(db, email, phone, customer.origin, external_id, customer.id)
    if 'email' in changes:
        changes['email'] = email
    if 'phone' in changes:
        changes['phone'] = phone_key(phone)
    for key, value in changes.items():
        setattr(customer, key, value)
    if address_values is not None:
        address = db.scalar(select(CustomerAddress).where(CustomerAddress.customer_id == customer.id).order_by(CustomerAddress.created_at).limit(1))
        if address:
            for key, value in address_values.items():
                setattr(address, key, value)
        else:
            db.add(CustomerAddress(customer_id=customer.id, **address_values))
    audit(db, actor.id, 'customers.update', 'customer', customer.id, changes)
    db.commit()
    db.refresh(customer)
    return customer_record(db, customer)
