from collections import defaultdict
from statistics import mean
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.models import ConsumptionHistory


def observed_consumption(db: Session, partner_id: str) -> list[dict]:
    rows = list(db.scalars(select(ConsumptionHistory).where(ConsumptionHistory.partner_id == partner_id, ConsumptionHistory.voided.is_(False)).order_by(ConsumptionHistory.purchased_at.asc())))
    by_product: dict[str, list[ConsumptionHistory]] = defaultdict(list)
    for row in rows:
        by_product[row.product_id].append(row)
    results = []
    for product_id, purchases in by_product.items():
        intervals = [(current.purchased_at.date() - previous.purchased_at.date()).days for previous, current in zip(purchases, purchases[1:])]
        elapsed = (purchases[-1].purchased_at.date() - purchases[0].purchased_at.date()).days
        average_quantity = mean(float(item.quantity) for item in purchases)
        trend = 'unknown'
        if len(purchases) >= 4:
            split = len(purchases) // 2
            earlier = mean(float(item.quantity) for item in purchases[:split])
            later = mean(float(item.quantity) for item in purchases[split:])
            change = (later - earlier) / earlier if earlier else 0
            trend = 'increasing' if change > .1 else 'decreasing' if change < -.1 else 'stable'
        results.append({
            'product_id': product_id,
            'purchase_count': len(purchases),
            'last_purchase_at': purchases[-1].purchased_at,
            'last_quantity': purchases[-1].quantity,
            'quantity_total': sum((item.quantity for item in purchases), start=0),
            'mean_interval_days': mean(intervals) if intervals else None,
            'frequency_observed': 'single_purchase' if not intervals else 'recurrent',
            'mean_quantity_per_purchase': average_quantity,
            'observed_quantity_per_day': sum(float(item.quantity) for item in purchases) / elapsed if elapsed > 0 else None,
            'trend': trend,
            'statistical_summary_only': True,
        })
    return results
