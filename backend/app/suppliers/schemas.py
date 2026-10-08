from decimal import Decimal
from pydantic import BaseModel, Field


class SupplierInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    email: str | None = None
    phone: str | None = None
    location: str | None = Field(default=None, max_length=240)
    minimum_order: Decimal | None = Field(default=None, ge=0)
    delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None


class SupplierCreate(SupplierInput):
    location: str = Field(min_length=2, max_length=240)
    product_ids: list[str] = Field(default_factory=list)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    email: str | None = None
    phone: str | None = None
    location: str | None = Field(default=None, min_length=2, max_length=240)
    minimum_order: Decimal | None = Field(default=None, ge=0)
    delivery_days: int | None = Field(default=None, ge=0)
    notes: str | None = None
    product_ids: list[str] | None = None


class SupplierRecord(SupplierInput):
    id: str
    is_active: bool
    product_ids: list[str] = []

    model_config = {'from_attributes': True}
