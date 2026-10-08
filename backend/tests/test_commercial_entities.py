from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.customers.router import create_customer, customer_history_summary, update_customer
from app.customers.schemas import AddressInput, CustomerCreate, CustomerUpdate
from app.database.base import Base
from app.database.models import AccountReceivable, AuditLog, Customer, InventoryBalance, InventoryMovement, Order, OrderItem, Partner, Product, Purchase, Role, Supplier, SupplierProduct, User
from app.orders.router import create_order, get_order
from app.orders.schemas import OrderCreate
from app.partners.router import activate_partner
from app.partners.schemas import PartnerCreate
from app.products.router import update_product
from app.products.schemas import ProductUpdate
from app.reports.router import overview
from app.suppliers.router import create_supplier
from app.suppliers.schemas import SupplierCreate


@pytest.fixture
def commercial_database():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='commercial-test', is_system=True)
        first_product = Product(name='Produto A', unit='un', current_cost=5, current_price=12, minimum_stock=0)
        second_product = Product(name='Produto B', unit='un', current_cost=8, current_price=20, minimum_stock=0)
        db.add_all([role, first_product, second_product])
        db.flush()
        actor = User(name='Commercial Admin', email='commercial-test@example.com', role_id=role.id, is_general_admin=True)
        db.add_all([actor, InventoryBalance(product_id=first_product.id, quantity=Decimal('20')), InventoryBalance(product_id=second_product.id, quantity=Decimal('20'))])
        db.commit()
        yield db, actor, first_product, second_product
    engine.dispose()


def test_site_customer_links_to_existing_manual_customer_and_retries_idempotently(commercial_database):
    db, actor, _, _ = commercial_database
    manual = create_customer(CustomerCreate(name='Ana Silva', email='ana@example.com', phone='11987654321'), actor, db)
    website = create_customer(CustomerCreate(name='Ana S.', email='ANA@example.com', phone='(11) 98765-4321', origin='SITE_PUBLICO', external_id='shop-customer-42'), actor, db)
    retry = create_customer(CustomerCreate(name='Ana Updated', email='ana@example.com', origin='SITE_PUBLICO', external_id='shop-customer-42'), actor, db)

    assert website['id'] == manual['id'] == retry['id']
    assert retry['name'] == 'Ana Silva'
    assert retry['external_id'] == 'shop-customer-42'
    assert db.scalar(select(func.count(Customer.id))) == 1


def test_customer_email_duplicate_and_address_update_are_safe(commercial_database):
    db, actor, _, _ = commercial_database
    created = create_customer(CustomerCreate(
        name='Bruno Lima',
        email='bruno@example.com',
        address=AddressInput(street='Rua A', city='Campinas', state='SP'),
    ), actor, db)

    with pytest.raises(HTTPException) as duplicate:
        create_customer(CustomerCreate(name='Bruno L.', email='BRUNO@example.com'), actor, db)
    assert duplicate.value.status_code == 409

    updated = update_customer(created['id'], CustomerUpdate(name='Bruno Lima', address=AddressInput(street='Rua B', city='Campinas', state='SP')), actor, db)
    assert updated['address'].street == 'Rua B'


def test_customer_can_be_created_with_optional_email_notes_and_partial_address(commercial_database):
    db, actor, _, _ = commercial_database
    created = create_customer(CustomerCreate(
        name='Cliente com endereço parcial',
        email='parcial@example.com',
        notes='Observação opcional',
        address=AddressInput(number='42', postal_code='13000-000'),
    ), actor, db)

    assert created['email'] == 'parcial@example.com'
    assert created['notes'] == 'Observação opcional'
    assert created['address'].street is None
    assert created['address'].city is None
    assert created['address'].number == '42'
    assert created['address'].postal_code == '13000-000'


def test_supplier_location_and_products_are_many_to_many(commercial_database):
    db, actor, first_product, second_product = commercial_database
    first = create_supplier(SupplierCreate(name='Fornecedor A', location='Campinas, SP', product_ids=[first_product.id]), actor, db)
    second = create_supplier(SupplierCreate(name='Fornecedor B', location='São Paulo, SP', product_ids=[first_product.id, second_product.id]), actor, db)

    assert first['location'] == 'Campinas, SP'
    assert set(first['product_ids']) == {first_product.id}
    assert set(second['product_ids']) == {first_product.id, second_product.id}
    assert db.scalar(select(func.count(SupplierProduct.product_id)).where(SupplierProduct.product_id == first_product.id)) == 2

    with pytest.raises(HTTPException) as duplicate:
        create_supplier(SupplierCreate(name=' fornecedor a ', location='Outra localização'), actor, db)
    assert duplicate.value.status_code == 409


def test_website_order_is_idempotent_and_updates_metrics_stock_and_history(commercial_database):
    db, actor, product, _ = commercial_database
    customer = create_customer(CustomerCreate(name='Cliente Site', email='site@example.com'), actor, db)
    payload = OrderCreate(
        customer_id=customer['id'],
        ordered_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        status='DELIVERED',
        source='SITE_PUBLICO',
        external_id='shop-order-77',
        items=[{'product_id': product.id, 'quantity': Decimal('2')}],
    )

    first = create_order(payload, actor, db)
    detail = get_order(first['id'], None, db)
    retry = create_order(payload, actor, db)

    assert first['id'] == retry['id']
    assert detail['external_id'] == 'shop-order-77'
    assert detail['customer_id'] == customer['id']
    assert detail['status'] == 'DELIVERED'
    assert first['total'] == Decimal('24.0000')
    assert db.scalar(select(func.count(Order.id))) == 1
    assert db.scalar(select(func.count(OrderItem.id))) == 1
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id)) == Decimal('18.000')
    assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.order_id == first['id'])) == 1
    assert db.scalar(select(func.count(AccountReceivable.id)).where(AccountReceivable.reference_id == first['id'])) == 1
    assert db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action == 'orders.create', AuditLog.entity_id == first['id'])) == 1
    history = customer_history_summary(db, customer['id'])
    assert history['orders'] == 1
    assert history['total_spent'] == Decimal('24.00')


def test_partner_activation_reuses_customer_and_rejects_second_active_record(commercial_database):
    db, actor, _, _ = commercial_database
    customer = create_customer(CustomerCreate(name='Partner Customer', email='partner@example.com'), actor, db)
    first = activate_partner(PartnerCreate(customer_id=customer['id']), actor, db)
    assert first['customer_id'] == customer['id']
    assert db.scalar(select(func.count(Partner.id)).where(Partner.customer_id == customer['id'])) == 1

    with pytest.raises(HTTPException) as duplicate:
        activate_partner(PartnerCreate(customer_id=customer['id']), actor, db)
    assert duplicate.value.status_code == 409
    assert db.scalar(select(func.count(Partner.id)).where(Partner.customer_id == customer['id'])) == 1


def test_product_update_serializes_decimal_audit_details(commercial_database):
    db, actor, product, _ = commercial_database
    db.refresh(product)

    updated = update_product(
        product.id,
        ProductUpdate(minimum_stock=Decimal('3')),
        actor,
        db,
    )
    audit_entry = db.scalar(select(AuditLog).where(
        AuditLog.action == 'products.update',
        AuditLog.entity_id == product.id,
    ))

    assert updated.minimum_stock == Decimal('3')
    assert audit_entry is not None
    assert audit_entry.details == {'minimum_stock': '3'}


def test_overview_omits_cancelled_purchase_total(commercial_database):
    db, actor, _, _ = commercial_database
    supplier = Supplier(name='Report Supplier', location='Test')
    db.add(supplier)
    db.flush()
    purchased_at = datetime.now(timezone.utc)
    db.add_all([
        Purchase(
            supplier_id=supplier.id,
            purchased_at=purchased_at,
            products_value=10,
            total=10,
            status='APPROVED',
        ),
        Purchase(
            supplier_id=supplier.id,
            purchased_at=purchased_at,
            products_value=20,
            total=20,
            status='CANCELLED',
        ),
    ])
    db.commit()

    report = overview(
        start=date.today(),
        end=date.today(),
        _=actor,
        db=db,
    )

    assert report['purchases'] == Decimal('10')