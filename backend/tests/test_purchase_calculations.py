from datetime import datetime, timezone
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models import AccountPayable, InventoryBalance, InventoryMovement, Product, Purchase, PurchaseItem, Role, Supplier, User
from app.purchases.router import cancel_purchase, create_purchase
from app.purchases.schemas import PurchaseCreate

MIGRATION_PATH = Path(__file__).parents[1] / 'migrations' / 'versions' / '0002_purchase_details.py'
MIGRATION_SPEC = spec_from_file_location('purchase_details_migration', MIGRATION_PATH)
assert MIGRATION_SPEC and MIGRATION_SPEC.loader
PURCHASE_DETAILS_MIGRATION = module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(PURCHASE_DETAILS_MIGRATION)


@pytest.fixture
def purchase_database():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='purchase-test', is_system=True)
        supplier = Supplier(name='Fornecedor de teste')
        first_product = Product(name='Produto A', unit='un', current_cost=0, current_price=100, minimum_stock=0)
        second_product = Product(name='Produto B', unit='un', current_cost=0, current_price=60, minimum_stock=0)
        db.add_all([role, supplier, first_product, second_product])
        db.flush()
        actor = User(name='Test Admin', email='purchase-test@example.com', role_id=role.id, is_general_admin=True)
        db.add(actor)
        db.commit()
        yield db, actor, supplier, first_product, second_product
    engine.dispose()


def test_purchase_discounts_total_and_freight_are_allocated_by_net_value(purchase_database):
    db, actor, supplier, first_product, second_product = purchase_database
    payload = PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        document_number='NF-123',
        observations='Recebimento completo',
        freight=Decimal('100'),
        items=[
            {'product_id': first_product.id, 'quantity': Decimal('10'), 'unit_cost': Decimal('70'), 'discount': Decimal('0'), 'description': 'Caixa grande'},
            {'product_id': second_product.id, 'quantity': Decimal('10'), 'unit_cost': Decimal('30'), 'discount': Decimal('0')},
        ],
    )

    result = create_purchase(payload, actor, db)

    assert result['products_value'] == Decimal('1000.00')
    assert result['discount_total'] == Decimal('0.00')
    assert result['total'] == Decimal('1100.00')
    items = {item.product_id: item for item in db.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == result['id']))}
    assert items[first_product.id].freight_share == Decimal('70.0000')
    assert items[second_product.id].freight_share == Decimal('30.0000')
    assert items[first_product.id].description == 'Caixa grande'
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == first_product.id)) == Decimal('10.000')
    assert db.scalar(select(InventoryMovement.id).where(InventoryMovement.purchase_id == result['id'])) is not None
    saved_purchase = db.get(Purchase, result['id'])
    assert saved_purchase.document_number == 'NF-123'
    assert saved_purchase.observations == 'Recebimento completo'


def test_line_discount_reduces_purchase_total_and_real_unit_cost(purchase_database):
    db, actor, supplier, product, _ = purchase_database
    payload = PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        freight=Decimal('0'),
        items=[{'product_id': product.id, 'quantity': Decimal('20'), 'unit_cost': Decimal('22'), 'discount': Decimal('10')}],
    )

    result = create_purchase(payload, actor, db)
    item = db.scalar(select(PurchaseItem).where(PurchaseItem.purchase_id == result['id']))

    assert result['products_value'] == Decimal('440.00')
    assert result['discount_total'] == Decimal('10.00')
    assert result['total'] == Decimal('430.00')
    assert item.real_unit_cost == Decimal('21.5000')


def test_purchase_item_discount_cannot_exceed_gross_value():
    with pytest.raises(ValidationError):
        PurchaseCreate(
            supplier_id='supplier',
            purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            items=[{'product_id': 'product', 'quantity': 2, 'unit_cost': 22, 'discount': 45}],
        )


def test_fractional_freight_allocations_reconcile_to_the_purchase_total(purchase_database):
    db, actor, supplier, first_product, second_product = purchase_database
    third_product = Product(name='Produto C', unit='un', current_cost=0, current_price=20, minimum_stock=0)
    db.add(third_product)
    db.commit()
    payload = PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        freight=Decimal('0.01'),
        items=[
            {'product_id': first_product.id, 'quantity': Decimal('1'), 'unit_cost': Decimal('1')},
            {'product_id': second_product.id, 'quantity': Decimal('1'), 'unit_cost': Decimal('1')},
            {'product_id': third_product.id, 'quantity': Decimal('1'), 'unit_cost': Decimal('1')},
        ],
    )

    result = create_purchase(payload, actor, db)
    shares = list(db.scalars(select(PurchaseItem.freight_share).where(PurchaseItem.purchase_id == result['id'])))

    assert sum(shares, Decimal('0')) == Decimal('0.0100')


def test_purchase_retry_is_idempotent_for_stock_and_payable(purchase_database):
    db, actor, supplier, product, _ = purchase_database
    payload = PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        idempotency_key='purchase-invoice-unique-1',
        items=[{'product_id': product.id, 'quantity': Decimal('3'), 'unit_cost': Decimal('12')}],
    )

    first = create_purchase(payload, actor, db)
    retry = create_purchase(payload, actor, db)

    assert retry['id'] == first['id']
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id)) == Decimal('3.000')
    assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.purchase_id == first['id'])) == 1
    assert db.scalar(select(func.count(AccountPayable.id)).where(AccountPayable.reference_id == first['id'])) == 1


def test_purchase_cancellation_reverses_stock_cost_and_payable_once(purchase_database):
    db, actor, supplier, product, _ = purchase_database
    product.current_cost = Decimal('10')
    db.commit()
    purchase = create_purchase(PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        items=[{'product_id': product.id, 'quantity': Decimal('2'), 'unit_cost': Decimal('20')}],
    ), actor, db)

    cancelled = cancel_purchase(purchase['id'], actor, db)
    retry = cancel_purchase(purchase['id'], actor, db)

    payable = db.scalar(select(AccountPayable).where(AccountPayable.reference_id == purchase['id']))
    movements = list(db.scalars(select(InventoryMovement).where(InventoryMovement.purchase_id == purchase['id'])))
    assert cancelled['status'] == retry['status'] == 'CANCELLED'
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id)) == Decimal('0.000')
    assert db.get(Product, product.id).current_cost == Decimal('10.0000')
    assert payable.status == 'CANCELLED'
    assert len(movements) == 2
    assert [movement.reason for movement in movements].count('PURCHASE_CANCELLATION') == 1


def test_purchase_cancellation_refuses_consumed_stock(purchase_database):
    db, actor, supplier, product, _ = purchase_database
    purchase = create_purchase(PurchaseCreate(
        supplier_id=supplier.id,
        purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        items=[{'product_id': product.id, 'quantity': Decimal('2'), 'unit_cost': Decimal('20')}],
    ), actor, db)
    balance = db.scalar(select(InventoryBalance).where(InventoryBalance.product_id == product.id))
    balance.quantity = Decimal('1')
    db.commit()

    with pytest.raises(HTTPException, match='already been consumed'):
        cancel_purchase(purchase['id'], actor, db)

    assert db.get(Purchase, purchase['id']).status == 'APPROVED'
    assert balance.quantity == Decimal('1')


def test_purchase_details_migration_is_safe_after_dynamic_initial_revision():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            PURCHASE_DETAILS_MIGRATION.upgrade()
        purchase_columns = {column['name'] for column in inspect(connection).get_columns('purchases')}
        item_columns = {column['name'] for column in inspect(connection).get_columns('purchase_items')}
    assert {'document_number', 'observations', 'discount_total'} <= purchase_columns
    assert {'discount', 'description'} <= item_columns
    engine.dispose()


def test_purchase_details_migration_upgrades_existing_legacy_tables():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE purchases (id VARCHAR(36), supplier_id VARCHAR(36), purchased_at DATETIME, products_value NUMERIC(14, 2), freight NUMERIC(14, 2), other_costs NUMERIC(14, 2), total NUMERIC(14, 2), status VARCHAR(30), created_by VARCHAR(36))'))
        connection.execute(text('CREATE TABLE purchase_items (id VARCHAR(36), purchase_id VARCHAR(36), product_id VARCHAR(36), quantity NUMERIC(14, 3), unit_cost NUMERIC(14, 4), freight_share NUMERIC(14, 4), other_cost_share NUMERIC(14, 4), real_unit_cost NUMERIC(14, 4))'))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            PURCHASE_DETAILS_MIGRATION.upgrade()
        purchase_columns = {column['name'] for column in inspect(connection).get_columns('purchases')}
        item_columns = {column['name'] for column in inspect(connection).get_columns('purchase_items')}
    assert {'document_number', 'observations', 'discount_total'} <= purchase_columns
    assert {'discount', 'description'} <= item_columns
    engine.dispose()