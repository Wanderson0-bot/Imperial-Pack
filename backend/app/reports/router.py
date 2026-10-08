from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.database.models import Customer, InventoryBalance, Order, OrderItem, Partner, Product, Purchase, PurchaseItem, Supplier, User
from app.database.session import get_db
from app.orders.states import REALIZED_ORDER_STATUSES

router = APIRouter(prefix='/reports', tags=['reports'])


@router.get('/overview')
def overview(start: date = Query(), end: date = Query(), _: User = Depends(require_permission('reports:read')), db: Session = Depends(get_db)):
    if end < start:
        raise HTTPException(status_code=422, detail='End date must be on or after start date.')
    business_timezone = ZoneInfo('America/Sao_Paulo')
    start_at = datetime.combine(start, time.min, business_timezone).astimezone(timezone.utc)
    end_at = datetime.combine(end + timedelta(days=1), time.min, business_timezone).astimezone(timezone.utc)
    if db.bind and db.bind.dialect.name == 'sqlite':
        start_at, end_at = start_at.replace(tzinfo=None), end_at.replace(tzinfo=None)
    sales = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.ordered_at >= start_at, Order.ordered_at < end_at, Order.status.in_(REALIZED_ORDER_STATUSES)))
    purchase_total = db.scalar(select(func.coalesce(func.sum(Purchase.total), 0)).where(
        Purchase.purchased_at >= start_at,
        Purchase.purchased_at < end_at,
        Purchase.status != 'CANCELLED',
    ))
    stock_value = db.scalar(select(func.coalesce(func.sum(InventoryBalance.quantity * Product.current_cost), 0)).join(Product, Product.id == InventoryBalance.product_id))
    return {
        'period': {'start': start, 'end': end},
        'sales': sales,
        'purchases': purchase_total,
        'inventory_value_at_current_cost': stock_value,
        'active_customers': db.scalar(select(func.count(Customer.id)).where(Customer.status == 'ACTIVE')) or 0,
        'active_partners': db.scalar(select(func.count(Partner.id)).where(Partner.status == 'ACTIVE')) or 0,
        'active_products': db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0,
        'active_suppliers': db.scalar(select(func.count(Supplier.id)).where(Supplier.is_active.is_(True))) or 0,
    }


@router.get('/orders')
def order_report(start: date = Query(), end: date = Query(), _: User = Depends(require_permission('reports:read')), db: Session = Depends(get_db)):
    business_timezone = ZoneInfo('America/Sao_Paulo')
    start_at = datetime.combine(start, time.min, business_timezone).astimezone(timezone.utc)
    end_at = datetime.combine(end + timedelta(days=1), time.min, business_timezone).astimezone(timezone.utc)
    if db.bind and db.bind.dialect.name == 'sqlite':
        start_at, end_at = start_at.replace(tzinfo=None), end_at.replace(tzinfo=None)
    return list(db.execute(select(Order.status, func.count(Order.id).label('orders'), func.sum(Order.total).label('total')).where(Order.ordered_at >= start_at, Order.ordered_at < end_at).group_by(Order.status)).mappings())
