from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class PartnerCreate(BaseModel):
    customer_id: str


class ConditionsInput(BaseModel):
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    payment_method: str | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class CycleInput(BaseModel):
    cycle_type: str
    custom_days: int | None = Field(default=None, ge=1, le=365)


class ConsumptionRecord(BaseModel):
    id: str
    partner_id: str
    customer_id: str
    product_id: str
    order_id: str
    quantity: Decimal
    purchased_at: datetime
    unit_price: Decimal
    unit_cost: Decimal | None
    source: str
    interval_since_previous_days: int | None

    model_config = {'from_attributes': True}


class PredictionEvaluationInput(BaseModel):
    actual_value: Decimal | None = None
    actual_at: datetime | None = None
