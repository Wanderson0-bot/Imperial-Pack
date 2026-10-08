from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class InventoryAdjustment(BaseModel):
    product_id: str
    quantity_delta: Decimal
    movement_type: str = 'ADJUSTMENT'
    reason: str = Field(min_length=3, max_length=180)
    notes: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None

    @property
    def normalized_movement_type(self) -> str:
        value = (self.movement_type or 'ADJUSTMENT').upper()
        allowed = {'IN', 'OUT', 'ADJUSTMENT', 'LOSS', 'DAMAGE', 'RETURN', 'REVERSAL'}
        if value not in allowed:
            raise ValueError('Unsupported inventory movement type.')
        return value


class InventoryMovementRecord(BaseModel):
    id: str
    product_id: str
    movement_type: str
    quantity: Decimal
    occurred_at: datetime
    reason: str
    notes: str | None = None
    purchase_id: str | None
    order_id: str | None

    model_config = {'from_attributes': True}
