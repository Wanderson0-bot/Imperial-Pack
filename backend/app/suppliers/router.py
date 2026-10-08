import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import Product, Purchase, PurchaseItem, Supplier, SupplierProduct, User
from app.database.session import get_db
from app.suppliers.schemas import SupplierCreate, SupplierRecord, SupplierUpdate

router = APIRouter(prefix='/suppliers', tags=['suppliers'])


def phone_key(value: str | None) -> str | None:
    digits = re.sub(r'\D', '', value or '')
    return digits or None


def ensure_unique(db: Session, name: str, email: str | None, phone: str | None, exclude_id: str | None = None) -> None:
    normalized_name = name.strip().casefold()
    if db.scalar(select(Supplier.id).where(func.lower(func.trim(Supplier.name)) == normalized_name, Supplier.id != (exclude_id or ''))):
        raise HTTPException(status_code=409, detail='Supplier name is already registered.')
    if email and db.scalar(select(Supplier.id).where(func.lower(Supplier.email) == email.strip().lower(), Supplier.id != (exclude_id or ''))):
        raise HTTPException(status_code=409, detail='Supplier email is already registered.')
    normalized_phone = phone_key(phone)
    if normalized_phone:
        for existing in db.scalars(select(Supplier).where(Supplier.id != (exclude_id or ''))):
            if phone_key(existing.phone) == normalized_phone:
                raise HTTPException(status_code=409, detail='Supplier phone is already registered.')


def validate_product_ids(db: Session, product_ids: list[str]) -> list[Product]:
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(status_code=422, detail='A product cannot be linked to a supplier more than once.')
    products = list(db.scalars(select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True)))) if product_ids else []
    if len(products) != len(product_ids):
        raise HTTPException(status_code=422, detail='One or more active products were not found.')
    return products


def supplier_record(supplier: Supplier, db: Session) -> dict:
    record = SupplierRecord.model_validate(supplier).model_dump()
    record['product_ids'] = list(db.scalars(select(SupplierProduct.product_id).where(SupplierProduct.supplier_id == supplier.id)))
    return record


@router.get('', response_model=list[SupplierRecord])
def list_suppliers(search: str | None = Query(default=None, min_length=1, max_length=100), _: User = Depends(require_permission('suppliers:read')), db: Session = Depends(get_db)):
    statement = select(Supplier)
    if search and search.strip():
        term = f'%{search.strip()}%'
        statement = statement.where(Supplier.name.ilike(term) | Supplier.email.ilike(term) | Supplier.phone.ilike(term) | Supplier.location.ilike(term))
    return [supplier_record(supplier, db) for supplier in db.scalars(statement.order_by(Supplier.name))]


@router.get('/{supplier_id}', response_model=SupplierRecord)
def get_supplier(supplier_id: str, _: User = Depends(require_permission('suppliers:read')), db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail='Supplier not found.')
    return supplier_record(supplier, db)


@router.get('/{supplier_id}/analysis')
def supplier_analysis(supplier_id: str, _: User = Depends(require_permission('suppliers:read')), db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail='Supplier not found.')
    latest = db.scalar(select(Purchase).where(Purchase.supplier_id == supplier.id).order_by(Purchase.purchased_at.desc()).limit(1))
    products = list(db.scalars(select(Product).join(SupplierProduct, SupplierProduct.product_id == Product.id).where(SupplierProduct.supplier_id == supplier.id).order_by(Product.name)))
    last_costs = db.scalars(select(PurchaseItem.real_unit_cost).join(Purchase, Purchase.id == PurchaseItem.purchase_id).where(Purchase.supplier_id == supplier.id).order_by(Purchase.purchased_at.desc()).limit(100))
    costs = list(last_costs)
    average = sum(costs) / len(costs) if costs else 0
    variation_percent = (float(costs[0] - average) / float(average) * 100) if costs and average else 0
    cost_rows = db.execute(select(PurchaseItem.product_id, Purchase.purchased_at, PurchaseItem.real_unit_cost).join(Purchase, Purchase.id == PurchaseItem.purchase_id).where(Purchase.supplier_id == supplier.id).order_by(Purchase.purchased_at.desc(), PurchaseItem.id.desc())).all()
    latest_by_product = {}
    for product_id, purchased_at, real_unit_cost in cost_rows:
        latest_by_product.setdefault(product_id, {'last_cost': float(real_unit_cost), 'last_purchase': purchased_at.date().isoformat()})
    product_details = [{'id': product.id, 'name': product.name, **latest_by_product.get(product.id, {'last_cost': None, 'last_purchase': None})} for product in products]
    return {'id': supplier.id, 'name': supplier.name, 'email': supplier.email, 'phone': supplier.phone, 'location': supplier.location, 'contact': ' · '.join(part for part in [supplier.email, supplier.phone] if part), 'products': [product.name for product in products], 'productCosts': product_details, 'lastCost': float(costs[0]) if costs else 0, 'history': variation_percent, 'lastPurchase': latest.purchased_at.date().isoformat() if latest else '', 'observations': supplier.notes or '', 'minimumOrder': supplier.minimum_order, 'deliveryDays': supplier.delivery_days}


@router.get('/{supplier_id}/cost-analysis')
def cost_analysis(supplier_id: str, _: User = Depends(require_permission('suppliers:read')), db: Session = Depends(get_db)):
    if not db.get(Supplier, supplier_id):
        raise HTTPException(status_code=404, detail='Supplier not found.')
    return list(db.execute(select(Product.id, Product.name, Purchase.purchased_at, PurchaseItem.real_unit_cost).join(PurchaseItem, PurchaseItem.product_id == Product.id).join(Purchase, Purchase.id == PurchaseItem.purchase_id).where(Purchase.supplier_id == supplier_id).order_by(Purchase.purchased_at.desc())).mappings())


@router.post('', response_model=SupplierRecord, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, actor: User = Depends(require_permission('suppliers:manage')), db: Session = Depends(get_db)):
    ensure_unique(db, payload.name, payload.email, payload.phone)
    products = validate_product_ids(db, payload.product_ids)
    supplier = Supplier(**payload.model_dump(exclude={'product_ids'}, exclude_none=True))
    db.add(supplier)
    db.flush()
    db.add_all(SupplierProduct(supplier_id=supplier.id, product_id=product.id) for product in products)
    audit(db, actor.id, 'suppliers.create', 'supplier', supplier.id)
    db.commit()
    db.refresh(supplier)
    return supplier_record(supplier, db)


@router.put('/{supplier_id}/products')
def set_supplier_products(supplier_id: str, product_ids: list[str], actor: User = Depends(require_permission('suppliers:manage')), db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail='Supplier not found.')
    products = validate_product_ids(db, product_ids)
    db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier.id).delete(synchronize_session=False)
    db.add_all(SupplierProduct(supplier_id=supplier.id, product_id=product.id) for product in products)
    audit(db, actor.id, 'suppliers.products.update', 'supplier', supplier.id, {'product_ids': product_ids})
    db.commit()
    return {'supplier_id': supplier.id, 'product_ids': product_ids}


@router.patch('/{supplier_id}', response_model=SupplierRecord)
def update_supplier(supplier_id: str, payload: SupplierUpdate, actor: User = Depends(require_permission('suppliers:manage')), db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail='Supplier not found.')
    changes = payload.model_dump(exclude_unset=True)
    product_ids = changes.pop('product_ids', None)
    ensure_unique(db, changes.get('name', supplier.name), changes.get('email', supplier.email), changes.get('phone', supplier.phone), supplier.id)
    products = validate_product_ids(db, product_ids) if product_ids is not None else None
    for key, value in changes.items():
        setattr(supplier, key, value)
    if products is not None:
        db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier.id).delete(synchronize_session=False)
        db.add_all(SupplierProduct(supplier_id=supplier.id, product_id=product.id) for product in products)
    audit(db, actor.id, 'suppliers.update', 'supplier', supplier.id)
    db.commit()
    db.refresh(supplier)
    return supplier_record(supplier, db)
