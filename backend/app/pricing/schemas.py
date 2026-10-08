from decimal import Decimal
from pydantic import BaseModel, Field


class PriceApproval(BaseModel):
    product_id: str
    new_price: Decimal = Field(gt=0)


class PricingReview(BaseModel):
    product_id: str
    product_name: str
    cost: Decimal
    current_price: Decimal
    suggested_price: Decimal
    minimum_price: Decimal
    maximum_price: Decimal
    margin_percent: Decimal
    markup_percent: Decimal
