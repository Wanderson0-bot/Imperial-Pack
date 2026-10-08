from datetime import datetime, timezone
from decimal import Decimal
from contextlib import contextmanager

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.models import Customer, Order, OrderItem, Partner, Product, Role, User
from app.customers.router import customer_history_summary, customer_replenishment_estimate
from app.partners.router import partner_history_summary, partner_replenishment_estimate


@contextmanager
def make_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='history-test', is_system=True)
        db.add(role)
        db.flush()
        user = User(name='History User', email='history@example.com', role_id=role.id, is_general_admin=True)
        db.add(user)
        db.flush()

        product_a = Product(name='Produto A', unit='un', current_cost=Decimal('5'), current_price=Decimal('10'), minimum_stock=Decimal('2'))
        product_b = Product(name='Produto B', unit='un', current_cost=Decimal('8'), current_price=Decimal('20'), minimum_stock=Decimal('2'))
        db.add_all([product_a, product_b])
        db.flush()

        customer_without = Customer(name='Cliente sem histórico', origin='INTERNAL', status='ACTIVE')
        customer_with = Customer(name='Cliente recorrente', origin='INTERNAL', status='ACTIVE')
        db.add_all([customer_without, customer_with])
        db.flush()

        partner = Partner(customer_id=customer_with.id, status='ACTIVE', created_by=user.id)
        db.add(partner)
        db.flush()

        order1 = Order(customer_id=customer_with.id, ordered_at=datetime(2026, 1, 1, tzinfo=timezone.utc), status='DELIVERED', subtotal=Decimal('50'), total=Decimal('50'))
        order2 = Order(customer_id=customer_with.id, ordered_at=datetime(2026, 1, 15, tzinfo=timezone.utc), status='DELIVERED', subtotal=Decimal('90'), total=Decimal('90'))
        order3 = Order(customer_id=customer_with.id, ordered_at=datetime(2026, 2, 15, tzinfo=timezone.utc), status='DELIVERED', subtotal=Decimal('120'), total=Decimal('120'))
        new_order = Order(customer_id=customer_with.id, ordered_at=datetime(2025, 12, 1, tzinfo=timezone.utc), status='NEW', subtotal=Decimal('500'), total=Decimal('500'))
        cancelled_order = Order(customer_id=customer_with.id, ordered_at=datetime(2026, 3, 1, tzinfo=timezone.utc), status='CANCELLED', subtotal=Decimal('600'), total=Decimal('600'))
        db.add_all([order1, order2, order3, new_order, cancelled_order])
        db.flush()

        db.add_all([
            OrderItem(order_id=order1.id, product_id=product_a.id, product_name_snapshot=product_a.name, unit_price_snapshot=product_a.current_price, quantity=Decimal('2'), subtotal=Decimal('20')),
            OrderItem(order_id=order1.id, product_id=product_b.id, product_name_snapshot=product_b.name, unit_price_snapshot=product_b.current_price, quantity=Decimal('3'), subtotal=Decimal('30')),
            OrderItem(order_id=order2.id, product_id=product_a.id, product_name_snapshot=product_a.name, unit_price_snapshot=product_a.current_price, quantity=Decimal('4'), subtotal=Decimal('40')),
            OrderItem(order_id=order2.id, product_id=product_b.id, product_name_snapshot=product_b.name, unit_price_snapshot=product_b.current_price, quantity=Decimal('2'), subtotal=Decimal('50')),
            OrderItem(order_id=order3.id, product_id=product_a.id, product_name_snapshot=product_a.name, unit_price_snapshot=product_a.current_price, quantity=Decimal('3'), subtotal=Decimal('30')),
            OrderItem(order_id=order3.id, product_id=product_b.id, product_name_snapshot=product_b.name, unit_price_snapshot=product_b.current_price, quantity=Decimal('4'), subtotal=Decimal('90')),
        ])
        db.commit()
        yield db, customer_without, customer_with, partner, product_a, product_b
    engine.dispose()


def test_customer_without_history_has_insufficient_data():
    with make_db() as (db, customer_without, _, _, _, _):
        history = customer_history_summary(db, customer_without.id)
        estimate = customer_replenishment_estimate(db, customer_without.id)

        assert history['orders'] == 0
        assert history['total_spent'] == Decimal('0')
        assert history['status'] == 'insufficient_data'
        assert estimate['status'] == 'insufficient_data'


def test_customer_with_multiple_orders_has_real_history_and_estimate():
    with make_db() as (db, _, customer_with, _, product_a, product_b):
        history = customer_history_summary(db, customer_with.id)
        estimate = customer_replenishment_estimate(db, customer_with.id)

        assert history['orders'] == 3
        assert history['first_purchase'].day == 1
        assert history['last_purchase'].day == 15
        assert history['total_spent'] == Decimal('260')
        assert history['average_ticket'] == Decimal('86.66666666666666666666666667')
        assert history['average_interval_days'] == 22 or history['average_interval_days'] == 22.5
        assert history['product_summary'][product_a.id]['quantity'] >= 1
        assert history['product_summary'][product_b.id]['quantity'] >= 1
        assert estimate['status'] == 'ready'
        assert estimate['physical_stock_observed'] is False
        assert estimate['product_estimates'][product_a.id]['product_id'] == product_a.id


def test_partner_uses_customer_orders_as_real_history():
    with make_db() as (db, _, customer_with, partner, _, _):
        partner_history = partner_history_summary(db, partner.id)
        partner_estimate = partner_replenishment_estimate(db, partner.id)

        assert partner_history['customer_id'] == customer_with.id
        assert partner_history['orders'] == 3
        assert partner_history['status'] == 'ready'
        assert partner_estimate['status'] == 'ready'
        assert partner_estimate['product_estimates']


def test_customer_history_is_isolated_by_customer_id():
    with make_db() as (db, customer_without, customer_with, _, _, _):
        no_history = customer_history_summary(db, customer_without.id)
        with_history = customer_history_summary(db, customer_with.id)

        assert no_history['orders'] == 0
        assert with_history['orders'] == 3
