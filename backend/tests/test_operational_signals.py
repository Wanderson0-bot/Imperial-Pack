from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.alerts.service import accessible_scopes, refresh_operational_signals
from app.auth.dependencies import current_user
from app.database.base import Base
from app.database.models import (
    AccountPayable,
    AccountReceivable,
    AuditLog,
    Customer,
    InventoryBalance,
    Order,
    OrderItem,
    Partner,
    PartnerAlert,
    PartnerOpportunity,
    Permission,
    Product,
    Role,
    RolePermission,
    Supplier,
    User,
)
from app.database.session import get_db, set_user_context
from app.main import app

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


@pytest.fixture
def signals_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='signals-test', is_system=True)
        db.add(role)
        db.flush()
        actor = User(name='Signals User', email='signals@example.com', role_id=role.id, is_general_admin=True)
        db.add(actor)
        db.commit()
        yield db, actor
    engine.dispose()


def add_customer(db: Session, name: str = 'Cliente') -> Customer:
    customer = Customer(name=name, origin='INTERNAL', status='ACTIVE')
    db.add(customer)
    db.flush()
    return customer


def add_product(db: Session, name: str = 'Produto', minimum: Decimal = Decimal('10')) -> Product:
    product = Product(name=name, unit='un', current_cost=Decimal('5'), current_price=Decimal('10'), minimum_stock=minimum)
    db.add(product)
    db.flush()
    return product


def add_order(db: Session, customer: Customer, product: Product, ordered_at: datetime, quantity: Decimal = Decimal('2')) -> Order:
    order = Order(customer_id=customer.id, ordered_at=ordered_at, status='DELIVERED', subtotal=quantity * product.current_price, total=quantity * product.current_price)
    db.add(order)
    db.flush()
    db.add(OrderItem(order_id=order.id, product_id=product.id, product_name_snapshot=product.name, unit_price_snapshot=product.current_price, quantity=quantity, subtotal=quantity * product.current_price))
    db.flush()
    return order


def add_three_weekly_orders(db: Session, customer: Customer, product: Product) -> None:
    for days_ago in (60, 40, 20):
        add_order(db, customer, product, NOW - timedelta(days=days_ago))
    db.commit()


def test_stock_low_and_zero_generate_prioritized_alerts_and_opportunities(signals_db):
    db, _ = signals_db
    low = add_product(db, 'Estoque baixo')
    empty = add_product(db, 'Estoque zerado')
    db.add_all([
        InventoryBalance(product_id=low.id, quantity=Decimal('4')),
        InventoryBalance(product_id=empty.id, quantity=Decimal('0')),
    ])
    db.commit()

    refresh_operational_signals(db, {'inventory'}, NOW)
    alerts = {record.entity_label: record for record in db.scalars(select(PartnerAlert))}
    opportunities = list(db.scalars(select(PartnerOpportunity)))

    assert alerts['Estoque baixo'].alert_type == 'stock_below_minimum'
    assert alerts['Estoque baixo'].priority == 'medium'
    assert alerts['Estoque zerado'].alert_type == 'stock_zero'
    assert alerts['Estoque zerado'].priority == 'high'
    assert len(opportunities) == 2
    assert all(item.evidence['quantity'] in {'4.000', '0.000'} for item in opportunities)


def test_overdue_and_upcoming_financial_accounts_generate_alerts(signals_db):
    db, actor = signals_db
    supplier = Supplier(name='Fornecedor', is_active=True)
    customer = add_customer(db, 'Cliente Financeiro')
    db.add(supplier)
    db.flush()
    db.add_all([
        AccountPayable(supplier_id=supplier.id, description='Título vencido', amount=Decimal('50'), due_at=NOW - timedelta(days=1), status='PENDING', created_by=actor.id),
        AccountReceivable(customer_id=customer.id, description='Título próximo', amount=Decimal('80'), due_at=NOW + timedelta(days=3), status='PENDING', created_by=actor.id),
    ])
    db.commit()

    refresh_operational_signals(db, {'finance'}, NOW)
    alerts = {record.alert_type: record for record in db.scalars(select(PartnerAlert))}

    assert alerts['payable_overdue'].priority == 'high'
    assert alerts['receivable_due_soon'].priority == 'medium'
    assert 'Título vencido' in alerts['payable_overdue'].description


def test_customer_near_replenishment_is_based_on_purchase_history(signals_db):
    db, _ = signals_db
    customer = add_customer(db, 'Cliente recorrente')
    product = add_product(db, 'Produto recorrente', Decimal('0'))
    add_three_weekly_orders(db, customer, product)

    history_available, _ = refresh_operational_signals(db, {'customers'}, NOW)
    alerts = list(db.scalars(select(PartnerAlert)))
    opportunities = list(db.scalars(select(PartnerOpportunity)))

    assert history_available
    assert any(item.alert_type == 'customer_replenishment_window' for item in alerts)
    opportunity = next(item for item in opportunities if item.entity_type == 'customer')
    assert opportunity.evidence['orders'] == 3
    assert 'cliente' in opportunity.action.lower()


def test_customer_without_sufficient_history_has_no_replenishment_opportunity(signals_db):
    db, _ = signals_db
    customer = add_customer(db, 'Cliente sem histórico')
    product = add_product(db, 'Produto sem recorrência', Decimal('0'))
    add_order(db, customer, product, NOW - timedelta(days=20))
    db.commit()

    history_available, _ = refresh_operational_signals(db, {'customers'}, NOW)

    assert not history_available
    assert db.scalar(select(PartnerOpportunity.id).where(PartnerOpportunity.customer_id == customer.id)) is None


def test_partner_near_replenishment_uses_partner_customer_orders(signals_db):
    db, actor = signals_db
    customer = add_customer(db, 'Parceiro recorrente')
    product = add_product(db, 'Produto parceiro', Decimal('0'))
    partner = Partner(customer_id=customer.id, status='ACTIVE', created_by=actor.id)
    db.add(partner)
    db.flush()
    add_three_weekly_orders(db, customer, product)

    refresh_operational_signals(db, {'partners'}, NOW)
    alerts = list(db.scalars(select(PartnerAlert).where(PartnerAlert.entity_type == 'partner')))
    opportunities = list(db.scalars(select(PartnerOpportunity).where(PartnerOpportunity.partner_id == partner.id)))

    assert any(item.alert_type == 'partner_replenishment_window' for item in alerts)
    assert opportunities
    assert all(item.evidence.get('last_purchase') for item in opportunities)


def test_partner_purchase_quantity_change_uses_recorded_product_quantities(signals_db):
    db, actor = signals_db
    customer = add_customer(db, 'Parceiro com mudança de padrão')
    product = add_product(db, 'Produto em maior quantidade', Decimal('0'))
    partner = Partner(customer_id=customer.id, status='ACTIVE', created_by=actor.id)
    db.add(partner)
    db.flush()
    for days_ago, quantity in ((60, Decimal('2')), (40, Decimal('2')), (20, Decimal('5'))):
        add_order(db, customer, product, NOW - timedelta(days=days_ago), quantity)
    db.commit()

    refresh_operational_signals(db, {'partners'}, NOW)
    alert = db.scalar(select(PartnerAlert).where(PartnerAlert.alert_type == 'partner_purchase_pattern_change'))
    opportunity = db.scalar(select(PartnerOpportunity).where(PartnerOpportunity.dedupe_key.like('partner_purchase_pattern_change:%')))

    assert alert is not None
    assert alert.priority == 'high'
    assert Decimal(opportunity.evidence['previous_average_quantity']) == Decimal('2')
    assert Decimal(opportunity.evidence['latest_quantity']) == Decimal('5')


def test_repeated_reads_update_existing_alerts_and_opportunities(signals_db):
    db, _ = signals_db
    product = add_product(db, 'Produto sem estoque')
    db.add(InventoryBalance(product_id=product.id, quantity=Decimal('0')))
    db.commit()

    refresh_operational_signals(db, {'inventory'}, NOW)
    refresh_operational_signals(db, {'inventory'}, NOW + timedelta(hours=1))

    assert len(list(db.scalars(select(PartnerAlert)))) == 1
    assert len(list(db.scalars(select(PartnerOpportunity)))) == 1


def test_signal_generation_is_limited_to_user_permissions(signals_db):
    db, _ = signals_db
    role = Role(name='inventory-reader', is_system=False)
    db.add(role)
    db.flush()
    permission = Permission(key='inventory:read', description='Read inventory')
    db.add(permission)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    user = User(name='Inventory Reader', email='inventory@example.com', role_id=role.id, is_general_admin=False)
    product = add_product(db, 'Estoque restrito')
    supplier = Supplier(name='Fornecedor restrito', is_active=True)
    db.add_all([user, supplier])
    db.flush()
    db.add_all([
        InventoryBalance(product_id=product.id, quantity=Decimal('0')),
        AccountPayable(supplier_id=supplier.id, description='Financeiro restrito', amount=Decimal('10'), due_at=NOW - timedelta(days=1), status='PENDING'),
    ])
    db.commit()

    scopes = accessible_scopes(db, user)
    refresh_operational_signals(db, scopes, NOW)
    alerts = list(db.scalars(select(PartnerAlert)))

    assert scopes == {'inventory'}
    assert alerts
    assert all(item.entity_type == 'inventory_product' for item in alerts)


def test_alert_api_is_authenticated_and_status_changes_are_audited(signals_db):
    db, actor = signals_db
    product = add_product(db, 'Produto API')
    db.add(InventoryBalance(product_id=product.id, quantity=Decimal('0')))
    db.commit()

    def database_override():
        set_user_context(db, actor.id, actor.is_general_admin)
        yield db

    app.dependency_overrides[get_db] = database_override
    try:
        with TestClient(app) as client:
            assert client.get('/api/alerts').status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            alerts_response = client.get('/api/alerts')
            assert alerts_response.status_code == 200
            alert = alerts_response.json()[0]
            assert alert['entity_label'] == 'Produto API'
            assert client.get(f"/api/alerts/{alert['id']}").status_code == 200
            changed = client.patch(f"/api/alerts/{alert['id']}", json={'status': 'RESOLVED'})
            assert changed.status_code == 200
            assert changed.json()['status'] == 'RESOLVED'
    finally:
        app.dependency_overrides.pop(current_user, None)
        app.dependency_overrides.pop(get_db, None)

    audit_entry = db.scalar(select(AuditLog).where(AuditLog.entity_type == 'alert', AuditLog.entity_id == alert['id']))
    assert audit_entry.action == 'alerts.status.update'


def test_alert_api_does_not_expose_other_permission_contexts(signals_db):
    db, admin = signals_db
    role = Role(name='inventory-api-reader', is_system=False)
    permission = Permission(key='inventory:read', description='Read inventory')
    db.add_all([role, permission])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    reader = User(name='Inventory API Reader', email='inventory-api@example.com', role_id=role.id, is_general_admin=False)
    product = add_product(db, 'Produto isolado')
    supplier = Supplier(name='Fornecedor API', is_active=True)
    partner_customer = add_customer(db, 'Parceiro isolado')
    partner = Partner(customer_id=partner_customer.id, status='ACTIVE')
    db.add_all([reader, supplier, partner])
    db.flush()
    db.add_all([
        InventoryBalance(product_id=product.id, quantity=Decimal('0')),
        AccountPayable(supplier_id=supplier.id, description='Conta isolada', amount=Decimal('15'), due_at=NOW - timedelta(days=1), status='PENDING'),
        PartnerAlert(partner_id=partner.id, entity_type='partner', entity_id=partner.id, entity_label=partner_customer.name, alert_type='partner_example', title='Alerta parceiro', description='Evento do contexto parceiro.', reason='Histórico parceiro.', priority='medium', status='OPEN', message='Evento do contexto parceiro.'),
    ])
    db.commit()

    def database_override():
        set_user_context(db, admin.id, admin.is_general_admin)
        yield db

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[current_user] = lambda: admin
    try:
        with TestClient(app) as client:
            assert any(item['entity_type'] == 'payable' for item in client.get('/api/alerts').json())
            partner_alerts = client.get('/api/partners/alerts').json()
            assert partner_alerts
            assert all(item['entity_type'] == 'partner' for item in partner_alerts)
        app.dependency_overrides[current_user] = lambda: reader
        set_user_context(db, reader.id, reader.is_general_admin)
        with TestClient(app) as client:
            restricted_alerts = client.get('/api/alerts')
            assert restricted_alerts.status_code == 200
            assert restricted_alerts.json()
            assert all(item['entity_type'] == 'inventory_product' for item in restricted_alerts.json())
    finally:
        app.dependency_overrides.pop(current_user, None)
        app.dependency_overrides.pop(get_db, None)