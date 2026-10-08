from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import (
    AccountPayable,
    AccountReceivable,
    CashMovement,
    Customer,
    FinancialCategory,
    Supplier,
    User,
)
from app.database.session import get_db
from app.database.idempotency import lock_idempotency_key
from app.finance.schemas import (
    AccountPayableCreate,
    AccountPayableRecord,
    AccountReceivableCreate,
    AccountReceivableRecord,
    CashMovementCreate,
    CashMovementRecord,
    FinancialCategoryInput,
    FinancialCategoryRecord,
)

router = APIRouter(prefix='/finance', tags=['finance'])


def _add_settlement_movement(db: Session, actor: User, movement_type: str, amount: Decimal, origin: str, reference_id: str, settlement_key: str, *, payable_id: str | None = None, receivable_id: str | None = None, notes: str | None = None) -> CashMovement:
    existing = db.scalar(select(CashMovement).where(CashMovement.settlement_key == settlement_key))
    if existing:
        return existing
    movement = CashMovement(
        movement_type=movement_type,
        amount=amount,
        origin=origin,
        reference_id=reference_id,
        payable_id=payable_id,
        receivable_id=receivable_id,
        settlement_key=settlement_key,
        notes=notes,
        created_by=actor.id,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(movement)
    db.flush()
    audit(db, actor.id, 'finance.settlement.cash_movement', 'cash_movement', movement.id, {'type': movement_type, 'amount': str(amount), 'reference_id': reference_id, 'settlement_key': settlement_key})
    return movement


def cash_flow_summary(db: Session, start: datetime | None = None, end: datetime | None = None) -> dict:
    entries_filter = [CashMovement.movement_type == 'ENTRY']
    exits_filter = [CashMovement.movement_type == 'EXIT']
    if start is not None:
        entries_filter.append(CashMovement.occurred_at >= start)
        exits_filter.append(CashMovement.occurred_at >= start)
    if end is not None:
        entries_filter.append(CashMovement.occurred_at <= end)
        exits_filter.append(CashMovement.occurred_at <= end)

    entries_total = db.scalar(select(func.coalesce(func.sum(CashMovement.amount), Decimal('0'))).where(*entries_filter)) or Decimal('0')
    exits_total = db.scalar(select(func.coalesce(func.sum(CashMovement.amount), Decimal('0'))).where(*exits_filter)) or Decimal('0')
    pending_payables = db.scalar(select(func.coalesce(func.sum(AccountPayable.amount), Decimal('0'))).where(AccountPayable.status == 'PENDING')) or Decimal('0')
    pending_receivables = db.scalar(select(func.coalesce(func.sum(AccountReceivable.amount), Decimal('0'))).where(AccountReceivable.status == 'PENDING')) or Decimal('0')
    return {
        'cash_balance': entries_total - exits_total,
        'entries_total': entries_total,
        'exits_total': exits_total,
        'pending_receivables': pending_receivables,
        'pending_payables': pending_payables,
    }


def create_payable(description: str | AccountPayableCreate | None = None, amount: Decimal | None = None, counterpart: str | None = None, actor: User | None = None, db: Session | None = None, **kwargs) -> AccountPayable:
    if not actor or db is None:
        raise ValueError('actor and db are required to create a payable.')
    if isinstance(description, AccountPayableCreate):
        prepared = description
    elif isinstance(description, str):
        supplier_name = counterpart or kwargs.get('supplier_name') or 'Fornecedor manual'
        supplier = db.scalar(select(Supplier).where(Supplier.name == supplier_name))
        if supplier is None:
            supplier = Supplier(name=supplier_name, location='Manual', is_active=True)
            db.add(supplier)
            db.flush()
        prepared = AccountPayableCreate(
            supplier_id=supplier.id,
            description=description,
            amount=amount or Decimal('0'),
            due_at=kwargs.get('due_at') or datetime.now(timezone.utc),
            category_id=kwargs.get('category_id'),
            payment_method=kwargs.get('payment_method'),
            reference_id=kwargs.get('reference_id'),
            notes=kwargs.get('notes'),
            status=kwargs.get('status', 'PENDING'),
        )
    else:
        raise HTTPException(status_code=422, detail='Payable payload is required.')

    supplier = db.get(Supplier, prepared.supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail='Supplier not found.')
    if prepared.status not in {'PENDING', 'OVERDUE'}:
        raise HTTPException(status_code=422, detail='A payable must be settled through its status transition.')
    if prepared.reference_id:
        lock_idempotency_key(db, 'payable', prepared.reference_id)
        existing = db.scalar(select(AccountPayable).where(AccountPayable.reference_id == prepared.reference_id))
        if existing:
            if existing.supplier_id != supplier.id or existing.amount != prepared.amount:
                raise HTTPException(status_code=409, detail='Reference ID is already linked to a different payable.')
            return existing
    payable = AccountPayable(
        supplier_id=supplier.id,
        description=prepared.description,
        category_id=prepared.category_id,
        amount=prepared.amount,
        due_at=prepared.due_at,
        status=prepared.status,
        payment_method=prepared.payment_method,
        reference_id=prepared.reference_id,
        notes=prepared.notes,
        created_by=actor.id,
    )
    db.add(payable)
    db.flush()
    audit(db, actor.id, 'finance.payable.create', 'account_payable', payable.id, {'supplier_id': supplier.id, 'amount': str(prepared.amount)})
    db.commit()
    db.refresh(payable)
    return payable


def create_receivable(description: str | AccountReceivableCreate | None = None, amount: Decimal | None = None, counterpart: str | None = None, actor: User | None = None, db: Session | None = None, **kwargs) -> AccountReceivable:
    if not actor or db is None:
        raise ValueError('actor and db are required to create a receivable.')
    if isinstance(description, AccountReceivableCreate):
        prepared = description
    elif isinstance(description, str):
        customer_name = counterpart or kwargs.get('customer_name') or 'Cliente manual'
        customer = db.scalar(select(Customer).where(Customer.name == customer_name))
        if customer is None:
            customer = Customer(name=customer_name, email=kwargs.get('email'), phone=kwargs.get('phone'), origin='INTERNAL', status='ACTIVE', created_by=actor.id)
            db.add(customer)
            db.flush()
        prepared = AccountReceivableCreate(
            customer_id=customer.id,
            description=description,
            amount=amount or Decimal('0'),
            due_at=kwargs.get('due_at') or datetime.now(timezone.utc),
            category_id=kwargs.get('category_id'),
            payment_method=kwargs.get('payment_method'),
            reference_id=kwargs.get('reference_id'),
            notes=kwargs.get('notes'),
            status=kwargs.get('status', 'PENDING'),
        )
    else:
        raise HTTPException(status_code=422, detail='Receivable payload is required.')

    customer = db.get(Customer, prepared.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found.')
    if prepared.status not in {'PENDING', 'OVERDUE'}:
        raise HTTPException(status_code=422, detail='A receivable must be settled through its status transition.')
    if prepared.reference_id:
        lock_idempotency_key(db, 'receivable', prepared.reference_id)
        existing = db.scalar(select(AccountReceivable).where(AccountReceivable.reference_id == prepared.reference_id))
        if existing:
            if existing.customer_id != customer.id or existing.amount != prepared.amount:
                raise HTTPException(status_code=409, detail='Reference ID is already linked to a different receivable.')
            return existing
    receivable = AccountReceivable(
        customer_id=customer.id,
        description=prepared.description,
        category_id=prepared.category_id,
        amount=prepared.amount,
        due_at=prepared.due_at,
        status=prepared.status,
        payment_method=prepared.payment_method,
        reference_id=prepared.reference_id,
        notes=prepared.notes,
        created_by=actor.id,
    )
    db.add(receivable)
    db.flush()
    audit(db, actor.id, 'finance.receivable.create', 'account_receivable', receivable.id, {'customer_id': customer.id, 'amount': str(prepared.amount)})
    db.commit()
    db.refresh(receivable)
    return receivable


def create_cash_movement(movement_type: str | CashMovementCreate | None = None, amount: Decimal | None = None, origin: str | None = None, reference_id: str | None = None, actor: User | None = None, db: Session | None = None, **kwargs) -> CashMovement:
    if not actor or db is None:
        raise ValueError('actor and db are required to create a cash movement.')
    if isinstance(movement_type, CashMovementCreate):
        prepared = movement_type
    else:
        prepared = CashMovementCreate(
            movement_type=movement_type or 'ENTRY',
            amount=amount or Decimal('0'),
            origin=origin or kwargs.get('origin') or 'MANUAL',
            reference_id=reference_id or kwargs.get('reference_id'),
            notes=kwargs.get('notes'),
            category_id=kwargs.get('category_id'),
            occurred_at=kwargs.get('occurred_at'),
        )
    movement_type_value = prepared.movement_type.upper() if prepared.movement_type else 'ENTRY'
    if movement_type_value not in {'ENTRY', 'EXIT'}:
        raise HTTPException(status_code=422, detail='Movement type must be ENTRY or EXIT.')
    movement = CashMovement(
        movement_type=movement_type_value,
        amount=prepared.amount,
        category_id=prepared.category_id,
        origin=prepared.origin,
        reference_id=prepared.reference_id,
        notes=prepared.notes,
        occurred_at=prepared.occurred_at or datetime.now(timezone.utc),
        created_by=actor.id,
    )
    db.add(movement)
    db.flush()
    audit(db, actor.id, 'finance.cash_movement.create', 'cash_movement', movement.id, {'type': movement.movement_type, 'amount': str(prepared.amount)})
    db.commit()
    db.refresh(movement)
    return movement


@router.get('/categories', response_model=list[FinancialCategoryRecord])
def list_categories(_: User = Depends(require_permission('finance:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(FinancialCategory).where(FinancialCategory.is_active.is_(True)).order_by(FinancialCategory.name)))


@router.post('/categories', response_model=FinancialCategoryRecord, status_code=status.HTTP_201_CREATED)
def create_category_route(payload: FinancialCategoryInput, actor: User = Depends(require_permission('finance:write')), db: Session = Depends(get_db)):
    category = FinancialCategory(name=payload.name.strip(), kind=payload.kind.upper(), created_by=actor.id)
    db.add(category)
    db.flush()
    audit(db, actor.id, 'finance.category.create', 'financial_category', category.id, {'kind': category.kind})
    db.commit()
    db.refresh(category)
    return category


@router.get('/payables', response_model=list[AccountPayableRecord])
def list_payables(_: User = Depends(require_permission('finance:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(AccountPayable).order_by(AccountPayable.due_at.asc())))


@router.post('/payables', response_model=AccountPayableRecord, status_code=status.HTTP_201_CREATED)
def payables_create(
    payload: AccountPayableCreate | None = None,
    actor: User = Depends(require_permission('finance:write')),
    db: Session = Depends(get_db),
):
    if payload is None:
        raise HTTPException(status_code=422, detail='Payable payload is required.')
    return create_payable(payload, actor=actor, db=db)


@router.patch('/payables/{payable_id}', response_model=AccountPayableRecord)
def update_payable_status(payable_id: str, status_value: str = Query(..., alias='status'), actor: User = Depends(require_permission('finance:write')), db: Session = Depends(get_db)):
    payable = db.scalar(select(AccountPayable).where(AccountPayable.id == payable_id).with_for_update())
    if not payable:
        raise HTTPException(status_code=404, detail='Payable not found.')
    if status_value not in {'PENDING', 'OVERDUE', 'PAID', 'CANCELLED'}:
        raise HTTPException(status_code=422, detail='Invalid payable status.')
    previous = payable.status
    allowed = {'PENDING': {'PENDING', 'OVERDUE', 'PAID', 'CANCELLED'}, 'OVERDUE': {'PENDING', 'OVERDUE', 'PAID', 'CANCELLED'}, 'PAID': {'PAID'}, 'CANCELLED': {'CANCELLED'}}
    if status_value not in allowed.get(previous, set()):
        raise HTTPException(status_code=409, detail=f'Cannot change payable from {previous} to {status_value}.')
    if previous == status_value:
        return payable
    payable.status = status_value
    if status_value == 'PAID':
        payable.paid_at = datetime.now(timezone.utc)
        _add_settlement_movement(db, actor, 'EXIT', payable.amount, 'PAYABLE_SETTLEMENT', payable.id, f'payable:{payable.id}:settlement', payable_id=payable.id, notes=payable.description)
    elif status_value != 'CANCELLED':
        payable.paid_at = None
    audit(db, actor.id, 'finance.payable.update', 'account_payable', payable.id, {'from': previous, 'to': status_value})
    db.commit()
    db.refresh(payable)
    return payable


@router.post('/payables/{payable_id}/refund', response_model=AccountPayableRecord)
def refund_payable(payable_id: str, actor: User = Depends(require_permission('finance:write')), db: Session = Depends(get_db)):
    payable = db.scalar(select(AccountPayable).where(AccountPayable.id == payable_id).with_for_update())
    if not payable:
        raise HTTPException(status_code=404, detail='Payable not found.')
    if payable.refunded_at:
        return payable
    if payable.status != 'PAID':
        raise HTTPException(status_code=409, detail='Only a paid payable can be refunded.')
    movement = _add_settlement_movement(db, actor, 'ENTRY', payable.amount, 'PAYABLE_REFUND', payable.id, f'payable:{payable.id}:refund', payable_id=payable.id, notes=payable.description)
    payable.status = 'CANCELLED'
    payable.refunded_at = datetime.now(timezone.utc)
    audit(db, actor.id, 'finance.payable.refund', 'account_payable', payable.id, {'from': 'PAID', 'to': 'CANCELLED', 'cash_movement_id': movement.id})
    db.commit()
    db.refresh(payable)
    return payable


@router.get('/receivables', response_model=list[AccountReceivableRecord])
def list_receivables(_: User = Depends(require_permission('finance:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(AccountReceivable).order_by(AccountReceivable.due_at.asc())))


@router.post('/receivables', response_model=AccountReceivableRecord, status_code=status.HTTP_201_CREATED)
def receivables_create(
    payload: AccountReceivableCreate | None = None,
    actor: User = Depends(require_permission('finance:write')),
    db: Session = Depends(get_db),
):
    if payload is None:
        raise HTTPException(status_code=422, detail='Receivable payload is required.')
    return create_receivable(payload, actor=actor, db=db)


@router.patch('/receivables/{receivable_id}', response_model=AccountReceivableRecord)
def update_receivable_status(receivable_id: str, status_value: str = Query(..., alias='status'), actor: User = Depends(require_permission('finance:write')), db: Session = Depends(get_db)):
    receivable = db.scalar(select(AccountReceivable).where(AccountReceivable.id == receivable_id).with_for_update())
    if not receivable:
        raise HTTPException(status_code=404, detail='Receivable not found.')
    if status_value not in {'PENDING', 'OVERDUE', 'RECEIVED', 'CANCELLED'}:
        raise HTTPException(status_code=422, detail='Invalid receivable status.')
    previous = receivable.status
    allowed = {'PENDING': {'PENDING', 'OVERDUE', 'RECEIVED', 'CANCELLED'}, 'OVERDUE': {'PENDING', 'OVERDUE', 'RECEIVED', 'CANCELLED'}, 'RECEIVED': {'RECEIVED'}, 'CANCELLED': {'CANCELLED'}}
    if status_value not in allowed.get(previous, set()):
        raise HTTPException(status_code=409, detail=f'Cannot change receivable from {previous} to {status_value}.')
    if previous == status_value:
        return receivable
    receivable.status = status_value
    if status_value == 'RECEIVED':
        receivable.received_at = datetime.now(timezone.utc)
        _add_settlement_movement(db, actor, 'ENTRY', receivable.amount, 'RECEIVABLE_SETTLEMENT', receivable.id, f'receivable:{receivable.id}:settlement', receivable_id=receivable.id, notes=receivable.description)
    elif status_value != 'CANCELLED':
        receivable.received_at = None
    audit(db, actor.id, 'finance.receivable.update', 'account_receivable', receivable.id, {'from': previous, 'to': status_value})
    db.commit()
    db.refresh(receivable)
    return receivable


@router.post('/receivables/{receivable_id}/refund', response_model=AccountReceivableRecord)
def refund_receivable(receivable_id: str, actor: User = Depends(require_permission('finance:write')), db: Session = Depends(get_db)):
    receivable = db.scalar(select(AccountReceivable).where(AccountReceivable.id == receivable_id).with_for_update())
    if not receivable:
        raise HTTPException(status_code=404, detail='Receivable not found.')
    if receivable.refunded_at:
        return receivable
    if receivable.status != 'RECEIVED':
        raise HTTPException(status_code=409, detail='Only a received receivable can be refunded.')
    movement = _add_settlement_movement(db, actor, 'EXIT', receivable.amount, 'RECEIVABLE_REFUND', receivable.id, f'receivable:{receivable.id}:refund', receivable_id=receivable.id, notes=receivable.description)
    receivable.status = 'CANCELLED'
    receivable.refunded_at = datetime.now(timezone.utc)
    audit(db, actor.id, 'finance.receivable.refund', 'account_receivable', receivable.id, {'from': 'RECEIVED', 'to': 'CANCELLED', 'cash_movement_id': movement.id})
    db.commit()
    db.refresh(receivable)
    return receivable


@router.get('/movements', response_model=list[CashMovementRecord])
def list_movements(_: User = Depends(require_permission('finance:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(CashMovement).order_by(CashMovement.occurred_at.desc())))


@router.post('/movements', response_model=CashMovementRecord, status_code=status.HTTP_201_CREATED)
def movements_create(
    payload: CashMovementCreate | None = None,
    actor: User = Depends(require_permission('finance:write')),
    db: Session = Depends(get_db),
):
    if payload is None:
        raise HTTPException(status_code=422, detail='Cash movement payload is required.')
    return create_cash_movement(payload, actor=actor, db=db)


@router.get('/summary')
def summary(start: datetime | None = Query(default=None), end: datetime | None = Query(default=None), _: User = Depends(require_permission('finance:read')), db: Session = Depends(get_db)):
    return cash_flow_summary(db, start=start, end=end)
