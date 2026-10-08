from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.customers.router import list_customers
from app.database.base import Base
from app.database.models import Customer, Order


def test_customer_metrics_count_only_realized_orders():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        customer = Customer(name='Customer One', origin='INTERNAL', status='ACTIVE')
        db.add(customer)
        db.flush()
        db.add_all([
            Order(customer_id=customer.id, ordered_at=datetime(2026, 8, 31, tzinfo=timezone.utc), status='NEW', subtotal=Decimal('800'), total=Decimal('800')),
            Order(customer_id=customer.id, ordered_at=datetime(2026, 9, 1, tzinfo=timezone.utc), status='DELIVERED', subtotal=Decimal('100'), total=Decimal('100')),
            Order(customer_id=customer.id, ordered_at=datetime(2026, 9, 2, tzinfo=timezone.utc), status='CANCELLED', subtotal=Decimal('900'), total=Decimal('900')),
        ])
        db.commit()

        record = list_customers(None, None, db)[0]

    assert record['orders'] == 1
    assert record['total_spent'] == Decimal('100')
    assert record['average_ticket'] == Decimal('100')
    assert record['last_purchase'].day == 1
    engine.dispose()