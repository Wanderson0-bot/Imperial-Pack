from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models import ConsumptionHistory, Customer, Order, Partner, Product
from app.intelligence.pipeline import aggregate_evaluation_metrics, load_active_model, predict_pair, train_model


def test_real_pipeline_trains_persists_loads_and_predicts_pairwise_model(tmp_path, monkeypatch):
    monkeypatch.setenv('INTELLIGENCE_MODEL_DIR', str(tmp_path / 'model-artifacts'))
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        customer = Customer(name='Isolated ML fixture')
        product = Product(name='Fixture product', unit='un', current_cost=1, current_price=2)
        db.add_all([customer, product])
        db.flush()
        partner = Partner(customer_id=customer.id)
        db.add(partner)
        db.flush()
        day = date.today() - timedelta(days=250)
        elapsed = 0
        for index in range(12):
            if index:
                elapsed += 5 + index
            purchased_at = datetime.combine(day + timedelta(days=elapsed), datetime.min.time(), timezone.utc)
            order = Order(customer_id=customer.id, ordered_at=purchased_at, subtotal=Decimal('2'), total=Decimal('2'))
            db.add(order)
            db.flush()
            db.add(ConsumptionHistory(partner_id=partner.id, customer_id=customer.id, product_id=product.id,
                order_id=order.id, quantity=Decimal(100 + index * 10), purchased_at=purchased_at,
                unit_price=Decimal('2'), source='TEST'))
        db.commit()

        result = train_model(db, 'isolated-test-user')
        artifact = load_active_model()
        forecast = predict_pair(artifact, partner.id, product.id, [
            (day + timedelta(days=sum(5 + position for position in range(1, index + 1))), float(100 + index * 10))
            for index in range(12)
        ]) if artifact else None

        assert result['status'] == 'active'
        assert result['eligible_pairs'] == 1
        assert artifact is not None and artifact['version'] == result['version']
        assert forecast is not None
        assert forecast['method'] == 'machine_learning_pair_specific'
        assert forecast['recommended_quantity'] > 0
        assert forecast['physical_stock_observed'] is False
    engine.dispose()


def test_outcome_metrics_measure_quantity_and_replenishment_window_error():
    anchor = date(2026, 1, 1)
    evaluation = SimpleNamespace(absolute_error=Decimal('5'), actual_value=Decimal('100'),
        actual_at=datetime(2026, 1, 14, tzinfo=timezone.utc))

    metrics = aggregate_evaluation_metrics([(evaluation, {
        'anchor_purchase_date': anchor.isoformat(), 'predicted_interval_days': 10,
    })])

    assert metrics['mae'] == 5
    assert metrics['mape_percent'] == 5
    assert metrics['interval_error_days']['mae'] == 3
