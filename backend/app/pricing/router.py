from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import PricingHistory, Product, User
from app.database.session import get_db
from app.pricing.calculations import MAX_MARKUP, MIN_MARGIN, STANDARD_MARGIN, commercial_round, margin, markup, maximum_price, minimum_price
from app.pricing.schemas import PriceApproval, PricingReview

router = APIRouter(prefix='/pricing', tags=['pricing'])
def review(product: Product) -> PricingReview:
    suggested = commercial_round(product.current_cost / (1 - STANDARD_MARGIN)) if product.current_cost else Decimal('0')
    minimum = minimum_price(product.current_cost)
    maximum = maximum_price(product.current_cost)
    return PricingReview(product_id=product.id, product_name=product.name, cost=product.current_cost, current_price=product.current_price, suggested_price=suggested, minimum_price=minimum.quantize(Decimal('0.01')), maximum_price=maximum.quantize(Decimal('0.01')), margin_percent=margin(product.current_price, product.current_cost), markup_percent=markup(product.current_price, product.current_cost))


def approve(product: Product, value: Decimal, actor: User, db: Session, source: str):
    if value < minimum_price(product.current_cost):
        raise HTTPException(status_code=422, detail='Price is below the configured minimum margin.')
    if value > maximum_price(product.current_cost):
        raise HTTPException(status_code=422, detail='Price exceeds the configured maximum markup.')
    previous = product.current_price
    product.current_price = value
    product.margin_percent = margin(value, product.current_cost)
    product.markup_percent = markup(value, product.current_cost)
    db.add(PricingHistory(product_id=product.id, previous_price=previous, new_price=value, cost_snapshot=product.current_cost, margin_percent=product.margin_percent, markup_percent=product.markup_percent, source=source, changed_by=actor.id))
    audit(db, actor.id, 'pricing.approve', 'product', product.id, {'previous': str(previous), 'new': str(value), 'source': source})


@router.get('/reviews', response_model=list[PricingReview])
def reviews(_: User = Depends(require_permission('pricing:read')), db: Session = Depends(get_db)):
    return [review(product) for product in db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name))]


@router.post('/recalculate', response_model=list[PricingReview])
def recalculate(_: User = Depends(require_permission('pricing:approve')), db: Session = Depends(get_db)):
    # Recalculation returns review rows; it does not modify any product prices.
    return [review(product) for product in db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name))]


@router.post('/products/{product_id}/recalculate', response_model=PricingReview)
def recalculate_product(product_id: str, _: User = Depends(require_permission('pricing:approve')), db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.id == product_id, Product.is_active.is_(True)))
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    return review(product)


@router.post('/approve', response_model=PricingReview)
def approve_one(payload: PriceApproval, actor: User = Depends(require_permission('pricing:approve')), db: Session = Depends(get_db)):
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    approve(product, payload.new_price, actor, db, 'APPROVED_SINGLE')
    db.commit()
    db.refresh(product)
    return review(product)


@router.post('/approve-all', response_model=list[PricingReview])
def approve_all(actor: User = Depends(require_permission('pricing:approve')), db: Session = Depends(get_db)):
    products = list(db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name)))
    for product in products:
        candidate = review(product).suggested_price
        approve(product, candidate, actor, db, 'APPROVED_BULK')
    db.commit()
    return [review(product) for product in products]
