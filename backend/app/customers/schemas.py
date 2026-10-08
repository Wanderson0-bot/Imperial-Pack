from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


class AddressInput(BaseModel):
    label: str = 'Principal'
    street: str | None = Field(default=None, min_length=2, max_length=200)
    number: str | None = Field(default=None, max_length=30)
    complement: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state: str | None = Field(default=None, max_length=2)
    postal_code: str | None = None


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    establishment: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    city: str | None = None
    notes: str | None = None
    origin: str = 'INTERNAL'
    status: str = 'ACTIVE'
    external_id: str | None = Field(default=None, max_length=120)
    address: AddressInput | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    establishment: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    city: str | None = None
    notes: str | None = None
    status: str | None = None
    external_id: str | None = Field(default=None, max_length=120)
    address: AddressInput | None = None


class AddressRecord(AddressInput):
    id: str

    model_config = {'from_attributes': True}


class CustomerRecord(BaseModel):
    id: str
    name: str
    establishment: str | None
    email: str | None
    phone: str | None
    city: str | None
    notes: str | None
    origin: str
    status: str
    external_id: str | None = None
    address: AddressRecord | None = None
    orders: int | None = None
    total_spent: Decimal | None = None
    average_ticket: Decimal | None = None
    last_purchase: datetime | None = None

    model_config = {'from_attributes': True}
