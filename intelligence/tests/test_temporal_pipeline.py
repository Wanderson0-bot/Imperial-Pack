from datetime import date, timedelta
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / 'backend'))
sys.path.insert(0, str(REPOSITORY_ROOT))

from app.intelligence.pipeline import _fit, _predict, _samples


def test_temporal_snapshots_do_not_include_target_purchase():
    events = [(date(2026, 1, 1) + timedelta(days=10 * index), 100 + index) for index in range(5)]
    samples = _samples(events)

    assert samples[0]['target_date'] == events[3][0].isoformat()
    assert samples[0]['features']['purchase_count'] == 3
    assert samples[0]['features']['last_quantity'] == events[2][1]
    assert samples[0]['target_quantity'] == events[3][1]


def test_pairwise_ridge_learns_temporal_interval_relationship():
    samples = []
    for interval in (5, 7, 9, 11, 13):
        samples.append({
            'features': {'mean_interval_days': interval, 'last_interval_days': interval,
                         'mean_quantity': 10, 'last_quantity': 10},
            'target_interval_days': interval + 2,
        })
    keys = ('mean_interval_days', 'last_interval_days')
    model = _fit(samples, keys, 'target_interval_days')
    predicted = _predict(model, {'mean_interval_days': 15, 'last_interval_days': 15}, keys)

    assert 15 <= predicted <= 19
