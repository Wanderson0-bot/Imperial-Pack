from dataclasses import dataclass
from datetime import date
from statistics import mean, median, pstdev
from typing import Sequence


@dataclass(frozen=True)
class PurchaseObservation:
    purchased_at: date
    quantity: float


@dataclass(frozen=True)
class ConsumptionFeatures:
    purchase_count: int
    last_purchase: date | None
    last_quantity: float | None
    mean_interval_days: float | None
    mean_quantity_per_purchase: float | None
    observed_quantity_per_day: float | None
    trend: str
    sufficient_for_model: bool
    quantity_total: float = 0
    quantity_median: float | None = None
    quantity_minimum: float | None = None
    quantity_maximum: float | None = None
    days_since_last_purchase: int | None = None
    median_interval_days: float | None = None
    minimum_interval_days: int | None = None
    maximum_interval_days: int | None = None
    interval_stddev_days: float | None = None
    recent_quantity_7d: float = 0
    recent_quantity_14d: float = 0
    recent_quantity_30d: float = 0
    recent_quantity_60d: float = 0
    recent_quantity_90d: float = 0


def build_features(observations: Sequence[PurchaseObservation]) -> ConsumptionFeatures:
    ordered = sorted(observations, key=lambda entry: entry.purchased_at)
    if not ordered:
        return ConsumptionFeatures(0, None, None, None, None, None, 'unknown', False)
    intervals = [(current.purchased_at - previous.purchased_at).days for previous, current in zip(ordered, ordered[1:])]
    elapsed = (ordered[-1].purchased_at - ordered[0].purchased_at).days
    mean_quantity = mean(item.quantity for item in ordered)
    trend = 'unknown'
    if len(ordered) >= 4:
        split = len(ordered) // 2
        earlier = mean(item.quantity for item in ordered[:split])
        later = mean(item.quantity for item in ordered[split:])
        ratio = (later - earlier) / earlier if earlier else 0
        trend = 'increasing' if ratio > .1 else 'decreasing' if ratio < -.1 else 'stable'
    quantities = [item.quantity for item in ordered]
    as_of = ordered[-1].purchased_at
    recent = lambda days: sum(item.quantity for item in ordered if 0 <= (as_of - item.purchased_at).days < days)
    return ConsumptionFeatures(
        purchase_count=len(ordered), last_purchase=ordered[-1].purchased_at,
        last_quantity=ordered[-1].quantity, mean_interval_days=mean(intervals) if intervals else None,
        mean_quantity_per_purchase=mean_quantity,
        observed_quantity_per_day=sum(item.quantity for item in ordered) / elapsed if elapsed else None,
        trend=trend, sufficient_for_model=len(ordered) >= 3 and elapsed > 0,
        quantity_total=sum(quantities), quantity_median=median(quantities),
        quantity_minimum=min(quantities), quantity_maximum=max(quantities),
        days_since_last_purchase=0,
        median_interval_days=median(intervals) if intervals else None,
        minimum_interval_days=min(intervals) if intervals else None,
        maximum_interval_days=max(intervals) if intervals else None,
        interval_stddev_days=pstdev(intervals) if len(intervals) > 1 else (0.0 if intervals else None),
        recent_quantity_7d=recent(7), recent_quantity_14d=recent(14),
        recent_quantity_30d=recent(30), recent_quantity_60d=recent(60),
        recent_quantity_90d=recent(90),
    )
