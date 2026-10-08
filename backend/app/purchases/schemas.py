from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class PurchaseItemInput(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal('0'), ge=0)
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode='after')
    def discount_does_not_exceed_line_value(self):
        if self.discount > self.quantity * self.unit_cost:
            raise ValueError('Item discount cannot exceed its gross value.')
        return self


class PurchaseCreate(BaseModel):
    supplier_id: str
    purchased_at: datetime
    idempotency_key: str | None = Field(default=None, max_length=120)
    document_number: str | None = Field(default=None, max_length=100)
    observations: str | None = Field(default=None, max_length=2000)
    freight: Decimal = Field(default=Decimal('0'), ge=0)
    other_costs: Decimal = Field(default=Decimal('0'), ge=0)
    items: list[PurchaseItemInput] = Field(min_length=1)


class PurchaseItemRecord(BaseModel):
    id: str
    product_id: str
    quantity: Decimal
    unit_cost: Decimal
    discount: Decimal
    description: str | None
    freight_share: Decimal
    other_cost_share: Decimal
    real_unit_cost: Decimal

    model_config = {'from_attributes': True}


class PurchaseRecord(BaseModel):
    id: str
    supplier_id: str
    purchased_at: datetime
    document_number: str | None = None
    observations: str | None = None
    products_value: Decimal
    discount_total: Decimal = Decimal('0')
    freight: Decimal
    other_costs: Decimal
    total: Decimal
    status: str
    items: list[PurchaseItemRecord] = []

    model_config = {'from_attributes': True}
