from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import InventoryBalance, InventoryMovement, Product, User
from app.database.session import get_db
from app.inventory.schemas import InventoryAdjustment, InventoryMovementRecord
from app.inventory.locking import lock_product_balances

router = APIRouter(prefix='/inventory', tags=['inventory'])


@router.get('/movements', response_model=list[InventoryMovementRecord])
def movements(_: User = Depends(require_permission('inventory:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(InventoryMovement).order_by(InventoryMovement.occurred_at.desc()).limit(500)))


@router.get('/balances')
def balances(_: User = Depends(require_permission('inventory:read')), db: Session = Depends(get_db)):
    rows = db.execute(select(InventoryBalance, Product).join(Product, Product.id == InventoryBalance.product_id).order_by(Product.name))
    return [{'product_id': product.id, 'product_name': product.name, 'quantity': balance.quantity, 'minimum': product.minimum_stock, 'status': 'Sem estoque' if balance.quantity <= 0 else 'Crítico' if balance.quantity <= product.minimum_stock / 2 else 'Baixo' if balance.quantity <= product.minimum_stock else 'Normal'} for balance, product in rows]


@router.post('/adjustments', status_code=status.HTTP_201_CREATED)
def adjust(payload: InventoryAdjustment, actor: User = Depends(require_permission('inventory:adjust')), db: Session = Depends(get_db)):
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found.')
    if payload.quantity_delta == 0:
        raise HTTPException(status_code=422, detail='Inventory delta must not be zero.')
    movement_type = payload.normalized_movement_type
    try:
        balance = lock_product_balances(db, [product.id])[product.id]
    except ValueError as error:
        raise HTTPException(status_code=404, detail='Product not found.') from error
    previous_quantity = balance.quantity
    new_balance = balance.quantity + payload.quantity_delta
    if new_balance < Decimal('0'):
        raise HTTPException(status_code=409, detail='Adjustment would make stock negative.')
    balance.quantity = new_balance
    movement = InventoryMovement(
        product_id=product.id,
        movement_type=movement_type,
        quantity=abs(payload.quantity_delta),
        reason=payload.reason,
        notes=payload.notes,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        created_by=actor.id,
    )
    db.add(movement)
    audit(db, actor.id, 'inventory.adjust', 'product', product.id, {'before': str(previous_quantity), 'after': str(new_balance), 'delta': str(payload.quantity_delta), 'reason': payload.reason, 'type': movement_type})
    db.commit()
    return {'product_id': product.id, 'quantity': balance.quantity, 'movement_id': movement.id}
