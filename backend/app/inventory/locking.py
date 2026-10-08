from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import InventoryBalance, Product


def lock_product_balances(db: Session, product_ids: list[str]) -> dict[str, InventoryBalance]:
    ordered_ids = sorted(set(product_ids))
    if not ordered_ids:
        return {}

    products = list(db.scalars(select(Product).where(Product.id.in_(ordered_ids)).order_by(Product.id).with_for_update().execution_options(populate_existing=True)))
    if len(products) != len(ordered_ids):
        raise ValueError('One or more inventory products no longer exist.')

    balances = list(db.scalars(select(InventoryBalance).where(InventoryBalance.product_id.in_(ordered_ids)).order_by(InventoryBalance.product_id).with_for_update().execution_options(populate_existing=True)))
    result = {balance.product_id: balance for balance in balances}
    for product in products:
        if product.id not in result:
            balance = InventoryBalance(product_id=product.id, quantity=0)
            db.add(balance)
            result[product.id] = balance
    db.flush()
    return result