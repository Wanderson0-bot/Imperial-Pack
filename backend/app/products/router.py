from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission, user_permission_keys
from app.core.audit import audit
from app.database.models import InventoryBalance, Product, ProductCategory, User
from app.database.session import get_db
from app.products.schemas import CategoryInput, ProductCreate, ProductRecord, ProductUpdate
from app.pricing.calculations import margin, markup, minimum_price, maximum_price

router = APIRouter(prefix='/products', tags=['products'])


@router.get('/categories')
def list_categories(_: User = Depends(require_permission('products:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(ProductCategory).order_by(ProductCategory.name)))


@router.post('/categories', status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryInput, actor: User = Depends(require_permission('products:create')), db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail='Category name is required.')
    if db.scalar(select(ProductCategory.id).where(ProductCategory.name == name)):
        raise HTTPException(status_code=409, detail='Category already exists.')
    category = ProductCategory(name=name, image_url=payload.image_url)
    db.add(category)
    db.flush()
    audit(db, actor.id, 'products.category.create', 'product_category', category.id)
    db.commit()
    return {'id': category.id, 'name': category.name, 'image_url': category.image_url}


@router.patch('/categories/{category_id}')
def update_category(category_id: str, payload: CategoryInput, actor: User = Depends(require_permission('products:update')), db: Session = Depends(get_db)):
    category = db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found.')
    category.name = payload.name.strip()
    category.image_url = payload.image_url
    audit(db, actor.id, 'products.category.update', 'product_category', category.id)
    db.commit()
    return {'id': category.id, 'name': category.name, 'image_url': category.image_url}


@router.delete('/categories/{category_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, replacement_category_id: str | None = None, actor: User = Depends(require_permission('products:update')), db: Session = Depends(get_db)):
    category = db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail='Category not found.')
    products = list(db.scalars(select(Product).where(Product.category_id == category.id)))
    if products and not replacement_category_id:
        raise HTTPException(status_code=409, detail='Category has linked products; provide a replacement category.')
    replacement = db.get(ProductCategory, replacement_category_id) if replacement_category_id else None
    if products and not replacement:
        raise HTTPException(status_code=422, detail='Replacement category not found.')
    for product in products:
        product.category_id = replacement.id if replacement else None
    audit(db, actor.id, 'products.category.delete', 'product_category', category.id, {'replacement': replacement_category_id})
    db.delete(category)
    db.commit()


def serialize(product: Product, db: Session) -> ProductRecord:
    balance = db.scalar(select(InventoryBalance.quantity).where(InventoryBalance.product_id == product.id))
    stock = balance or Decimal('0')
    state = 'Sem estoque' if stock <= 0 else 'Crítico' if stock <= product.minimum_stock / 2 else 'Baixo' if stock <= product.minimum_stock else 'Normal'
    return ProductRecord(id=product.id, name=product.name, category_id=product.category_id, image_url=product.image_url, description=product.description, unit=product.unit, current_cost=product.current_cost, current_price=product.current_price, minimum_stock=product.minimum_stock, margin_percent=product.margin_percent, markup_percent=product.markup_percent, stock=stock, status=state)


@router.get('', response_model=list[ProductRecord])
def list_products(_: User = Depends(require_permission('products:read')), db: Session = Depends(get_db)):
    return [serialize(product, db) for product in db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name))]


@router.post('', response_model=ProductRecord, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, actor: User = Depends(require_permission('products:create')), db: Session = Depends(get_db)):
    if payload.category_id and not db.get(ProductCategory, payload.category_id):
        raise HTTPException(status_code=422, detail='Unknown product category.')
    product = Product(**payload.model_dump(), margin_percent=margin(payload.current_price, payload.current_cost), markup_percent=markup(payload.current_price, payload.current_cost))
    db.add(product)
    db.flush()
    db.add(InventoryBalance(product_id=product.id, quantity=0))
    audit(db, actor.id, 'products.create', 'product', product.id)
    db.commit()
    db.refresh(product)
    return serialize(product, db)


@router.patch('/{product_id}', response_model=ProductRecord)
def update_product(product_id: str, payload: ProductUpdate, actor: User = Depends(require_permission('products:update')), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    changes = payload.model_dump(exclude_unset=True)
    if changes.get('category_id') and not db.get(ProductCategory, changes['category_id']):
        raise HTTPException(status_code=422, detail='Unknown product category.')
    previous_price = product.current_price
    for key, value in changes.items():
        setattr(product, key, value)
    product.margin_percent = margin(product.current_price, product.current_cost)
    product.markup_percent = markup(product.current_price, product.current_cost)
    if 'current_price' in changes and changes['current_price'] != previous_price:
        if not actor.is_general_admin and 'pricing:approve' not in user_permission_keys(db, actor):
            raise HTTPException(status_code=403, detail='Pricing approval permission is required to change a product price.')
        if product.current_price < minimum_price(product.current_cost) or product.current_price > maximum_price(product.current_cost):
            raise HTTPException(status_code=422, detail='Price violates configured margin or markup limits.')
        from app.database.models import PricingHistory
        db.add(PricingHistory(product_id=product.id, previous_price=previous_price, new_price=product.current_price, cost_snapshot=product.current_cost, margin_percent=product.margin_percent, markup_percent=product.markup_percent, source='MANUAL_EDIT', changed_by=actor.id))
        audit(db, actor.id, 'pricing.manual_update', 'product', product.id, {'previous_price': str(previous_price), 'new_price': str(product.current_price)})
    else:
        audit(
            db,
            actor.id,
            'products.update',
            'product',
            product.id,
            {key: str(value) if isinstance(value, Decimal) else value for key, value in changes.items()},
        )
    db.commit()
    db.refresh(product)
    return serialize(product, db)


@router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(product_id: str, actor: User = Depends(require_permission('products:update')), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    product.is_active = False
    audit(db, actor.id, 'products.deactivate', 'product', product.id)
    db.commit()


@router.get('/{product_id}/cost-history')
def cost_history(product_id: str, _: User = Depends(require_permission('products:read')), db: Session = Depends(get_db)):
    from app.database.models import CostHistory, Purchase, Supplier
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail='Product not found.')
    entries = db.execute(select(CostHistory, Purchase, Supplier).outerjoin(Purchase, Purchase.id == CostHistory.purchase_id).outerjoin(Supplier, Supplier.id == Purchase.supplier_id).where(CostHistory.product_id == product_id).order_by(CostHistory.changed_at.desc()).limit(100))
    return [{'id': entry.id, 'product_id': entry.product_id, 'date': entry.changed_at, 'previous_cost': entry.previous_cost, 'new_cost': entry.new_cost, 'reason': 'Purchase', 'supplier': supplier.name if supplier else ''} for entry, purchase, supplier in entries]


@router.get('/{product_id}/price-history')
def price_history(product_id: str, _: User = Depends(require_permission('products:read')), db: Session = Depends(get_db)):
    from app.database.models import PricingHistory
    if not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail='Product not found.')
    entries = db.scalars(select(PricingHistory).where(PricingHistory.product_id == product_id).order_by(PricingHistory.changed_at.desc()).limit(100))
    return [{'id': entry.id, 'product_id': entry.product_id, 'date': entry.changed_at, 'previous_price': entry.previous_price, 'new_price': entry.new_price, 'reason': entry.source, 'margin': entry.margin_percent} for entry in entries]
