from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import platform
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.customers.schemas import CustomerCreate
from app.customers.router import create_customer
from app.database.base import Base
from app.database.models import AccountPayable, AccountReceivable, AuditLog, CashMovement, Customer, InventoryBalance, InventoryMovement, Order, Product, Purchase, Role, Supplier, User
from app.orders.router import create_order
from app.orders.schemas import OrderCreate
from app.purchases.router import create_purchase
from app.purchases.schemas import PurchaseCreate


@pytest.fixture
def postgres_database():
    import os

    url = os.environ.get('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is not configured; PostgreSQL integration checks were not run.')

    admin_engine = create_engine(url, connect_args={'connect_timeout': 3})
    schema = f'ip_integrity_{uuid4().hex[:16]}'
    with admin_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(url, connect_args={'connect_timeout': 3, 'options': f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            role = Role(name='postgres-integrity')
            supplier = Supplier(name=f'Fornecedor {schema}', location='Campinas, SP')
            product = Product(name=f'Produto {schema}', unit='un', current_cost=10, current_price=25, minimum_stock=0)
            db.add_all([role, supplier, product])
            db.flush()
            actor = User(name='PostgreSQL Test', email=f'{schema}@example.com', role_id=role.id, is_general_admin=True)
            customer = Customer(name=f'Cliente {schema}', origin='INTERNAL', status='ACTIVE')
            db.add_all([actor, customer])
            db.flush()
            balance = InventoryBalance(product_id=product.id, quantity=Decimal('5'))
            db.add(balance)
            db.commit()
            yield engine, actor.id, supplier.id, product.id, customer.id
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin_engine.dispose()


def _run_concurrently(engine, operation, count=2):
    platform.uname()
    barrier = Barrier(count)

    def run(index):
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=10)
            return operation(index, db)

    with ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(run, index) for index in range(count)]
        return [future.result(timeout=30) for future in futures]


def test_postgres_concurrent_adjustments_preserve_both_deltas(postgres_database):
    engine, actor_id, _, product_id, _ = postgres_database

    def adjust(index, db):
        from app.database.models import User
        from app.inventory.router import adjust as adjust_inventory
        from app.inventory.schemas import InventoryAdjustment

        return adjust_inventory(InventoryAdjustment(product_id=product_id, quantity_delta=Decimal(index + 3), reason=f'concorrente-{index}'), db.get(User, actor_id), db)

    _run_concurrently(engine, adjust)
    with Session(engine) as db:
        assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product_id)) == Decimal('12.000')
        assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.product_id == product_id)) == 2


def test_postgres_two_concurrent_orders_cannot_oversell(postgres_database):
    engine, actor_id, _, product_id, customer_id = postgres_database

    def sell(index, db):
        from app.database.models import User

        payload = OrderCreate(customer_id=customer_id, ordered_at=datetime.now(timezone.utc), status='CONFIRMED', items=[{'product_id': product_id, 'quantity': Decimal('4')}])
        try:
            return create_order(payload, db.get(User, actor_id), db)['id']
        except HTTPException as error:
            return error.status_code

    results = _run_concurrently(engine, sell)
    with Session(engine) as db:
        assert sum(isinstance(result, str) for result in results) == 1
        assert 409 in results
        assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product_id)) == Decimal('1.000')
        assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.product_id == product_id)) == 1


def test_postgres_concurrent_external_order_retry_is_idempotent(postgres_database):
    engine, actor_id, _, product_id, customer_id = postgres_database

    def import_order(_, db):
        from app.database.models import User

        payload = OrderCreate(customer_id=customer_id, ordered_at=datetime.now(timezone.utc), status='DELIVERED', source='SITE_PUBLICO', external_id='same-external-order', items=[{'product_id': product_id, 'quantity': Decimal('2')}])
        return create_order(payload, db.get(User, actor_id), db)['id']

    order_ids = _run_concurrently(engine, import_order)
    with Session(engine) as db:
        assert len(set(order_ids)) == 1
        assert db.scalar(select(func.count(Order.id)).where(Order.source == 'SITE_PUBLICO', Order.external_id == 'same-external-order')) == 1
        assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product_id)) == Decimal('3.000')
        assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.order_id == order_ids[0])) == 1
        assert db.scalar(select(func.count(AccountReceivable.id)).where(AccountReceivable.reference_id == order_ids[0])) == 1
        assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.entity_id == order_ids[0])) == 1


def test_postgres_concurrent_purchase_retry_is_idempotent(postgres_database):
    engine, actor_id, supplier_id, product_id, _ = postgres_database

    def purchase(_, db):
        from app.database.models import User

        payload = PurchaseCreate(supplier_id=supplier_id, purchased_at=datetime.now(timezone.utc), idempotency_key='same-purchase-key', items=[{'product_id': product_id, 'quantity': Decimal('2'), 'unit_cost': Decimal('12')}])
        return create_purchase(payload, db.get(User, actor_id), db)['id']

    purchase_ids = _run_concurrently(engine, purchase)
    with Session(engine) as db:
        assert len(set(purchase_ids)) == 1
        assert db.scalar(select(func.count(Purchase.id)).where(Purchase.idempotency_key == 'same-purchase-key')) == 1
        assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product_id)) == Decimal('7.000')
        assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.purchase_id == purchase_ids[0])) == 1
        assert db.scalar(select(func.count(AccountPayable.id)).where(AccountPayable.reference_id == purchase_ids[0])) == 1


def test_postgres_external_customer_retry_is_idempotent(postgres_database):
    engine, actor_id, _, _, _ = postgres_database

    def register(_, db):
        from app.database.models import User

        return create_customer(CustomerCreate(name='Cliente site', email='postgres-site@example.com', origin='SITE_PUBLICO', external_id='same-customer'), db.get(User, actor_id), db)['id']

    customer_ids = _run_concurrently(engine, register)
    with Session(engine) as db:
        assert len(set(customer_ids)) == 1
        assert db.scalar(select(func.count(Customer.id)).where(Customer.origin == 'SITE_PUBLICO', Customer.external_id == 'same-customer')) == 1


def test_postgres_reference_and_settlement_keys_are_unique(postgres_database):
    engine, actor_id, _, _, _ = postgres_database
    with Session(engine) as db:
        first = CashMovement(movement_type='ENTRY', amount=1, origin='TEST', reference_id='ref-unique', settlement_key='settlement-unique', created_by=actor_id)
        db.add(first)
        db.commit()
        db.add(CashMovement(movement_type='ENTRY', amount=1, origin='TEST', reference_id='ref-unique-2', settlement_key='settlement-unique', created_by=actor_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_postgres_concurrent_order_cancellation_reverses_stock_once(postgres_database):
    engine, actor_id, _, product_id, customer_id = postgres_database
    with Session(engine, expire_on_commit=False) as db:
        from app.database.models import User
        from app.orders.schemas import OrderStatusUpdate
        from app.orders.router import update_order_status

        order = create_order(OrderCreate(customer_id=customer_id, ordered_at=datetime.now(timezone.utc), status='CONFIRMED', items=[{'product_id': product_id, 'quantity': Decimal('2')}]), db.get(User, actor_id), db)
        order_id = order['id']

    def cancel(_, db):
        from app.database.models import User
        from app.orders.schemas import OrderStatusUpdate
        from app.orders.router import update_order_status

        return update_order_status(order_id, OrderStatusUpdate(status='CANCELLED'), db.get(User, actor_id), db)['status']

    assert _run_concurrently(engine, cancel) == ['CANCELLED', 'CANCELLED']
    with Session(engine) as db:
        assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product_id)) == Decimal('5.000')
        assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.order_id == order_id, InventoryMovement.reason == 'ORDER_CANCELLATION')) == 1