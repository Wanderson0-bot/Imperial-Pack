from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import ConsumptionHistory, Customer, Order, OrderItem, Partner, PartnerAlert, PartnerCondition, PartnerOpportunity, PartnerReplenishmentCycle, Prediction, PredictionEvaluation, Product, User
from app.database.session import get_db
from app.partners.schemas import ConditionsInput, ConsumptionRecord, CycleInput, PartnerCreate, PredictionEvaluationInput
from app.partners.consumption import observed_consumption
from app.orders.states import REALIZED_ORDER_STATUSES
from app.intelligence.pipeline import _history, load_active_model, predict_pair
from intelligence.prediction.provider import ArtifactPredictionProvider

router = APIRouter(prefix='/partners', tags=['partners'])
ALLOWED_CYCLES = {'weekly', 'fortnightly', 'monthly', 'bimonthly', 'custom'}


@router.get('')
def list_partners(_: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    partners = list(db.scalars(select(Partner).where(Partner.status == 'ACTIVE').order_by(Partner.activated_at.desc())))
    result = []
    for partner in partners:
        customer = db.get(Customer, partner.customer_id)
        condition = db.scalar(select(PartnerCondition).where(PartnerCondition.partner_id == partner.id))
        cycle = db.scalar(select(PartnerReplenishmentCycle).where(PartnerReplenishmentCycle.partner_id == partner.id, PartnerReplenishmentCycle.is_active.is_(True)).order_by(PartnerReplenishmentCycle.created_at.desc()))
        result.append({'id': partner.id, 'customer': customer, 'status': partner.status, 'conditions': condition, 'cycle': cycle})
    return result


@router.post('', status_code=status.HTTP_201_CREATED)
def activate_partner(payload: PartnerCreate, actor: User = Depends(require_permission('partners:activate')), db: Session = Depends(get_db)):
    customer = db.get(Customer, payload.customer_id)
    if not customer or customer.status != 'ACTIVE':
        raise HTTPException(status_code=404, detail='Active customer not found.')
    existing = db.scalar(select(Partner).where(Partner.customer_id == customer.id))
    if existing:
        if existing.status == 'ACTIVE':
            raise HTTPException(status_code=409, detail='Customer is already an active partner.')
        existing.status = 'ACTIVE'
        existing.activated_at = datetime.now(timezone.utc)
        existing.deactivated_at = None
        partner = existing
    else:
        partner = Partner(customer_id=customer.id, created_by=actor.id)
        db.add(partner)
        db.flush()
    audit(db, actor.id, 'partners.activate', 'partner', partner.id, {'customer_id': customer.id})
    db.commit()
    db.refresh(partner)
    return {'id': partner.id, 'customer_id': partner.customer_id, 'status': partner.status, 'activated_at': partner.activated_at}


@router.post('/{partner_id}/deactivate')
def deactivate_partner(partner_id: str, actor: User = Depends(require_permission('partners:deactivate')), db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    partner.status = 'INACTIVE'
    partner.deactivated_at = datetime.now(timezone.utc)
    audit(db, actor.id, 'partners.deactivate', 'partner', partner.id)
    db.commit()
    return {'id': partner.id, 'status': partner.status, 'customer_id': partner.customer_id}


@router.put('/{partner_id}/conditions')
def set_conditions(partner_id: str, payload: ConditionsInput, actor: User = Depends(require_permission('partners:conditions')), db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if not partner or partner.status != 'ACTIVE':
        raise HTTPException(status_code=404, detail='Active partner not found.')
    condition = db.scalar(select(PartnerCondition).where(PartnerCondition.partner_id == partner.id))
    if condition:
        for key, value in payload.model_dump().items(): setattr(condition, key, value)
    else:
        condition = PartnerCondition(partner_id=partner.id, **payload.model_dump())
        db.add(condition)
    audit(db, actor.id, 'partners.conditions.update', 'partner', partner.id)
    db.commit()
    db.refresh(condition)
    return condition


@router.put('/{partner_id}/cycle')
def set_cycle(partner_id: str, payload: CycleInput, actor: User = Depends(require_permission('partners:conditions')), db: Session = Depends(get_db)):
    if payload.cycle_type not in ALLOWED_CYCLES or (payload.cycle_type == 'custom' and payload.custom_days is None):
        raise HTTPException(status_code=422, detail='A custom cycle requires custom_days; choose a supported cycle type.')
    partner = db.get(Partner, partner_id)
    if not partner or partner.status != 'ACTIVE':
        raise HTTPException(status_code=404, detail='Active partner not found.')
    for previous in db.scalars(select(PartnerReplenishmentCycle).where(PartnerReplenishmentCycle.partner_id == partner.id, PartnerReplenishmentCycle.is_active.is_(True))):
        previous.is_active = False
    cycle = PartnerReplenishmentCycle(partner_id=partner.id, cycle_type=payload.cycle_type, custom_days=payload.custom_days)
    db.add(cycle)
    audit(db, actor.id, 'partners.cycle.update', 'partner', partner.id, payload.model_dump())
    db.commit()
    return cycle


def partner_history_summary(db: Session, partner_id: str) -> dict:
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    customer = db.get(Customer, partner.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Partner customer not found.')

    orders = list(db.scalars(select(Order).where(Order.customer_id == customer.id, Order.status.in_(REALIZED_ORDER_STATUSES)).order_by(Order.ordered_at.asc())))
    if not orders:
        return {
            'partner_id': partner.id,
            'customer_id': customer.id,
            'status': 'insufficient_data',
            'message': 'Não há histórico suficiente para uma estimativa confiável.',
            'orders': 0,
            'last_purchase': None,
            'average_value': Decimal('0'),
            'frequency': None,
            'product_summary': {},
        }

    order_ids = [order.id for order in orders]
    order_items = list(db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)).order_by(OrderItem.order_id.asc())))

    by_product: dict[str, dict] = {}
    total_value = sum((order.total for order in orders), Decimal('0'))
    intervals = [(current.ordered_at.date() - previous.ordered_at.date()).days for previous, current in zip(orders, orders[1:])]
    for item in order_items:
        product = db.get(Product, item.product_id)
        if product is None:
            continue
        product_summary = by_product.setdefault(item.product_id, {'product_id': item.product_id, 'product_name': product.name, 'quantity': Decimal('0'), 'value': Decimal('0'), 'purchases': 0})
        product_summary['quantity'] += item.quantity
        product_summary['value'] += item.subtotal
        product_summary['purchases'] += 1

    average_interval = mean(intervals) if intervals else None
    summary = {
        'partner_id': partner.id,
        'customer_id': customer.id,
        'status': 'ready' if len(orders) >= 2 else 'insufficient_data',
        'message': 'Histórico suficiente para estimativa confiável.' if len(orders) >= 2 else 'Não há histórico suficiente para uma estimativa confiável.',
        'orders': len(orders),
        'last_purchase': orders[-1].ordered_at,
        'average_value': total_value / Decimal(len(orders)) if orders else Decimal('0'),
        'frequency': {'average_days': average_interval, 'intervals': intervals},
        'product_summary': by_product,
    }
    if len(orders) < 2:
        summary['status'] = 'insufficient_data'
        summary['message'] = 'Não há histórico suficiente para uma estimativa confiável.'
    return summary


def partner_replenishment_estimate(db: Session, partner_id: str) -> dict:
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    history = partner_history_summary(db, partner.id)
    if history['status'] == 'insufficient_data':
        return {
            'partner_id': partner.id,
            'customer_id': partner.customer_id,
            'status': 'insufficient_data',
            'message': 'Não há histórico suficiente para uma estimativa confiável.',
            'physical_stock_observed': False,
            'product_estimates': {},
        }

    customer_orders = list(db.scalars(select(Order).where(Order.customer_id == partner.customer_id, Order.status.in_(REALIZED_ORDER_STATUSES)).order_by(Order.ordered_at.asc())))
    order_ids = [order.id for order in customer_orders]
    records = list(db.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)).order_by(OrderItem.order_id.asc())))
    by_product: dict[str, list[OrderItem]] = {}
    for row in records:
        by_product.setdefault(row.product_id, []).append(row)

    estimates = {}
    for product_id, rows in by_product.items():
        if len(rows) < 2:
            continue
        product_order_ids = {row.order_id for row in rows}
        product_orders = [order for order in customer_orders if order.id in product_order_ids]
        if len(product_orders) < 2:
            continue
        intervals = [(current.ordered_at.date() - previous.ordered_at.date()).days for previous, current in zip(product_orders, product_orders[1:])]
        if not intervals:
            continue
        avg_interval = mean(intervals)
        avg_qty = sum((row.quantity for row in rows), Decimal('0')) / Decimal(len(rows))
        last = product_orders[-1]
        last_quantity = sum((row.quantity for row in rows if row.order_id == last.id), Decimal('0'))
        estimates[product_id] = {
            'product_id': product_id,
            'last_purchase': last.ordered_at,
            'last_quantity': last_quantity,
            'average_interval_days': Decimal(str(avg_interval)) if isinstance(avg_interval, float) else avg_interval,
            'average_quantity_per_purchase': avg_qty,
            'next_replenishment_window_start': last.ordered_at + timedelta(days=round(avg_interval)),
            'confidence': 'limited' if len(rows) < 3 else 'medium',
        }

    return {
        'partner_id': partner.id,
        'customer_id': partner.customer_id,
        'status': 'ready' if estimates else 'insufficient_data',
        'message': 'Estimativa baseada nos pedidos observados; o estoque físico do cliente não é observado.' if estimates else 'Não há histórico suficiente para uma estimativa confiável.',
        'physical_stock_observed': False,
        'product_estimates': estimates,
    }


@router.get('/{partner_id}/history')
def partner_history(partner_id: str, _: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    return partner_history_summary(db, partner_id)


@router.get('/{partner_id}/replenishment')
def partner_replenishment(partner_id: str, _: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    return partner_replenishment_estimate(db, partner_id)


@router.get('/{partner_id}/consumption', response_model=list[ConsumptionRecord])
def consumption(partner_id: str, _: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    return list(db.scalars(select(ConsumptionHistory).where(ConsumptionHistory.partner_id == partner.id, ConsumptionHistory.voided.is_(False)).order_by(ConsumptionHistory.purchased_at.desc())))


@router.get('/{partner_id}/consumption/summary')
def consumption_summary(partner_id: str, _: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    return observed_consumption(db, partner.id)


@router.get('/{partner_id}/predictions')
def partner_predictions(partner_id: str, _: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    partner = db.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail='Partner not found.')
    histories, _ = _history(db, datetime.now(timezone.utc).date())
    artifact = load_active_model()
    provider = ArtifactPredictionProvider(lambda: artifact, predict_pair)
    predictions = []
    customer = db.get(Customer, partner.customer_id)
    if artifact:
        for (candidate_partner_id, product_id), events in histories.items():
            if candidate_partner_id != partner.id:
                continue
            try:
                forecast = provider.predict_pair(partner.id, product_id, events)
            except RuntimeError:
                continue
            today = datetime.now(timezone.utc).date().isoformat()
            prediction = db.scalar(select(Prediction).where(
                Prediction.partner_id == partner.id, Prediction.product_id == product_id,
                Prediction.model_version == artifact['version'],
                func.date(Prediction.generated_at) == today,
            ).order_by(Prediction.generated_at.desc()).limit(1))
            if prediction is None:
                prediction = Prediction(partner_id=partner.id, product_id=product_id,
                    prediction_type='partner_replenishment', payload=forecast, model_version=artifact['version'])
                db.add(prediction)
                db.flush()
                if forecast['confidence'] in {'high', 'medium'}:
                    product = db.get(Product, product_id)
                    dedupe_key = f'ml_replenishment:{partner.id}:{product_id}'
                    opportunity = db.scalar(select(PartnerOpportunity).where(PartnerOpportunity.dedupe_key == dedupe_key))
                    evidence = {'prediction_id': prediction.id, 'model_version': artifact['version'],
                        'window': forecast['replenishment_window'], 'recommended_quantity': forecast['recommended_quantity'],
                        'confidence_basis': forecast['confidence_basis']}
                    if opportunity:
                        opportunity.evidence = evidence
                        opportunity.description = forecast['explanation']
                    else:
                        db.add(PartnerOpportunity(partner_id=partner.id, product_id=product_id,
                            customer_id=partner.customer_id, entity_type='partner', entity_id=partner.id,
                            entity_label=customer.name if customer else partner.id,
                            title=f"Reposição prevista · {product.name if product else product_id}",
                            description=forecast['explanation'],
                            action='Confirmar a necessidade diretamente com o parceiro antes de registrar um pedido.',
                            evidence=evidence, status='OPEN', is_active=True, dedupe_key=dedupe_key))
            predictions.append(prediction)
    db.commit()
    if predictions:
        return {'status': 'ready', 'method': 'machine_learning_pair_specific', 'predictions': predictions}
    pair_counts = [len(events) for (candidate_partner_id, _), events in histories.items() if candidate_partner_id == partner.id]
    best_pair_count = max(pair_counts, default=0)
    if best_pair_count < 8:
        message = f'DADOS INSUFICIENTES PARA PREVISÃO ML. Melhor histórico deste parceiro: {best_pair_count} compras de produto; mínimo 8 por relacionamento, além da validação temporal.'
        status_value = 'insufficient-data'
    elif artifact is None:
        message = 'Histórico disponível, mas não há modelo ML ativo. Um administrador deve iniciar treinamento validado.'
        status_value = 'model-unavailable'
    else:
        message = 'Este parceiro/produto não foi aprovado na validação temporal; nenhuma previsão ML foi gerada.'
        status_value = 'model-unavailable'
    return {'status': status_value, 'predictions': [], 'message': message, 'minimum_observations': 8}


@router.post('/predictions/{prediction_id}/evaluation', status_code=status.HTTP_201_CREATED)
def evaluate_prediction(prediction_id: str, payload: PredictionEvaluationInput, actor: User = Depends(require_permission('partners:evaluate_predictions')), db: Session = Depends(get_db)):
    prediction = db.get(Prediction, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail='Prediction not found.')
    if db.scalar(select(PredictionEvaluation.id).where(PredictionEvaluation.prediction_id == prediction.id)):
        raise HTTPException(status_code=409, detail='Prediction has already been evaluated.')
    predicted = prediction.payload.get('recommended_quantity')
    absolute_error = abs(payload.actual_value - Decimal(str(predicted))) if payload.actual_value is not None and predicted is not None else None
    evaluation = PredictionEvaluation(prediction_id=prediction.id, actual_value=payload.actual_value, actual_at=payload.actual_at, absolute_error=absolute_error)
    db.add(evaluation)
    audit(db, actor.id, 'partners.prediction.evaluate', 'prediction', prediction.id, payload.model_dump(mode='json'))
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.get('/alerts')
def alerts(_: User = Depends(require_permission('partners:read')), db: Session = Depends(get_db)):
    return list(db.scalars(select(PartnerAlert).where(PartnerAlert.entity_type == 'partner', PartnerAlert.partner_id.is_not(None), PartnerAlert.resolved_at.is_(None), PartnerAlert.status == 'OPEN').order_by(PartnerAlert.created_at.desc())))
