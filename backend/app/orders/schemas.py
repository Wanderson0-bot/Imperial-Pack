from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class OrderItemInput(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: str
    ordered_at: datetime
    status: str = 'NEW'
    notes: str | None = None
    source: str = 'INTERNAL'
    external_id: str | None = Field(default=None, max_length=120)
    items: list[OrderItemInput] = Field(min_length=1)

    @model_validator(mode='after')
    def validate_order_lines(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError('Use a single order line per product.')
        if self.source not in {'INTERNAL', 'WHATSAPP', 'SALESPERSON', 'SITE_PUBLICO'}:
            raise ValueError('Unsupported order source.')
        return self


class OrderItemRecord(BaseModel):
    id: str
    product_id: str
    product_name_snapshot: str
    unit_price_snapshot: Decimal
    quantity: Decimal
    subtotal: Decimal

    model_config = {'from_attributes': True}


class OrderRecord(BaseModel):
    id: str
    customer_id: str
    ordered_at: datetime
    status: str
    subtotal: Decimal
    total: Decimal
    notes: str | None
    source: str
    external_id: str | None = None
    items: list[OrderItemRecord] = []

    model_config = {'from_attributes': True}


class OrderStatusUpdate(BaseModel):
    status: str
