from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.customers.schemas import CustomerCreate
from app.database.base import Base
from app.database.models import AccountPayable, AccountReceivable, CashMovement, InventoryBalance, InventoryMovement, Order, Product, Role, Supplier, User
from app.orders.schemas import OrderCreate, OrderStatusUpdate
from app.purchases.schemas import PurchaseCreate
from app.customers.router import create_customer
from app.orders.router import create_order
from app.purchases.router import create_purchase
from app.suppliers.router import create_supplier
from app.suppliers.schemas import SupplierCreate
from app.finance.router import cash_flow_summary, create_cash_movement, create_payable, create_receivable, refund_payable, refund_receivable, update_payable_status, update_receivable_status
from app.finance.schemas import AccountPayableCreate, AccountReceivableCreate
from app.orders.router import update_order_status


@pytest.fixture
def finance_database():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        role = Role(name='finance-test', is_system=True)
        product = Product(name='Mão de obra', unit='un', current_cost=Decimal('10'), current_price=Decimal('25'), minimum_stock=Decimal('0'))
        db.add_all([role, product])
        db.flush()
        actor = User(name='Finance User', email='finance@example.com', role_id=role.id, is_general_admin=True)
        db.add(actor)
        db.commit()
        yield db, actor, product
    engine.dispose()


def test_financial_records_are_created_for_purchase_and_order(finance_database):
    db, actor, product = finance_database
    supplier = create_supplier(SupplierCreate(name='Fornecedor Financeiro', location='Campinas, SP', product_ids=[product.id]), actor, db)
    customer = create_customer(CustomerCreate(name='Cliente Financeiro', email='cliente.finance@example.com'), actor, db)

    purchase = create_purchase(
        PurchaseCreate(
            supplier_id=supplier['id'],
            purchased_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            products_value=Decimal('40'),
            freight=Decimal('5'),
            other_costs=Decimal('3'),
            total=Decimal('48'),
            items=[{'product_id': product.id, 'quantity': Decimal('2'), 'unit_cost': Decimal('20'), 'discount': Decimal('0'), 'description': 'Compra teste'}],
        ),
        actor,
        db,
    )

    order = create_order(
        OrderCreate(
            customer_id=customer['id'],
            ordered_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            status='CONFIRMED',
            source='INTERNAL',
            items=[{'product_id': product.id, 'quantity': Decimal('1')}],
        ),
        actor,
        db,
    )

    payable = db.scalar(select(AccountPayable).where(AccountPayable.reference_id == purchase['id']))
    receivable = db.scalar(select(AccountReceivable).where(AccountReceivable.reference_id == order['id']))

    assert payable is not None
    assert payable.amount == Decimal('48')
    assert payable.status == 'PENDING'
    assert receivable is not None
    assert receivable.amount == Decimal('25')
    assert receivable.status == 'PENDING'


def test_cash_flow_summary_counts_real_entries_and_exits(finance_database):
    db, actor, _ = finance_database
    create_payable('Teste de despesa', Decimal('120'), 'Fornecedor', actor, db)
    create_receivable('Teste de receita', Decimal('180'), 'Cliente', actor, db)
    create_cash_movement('ENTRY', Decimal('180'), 'receipt', 'RECEBIMENTO', actor, db, notes='Recebimento do cliente')
    create_cash_movement('EXIT', Decimal('120'), 'payment', 'PAGAMENTO', actor, db, notes='Pagamento ao fornecedor')

    summary = cash_flow_summary(db, start=None, end=None)

    assert summary['cash_balance'] == Decimal('60')
    assert summary['entries_total'] == Decimal('180')
    assert summary['exits_total'] == Decimal('120')
    assert db.scalar(select(func.count(CashMovement.id))) == 2


def test_title_settlement_and_refund_create_idempotent_cash_movements(finance_database):
    db, actor, product = finance_database
    supplier = create_supplier(SupplierCreate(name='Fornecedor Liquidação', location='Campinas, SP', product_ids=[product.id]), actor, db)
    customer = create_customer(CustomerCreate(name='Cliente Liquidação', email='liquidacao@example.com'), actor, db)
    payable = create_payable(
        AccountPayableCreate(supplier_id=supplier['id'], description='Título pagar', amount=Decimal('70'), due_at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
        actor=actor,
        db=db,
    )
    receivable = create_receivable(
        AccountReceivableCreate(customer_id=customer['id'], description='Título receber', amount=Decimal('70'), due_at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
        actor=actor,
        db=db,
    )

    update_payable_status(payable.id, 'PAID', actor, db)
    update_payable_status(payable.id, 'PAID', actor, db)
    update_receivable_status(receivable.id, 'RECEIVED', actor, db)
    update_receivable_status(receivable.id, 'RECEIVED', actor, db)

    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.payable_id == payable.id)) == 1
    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.receivable_id == receivable.id)) == 1

    refund_payable(payable.id, actor, db)
    refund_payable(payable.id, actor, db)
    refund_receivable(receivable.id, actor, db)
    refund_receivable(receivable.id, actor, db)

    assert db.get(AccountPayable, payable.id).status == 'CANCELLED'
    assert db.get(AccountPayable, payable.id).refunded_at is not None
    assert db.get(AccountReceivable, receivable.id).status == 'CANCELLED'
    assert db.get(AccountReceivable, receivable.id).refunded_at is not None
    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.payable_id == payable.id)) == 2
    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.receivable_id == receivable.id)) == 2
    assert cash_flow_summary(db)['cash_balance'] == Decimal('0')


def test_received_order_requires_refund_before_cancellation(finance_database):
    db, actor, product = finance_database
    customer = create_customer(CustomerCreate(name='Cliente Reembolso', email='refund-order@example.com'), actor, db)
    db.add(InventoryBalance(product_id=product.id, quantity=Decimal('5')))
    db.commit()
    order = create_order(
        OrderCreate(
            customer_id=customer['id'],
            ordered_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
            status='CONFIRMED',
            items=[{'product_id': product.id, 'quantity': Decimal('2')}],
        ),
        actor,
        db,
    )
    receivable = db.scalar(select(AccountReceivable).where(AccountReceivable.reference_id == order['id']))
    update_receivable_status(receivable.id, 'RECEIVED', actor, db)

    with pytest.raises(HTTPException, match='Refund the received amount'):
        update_order_status(order['id'], OrderStatusUpdate(status='CANCELLED'), actor, db)
    assert db.get(Order, order['id']).status == 'CONFIRMED'
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id)) == Decimal('3.000')
    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.receivable_id == receivable.id)) == 1

    refund_receivable(receivable.id, actor, db)
    update_order_status(order['id'], OrderStatusUpdate(status='CANCELLED'), actor, db)

    assert db.get(Order, order['id']).status == 'CANCELLED'
    assert db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id)) == Decimal('5.000')
    assert db.scalar(select(func.count(CashMovement.id)).where(CashMovement.receivable_id == receivable.id)) == 2
    assert db.scalar(select(func.count(InventoryMovement.id)).where(InventoryMovement.order_id == order['id'])) == 2
