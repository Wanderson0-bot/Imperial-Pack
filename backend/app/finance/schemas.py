from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FinancialCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default='GENERAL', min_length=1, max_length=20)


class AccountPayableCreate(BaseModel):
    supplier_id: str
    description: str = Field(min_length=1, max_length=180)
    amount: Decimal = Field(ge=0)
    due_at: datetime
    category_id: str | None = None
    payment_method: str | None = None
    reference_id: str | None = None
    notes: str | None = None
    status: str = 'PENDING'


class AccountReceivableCreate(BaseModel):
    customer_id: str
    description: str = Field(min_length=1, max_length=180)
    amount: Decimal = Field(ge=0)
    due_at: datetime
    category_id: str | None = None
    payment_method: str | None = None
    reference_id: str | None = None
    notes: str | None = None
    status: str = 'PENDING'


class CashMovementCreate(BaseModel):
    movement_type: str = Field(min_length=3, max_length=10)
    amount: Decimal = Field(ge=0)
    origin: str = Field(min_length=1, max_length=30)
    category_id: str | None = None
    reference_id: str | None = None
    notes: str | None = None
    occurred_at: datetime | None = None


class FinancialCategoryRecord(FinancialCategoryInput):
    id: str
    is_active: bool

    model_config = {'from_attributes': True}


class AccountPayableRecord(AccountPayableCreate):
    id: str
    paid_at: datetime | None = None
    refunded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class AccountReceivableRecord(AccountReceivableCreate):
    id: str
    received_at: datetime | None = None
    refunded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class CashMovementRecord(CashMovementCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}
