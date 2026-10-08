"""Small, pair-specific temporal regression pipeline for partner replenishment."""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ConsumptionHistory

# The established intelligence package lives at the repository root while the
# FastAPI application is launched from ``backend`` in local and hosted setups.
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from intelligence.features.consumption import PurchaseObservation, build_features

ALGORITHM = 'Pairwise ridge regression (next interval and next purchase quantity)'
FEATURES = ['mean_interval_days', 'last_interval_days', 'mean_quantity', 'last_quantity']
MIN_OBSERVATIONS = 8
MODEL_VERSION_PREFIX = 'partner-product-ridge-v1'


def artifact_dir() -> Path:
    configured = os.getenv('INTELLIGENCE_MODEL_DIR')
    return Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / 'model_artifacts'


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.model-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(payload, output, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _features(rows: list[tuple[date, float]]) -> dict[str, float]:
    built = build_features([PurchaseObservation(day, qty) for day, qty in rows])
    intervals = [(rows[i][0] - rows[i - 1][0]).days for i in range(1, len(rows))]
    return {
        'purchase_count': float(built.purchase_count),
        'mean_interval_days': float(built.mean_interval_days or 0),
        'last_interval_days': float(intervals[-1] if intervals else 0),
        'mean_quantity': float(built.mean_quantity_per_purchase or 0),
        'last_quantity': float(built.last_quantity or 0),
        'interval_stddev_days': float(built.interval_stddev_days or 0),
    }


def _samples(rows: list[tuple[date, float]]) -> list[dict[str, Any]]:
    result = []
    # At every cutoff, features contain only purchases available by that date.
    for target_index in range(3, len(rows)):
        previous_day, _ = rows[target_index - 1]
        target_day, target_quantity = rows[target_index]
        result.append({
            'features': _features(rows[:target_index]),
            'target_interval_days': float((target_day - previous_day).days),
            'target_quantity': target_quantity,
            'target_date': target_day.isoformat(),
        })
    return result


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for tiny ridge systems."""
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            augmented[pivot][column] = 1e-12
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            scale = augmented[row][column]
            augmented[row] = [a - scale * b for a, b in zip(augmented[row], augmented[column])]
    return [augmented[row][-1] for row in range(size)]


def _fit(rows: list[dict[str, Any]], feature_keys: tuple[str, str], target_key: str) -> list[float]:
    # Standardize inputs so the small ridge penalty is scale-independent.
    columns = [[float(row['features'][key]) for row in rows] for key in feature_keys]
    means = [statistics.mean(column) for column in columns]
    scales = [statistics.pstdev(column) or 1.0 for column in columns]
    design = [[1.0] + [(columns[col][i] - means[col]) / scales[col] for col in range(2)] for i in range(len(rows))]
    targets = [float(row[target_key]) for row in rows]
    gram = [[sum(row[i] * row[j] for row in design) for j in range(3)] for i in range(3)]
    # Keep the intercept unpenalized; the regularizer stabilizes sparse pairs.
    gram[1][1] += 0.1
    gram[2][2] += 0.1
    coefficients = _solve(gram, [sum(row[i] * target for row, target in zip(design, targets)) for i in range(3)])
    return [coefficients[0], coefficients[1], coefficients[2], means[0], means[1], scales[0], scales[1]]


def _predict(coefficients: list[float], feature_values: dict[str, float], feature_keys: tuple[str, str]) -> float:
    intercept, first, second, mean_first, mean_second, scale_first, scale_second = coefficients
    return intercept + first * (feature_values[feature_keys[0]] - mean_first) / scale_first + second * (feature_values[feature_keys[1]] - mean_second) / scale_second


def _errors(predictions: list[float], actuals: list[float]) -> dict[str, float | int]:
    if not actuals:
        return {'count': 0, 'mae': 0.0, 'rmse': 0.0}
    errors = [prediction - actual for prediction, actual in zip(predictions, actuals)]
    return {'count': len(errors), 'mae': statistics.mean(abs(error) for error in errors), 'rmse': math.sqrt(statistics.mean(error * error for error in errors))}


def _history(db: Session, now: date) -> tuple[dict[tuple[str, str], list[tuple[date, float]]], dict[str, Any]]:
    raw = list(db.scalars(select(ConsumptionHistory).where(ConsumptionHistory.voided.is_(False)).order_by(ConsumptionHistory.purchased_at.asc(), ConsumptionHistory.id.asc())))
    grouped: dict[tuple[str, str], dict[date, float]] = defaultdict(lambda: defaultdict(float))
    order_events: dict[tuple[str, str, str], tuple[date, float]] = {}
    quality = {'source_records': len(raw), 'used_records': 0, 'aggregated_order_product_rows': 0, 'ignored': {'future_or_invalid_date': 0, 'non_positive_quantity': 0, 'extreme_quantity_outlier': 0}, 'pairs_with_history': 0}
    for event in raw:
        key = (event.partner_id, event.product_id, event.order_id)
        purchased_at = event.purchased_at
        event_date = purchased_at.date() if isinstance(purchased_at, datetime) else purchased_at
        quantity = float(event.quantity)
        if event_date > now:
            quality['ignored']['future_or_invalid_date'] += 1
            continue
        if not math.isfinite(quantity) or quantity <= 0:
            quality['ignored']['non_positive_quantity'] += 1
            continue
        if key in order_events:
            quality['aggregated_order_product_rows'] += 1
            prior_day, prior_quantity = order_events[key]
            order_events[key] = (prior_day, prior_quantity + quantity)
        else:
            order_events[key] = (event_date, quantity)
    for (partner_id, product_id, _), (event_date, quantity) in order_events.items():
        grouped[(partner_id, product_id)][event_date] += quantity
        quality['used_records'] += 1
    # Ignore extreme single-day quantities for model fitting only; source rows remain untouched.
    for key, by_day in grouped.items():
        daily_values = list(by_day.values())
        if len(daily_values) < 5:
            continue
        typical = statistics.median(daily_values)
        if typical <= 0:
            continue
        for event_day, quantity in list(by_day.items()):
            if quantity > typical * 10:
                del by_day[event_day]
                quality['ignored']['extreme_quantity_outlier'] += 1
                quality['used_records'] -= 1
    result = {key: sorted(daily.items()) for key, daily in grouped.items()}
    quality['pairs_with_history'] = len(result)
    return result, quality


def train_model(db: Session, trained_by: str) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    history, quality = _history(db, today)
    pair_models: dict[str, Any] = {}
    intervals_predicted, intervals_actual, quantities_predicted, quantities_actual = [], [], [], []
    trained_records = 0
    skipped = 0
    for (partner_id, product_id), events in history.items():
        trained_records += len(events)
        # Same-day lines are aggregated as one consumption event above.
        samples = _samples(events)
        if len(events) < MIN_OBSERVATIONS or len(samples) < 5:
            skipped += 1
            continue
        split = max(3, int(len(samples) * 0.7))
        split = min(split, len(samples) - 2)
        fit_samples, validation = samples[:split], samples[split:]
        gap_keys = ('mean_interval_days', 'last_interval_days')
        qty_keys = ('mean_quantity', 'last_quantity')
        gap_coefficients = _fit(fit_samples, gap_keys, 'target_interval_days')
        qty_coefficients = _fit(fit_samples, qty_keys, 'target_quantity')
        gaps = [max(1.0, _predict(gap_coefficients, row['features'], gap_keys)) for row in validation]
        quantities = [max(0.001, _predict(qty_coefficients, row['features'], qty_keys)) for row in validation]
        actual_gaps = [row['target_interval_days'] for row in validation]
        actual_quantities = [row['target_quantity'] for row in validation]
        baseline_gap = statistics.mean(row['target_interval_days'] for row in fit_samples)
        baseline_quantity = statistics.mean(row['target_quantity'] for row in fit_samples)
        gap_mae = statistics.mean(abs(prediction - actual) for prediction, actual in zip(gaps, actual_gaps))
        quantity_mae = statistics.mean(abs(prediction - actual) for prediction, actual in zip(quantities, actual_quantities))
        gap_baseline_mae = statistics.mean(abs(baseline_gap - actual) for actual in actual_gaps)
        qty_baseline_mae = statistics.mean(abs(baseline_quantity - actual) for actual in actual_quantities)
        # Only retain an ML pair when both targets beat their temporal holdout baseline.
        if gap_mae > gap_baseline_mae or quantity_mae > qty_baseline_mae:
            skipped += 1
            continue
        intervals_predicted.extend(gaps)
        intervals_actual.extend(actual_gaps)
        quantities_predicted.extend(quantities)
        quantities_actual.extend(actual_quantities)
        # Refit on all available samples after the untouched temporal holdout.
        pair_models[f'{partner_id}:{product_id}'] = {
            'partner_id': partner_id, 'product_id': product_id,
            'gap_coefficients': _fit(samples, gap_keys, 'target_interval_days'),
            'quantity_coefficients': _fit(samples, qty_keys, 'target_quantity'),
            'validation': {'samples': len(validation), 'gap_mae': gap_mae, 'quantity_mae': quantity_mae,
                           'gap_baseline_mae': gap_baseline_mae, 'quantity_baseline_mae': qty_baseline_mae},
            'observation_count': len(events), 'history_start': events[0][0].isoformat(), 'history_end': events[-1][0].isoformat(),
        }
    if not pair_models:
        return {'status': 'awaiting_data', 'message': 'Nenhum relacionamento atingiu o mínimo de dados e validação temporal. Nenhum artefato foi ativado.', 'quality': quality, 'eligible_pairs': 0, 'insufficient_pairs': skipped, 'minimum_observations': MIN_OBSERVATIONS}

    version = f'{MODEL_VERSION_PREFIX}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}'
    metrics = {'interval_days': _errors(intervals_predicted, intervals_actual), 'next_quantity': _errors(quantities_predicted, quantities_actual)}
    artifact = {
        'version': version, 'status': 'active', 'algorithm': ALGORITHM, 'features': FEATURES,
        'target': {'interval_days': 'days until next partner-product purchase', 'next_quantity': 'quantity on next partner-product order'},
        'horizon': 'until the next observed purchase', 'minimum_observations': MIN_OBSERVATIONS,
        'trained_at': datetime.now(timezone.utc).isoformat(), 'trained_by': trained_by,
        'training_records': trained_records, 'quality': quality, 'training_period': {
            'start': min(pair['history_start'] for pair in pair_models.values()),
            'end': max(pair['history_end'] for pair in pair_models.values()),
        }, 'metrics': metrics, 'eligible_pairs': len(pair_models), 'insufficient_pairs': skipped, 'pairs': pair_models,
        'validation_method': 'Per-pair chronological holdout (last 30% of snapshots, minimum 2); ML pair activated only when it beats the training-mean baseline on both targets.',
        'confidence_method': 'Reliability tier derived from out-of-time holdout relative MAE and record count; not a calibrated probability.',
    }
    directory = artifact_dir()
    _atomic_json(directory / f'{version}.json', artifact)
    _atomic_json(directory / 'active.json', {'version': version, 'artifact': f'{version}.json'})
    return {'status': 'active', 'version': version, 'algorithm': ALGORITHM, 'training_records': trained_records,
            'eligible_pairs': len(pair_models), 'insufficient_pairs': skipped, 'training_period': artifact['training_period'],
            'metrics': metrics, 'quality': quality}


def load_active_model() -> dict[str, Any] | None:
    try:
        directory = artifact_dir()
        pointer = json.loads((directory / 'active.json').read_text(encoding='utf-8'))
        artifact = json.loads((directory / pointer['artifact']).read_text(encoding='utf-8'))
        if artifact.get('version') != pointer.get('version') or artifact.get('status') != 'active':
            return None
        return artifact
    except (OSError, ValueError, KeyError, TypeError):
        return None


def predict_pair(artifact: dict[str, Any], partner_id: str, product_id: str, events: list[tuple[date, float]]) -> dict[str, Any] | None:
    pair = artifact.get('pairs', {}).get(f'{partner_id}:{product_id}')
    if not pair or len(events) < MIN_OBSERVATIONS:
        return None
    if any((events[index][0] - events[index - 1][0]).days <= 0 for index in range(1, len(events))):
        return None
    feature_values = _features(events)
    gap_keys = ('mean_interval_days', 'last_interval_days')
    qty_keys = ('mean_quantity', 'last_quantity')
    gap = max(1, round(_predict(pair['gap_coefficients'], feature_values, gap_keys)))
    historical_quantities = [quantity for _, quantity in events]
    quantity = _predict(pair['quantity_coefficients'], feature_values, qty_keys)
    quantity = min(max(quantity, min(historical_quantities) * 0.25), max(historical_quantities) * 4)
    validation = pair['validation']
    relative_gap_error = validation['gap_mae'] / max(1.0, statistics.mean([feature_values['mean_interval_days'], 1.0]))
    confidence = 'high' if pair['observation_count'] >= 12 and relative_gap_error <= .2 else 'medium' if pair['observation_count'] >= 8 and relative_gap_error <= .5 else 'low'
    window_days = max(1, math.ceil(validation['gap_mae']))
    center = events[-1][0] + timedelta(days=gap)
    return {
        'predicted_consumption': quantity, 'recommended_quantity': quantity,
        'predicted_interval_days': gap,
        'anchor_purchase_date': events[-1][0].isoformat(),
        'replenishment_window': {'start': (center - timedelta(days=window_days)).isoformat(), 'end': (center + timedelta(days=window_days)).isoformat()},
        'confidence': confidence, 'confidence_basis': 'Faixa de confiabilidade baseada no erro absoluto relativo em validação temporal; não é probabilidade calibrada.',
        'trend': build_features([PurchaseObservation(day, qty) for day, qty in events]).trend,
        'method': 'machine_learning_pair_specific', 'model_version': artifact['version'],
        'physical_stock_observed': False,
        'explanation': f"Regressão treinada apenas com {pair['observation_count']} compras deste parceiro e produto; janela calculada com erro temporal observado de {validation['gap_mae']:.1f} dias.",
    }


def aggregate_evaluation_metrics(evaluations: list[Any]) -> dict[str, Any]:
    quantity_rows = []
    interval_errors = []
    for evaluation, payload in evaluations:
        if evaluation.absolute_error is not None and evaluation.actual_value is not None:
            quantity_rows.append((float(evaluation.absolute_error), float(evaluation.actual_value)))
        if evaluation.actual_at is not None and payload.get('anchor_purchase_date') and payload.get('predicted_interval_days') is not None:
            actual_date = evaluation.actual_at.date() if isinstance(evaluation.actual_at, datetime) else evaluation.actual_at
            anchor_date = date.fromisoformat(payload['anchor_purchase_date'])
            actual_interval = (actual_date - anchor_date).days
            if actual_interval >= 0:
                interval_errors.append(abs(float(payload['predicted_interval_days']) - actual_interval))
    quantity_errors = [error for error, _ in quantity_rows]
    percentages = [error / abs(actual) * 100 for error, actual in quantity_rows if actual != 0]
    return {
        'count': len(quantity_rows),
        'mae': statistics.mean(quantity_errors) if quantity_errors else None,
        'rmse': math.sqrt(statistics.mean(error ** 2 for error in quantity_errors)) if quantity_errors else None,
        'mape_percent': statistics.mean(percentages) if percentages else None,
        'interval_error_days': {
            'count': len(interval_errors),
            'mae': statistics.mean(interval_errors) if interval_errors else None,
            'rmse': math.sqrt(statistics.mean(error ** 2 for error in interval_errors)) if interval_errors else None,
        },
    }
