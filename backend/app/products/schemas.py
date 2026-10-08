from decimal import Decimal
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    category_id: str | None = None
    image_url: str | None = None
    description: str | None = None
    unit: str = Field(min_length=1, max_length=30)
    current_cost: Decimal = Field(ge=0)
    current_price: Decimal = Field(ge=0)
    minimum_stock: Decimal = Field(ge=0)


class ProductRecord(ProductCreate):
    id: str
    margin_percent: Decimal
    markup_percent: Decimal
    stock: Decimal = Decimal('0')
    status: str


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: str | None = None
    image_url: str | None = None
    description: str | None = None
    unit: str | None = None
    current_price: Decimal | None = Field(default=None, ge=0)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    image_url: str | None = None
