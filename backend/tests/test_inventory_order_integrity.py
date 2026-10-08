from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.customers.router import create_customer
from app.customers.schemas import CustomerCreate
from app.database.base import Base
from app.database.models import Customer, InventoryBalance, InventoryMovement, Product, Role, User
from app.inventory.router import adjust
from app.inventory.schemas import InventoryAdjustment
from app.orders.router import create_order, update_order_status
from app.orders.schemas import OrderCreate, OrderStatusUpdate


@pytest.fixture
def inventory_order_database():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='inventory-order-test', is_system=True)
        product = Product(name='Produto de estoque', unit='un', current_cost=Decimal('10'), current_price=Decimal('25'), minimum_stock=Decimal('2'))
        db.add_all([role, product])
        db.flush()
        actor = User(name='Inventory User', email='inventory@example.com', role_id=role.id, is_general_admin=True)
        db.add(actor)
        db.flush()
        customer = Customer(name='Cliente Teste', email='cliente.teste@example.com', origin='INTERNAL', status='ACTIVE')
        db.add(customer)
        db.commit()
        db.add(InventoryBalance(product_id=product.id, quantity=Decimal('5')))
        db.commit()
        yield db, actor, product, customer
    engine.dispose()


def test_inventory_adjustment_records_reason_notes_and_respects_negative_policy(inventory_order_database):
    db, actor, product, _ = inventory_order_database

    result = adjust(
        InventoryAdjustment(
            product_id=product.id,
            quantity_delta=Decimal('-2'),
            movement_type='LOSS',
            reason='Quebra de embalagem',
            notes='Perda registrada na seleção',
            occurred_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        ),
        actor,
        db,
    )

    movement = db.scalar(select(InventoryMovement).where(InventoryMovement.product_id == product.id).order_by(InventoryMovement.occurred_at.desc()))
    assert result['quantity'] == Decimal('3')
    assert movement is not None
    assert movement.movement_type == 'LOSS'
    assert movement.reason == 'Quebra de embalagem'
    assert movement.notes == 'Perda registrada na seleção'

    with pytest.raises(HTTPException, match='negative'):
        adjust(
            InventoryAdjustment(
                product_id=product.id,
                quantity_delta=Decimal('-10'),
                movement_type='LOSS',
                reason='Estoque insuficiente',
            ),
            actor,
            db,
        )


def test_order_status_must_follow_valid_transitions(inventory_order_database):
    db, actor, product, customer = inventory_order_database

    with pytest.raises(HTTPException, match='Invalid order status transition'):
        create_order(
            OrderCreate(
                customer_id=customer.id,
                ordered_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
                status='DELIVERED',
                source='INTERNAL',
                items=[{'product_id': product.id, 'quantity': Decimal('1')}],
            ),
            actor,
            db,
        )


def test_order_cancellation_is_idempotent_and_does_not_duplicate_reversal(inventory_order_database):
    db, actor, product, customer = inventory_order_database

    order = create_order(
        OrderCreate(
            customer_id=customer.id,
            ordered_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
            status='CONFIRMED',
            source='INTERNAL',
            items=[{'product_id': product.id, 'quantity': Decimal('2')}],
        ),
        actor,
        db,
    )

    update_order_status(order['id'], OrderStatusUpdate(status='CANCELLED'), actor, db)
    update_order_status(order['id'], OrderStatusUpdate(status='CANCELLED'), actor, db)

    cancellation_movements = db.scalars(
        select(InventoryMovement).where(
            InventoryMovement.order_id == order['id'],
            InventoryMovement.reason == 'ORDER_CANCELLATION',
        )
    ).all()
    assert len(cancellation_movements) == 1

    balance = db.scalar(select(InventoryBalance).where(InventoryBalance.product_id == product.id))
    assert balance.quantity == Decimal('5')
