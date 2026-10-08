from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.core.audit import audit
from app.database.models import ConsumptionHistory, Partner, Prediction, PredictionEvaluation, User
from app.database.session import get_db
from app.intelligence.pipeline import aggregate_evaluation_metrics, load_active_model, train_model

router = APIRouter(prefix='/intelligence', tags=['intelligence'])


@router.get('/status')
def status(_: User = Depends(require_permission('intelligence:read')), db: Session = Depends(get_db)):
    records = db.scalar(select(func.count(ConsumptionHistory.id)).where(ConsumptionHistory.voided.is_(False))) or 0
    partners = db.scalar(select(func.count(Partner.id)).where(Partner.status == 'ACTIVE')) or 0
    products = db.scalar(select(func.count(func.distinct(ConsumptionHistory.product_id))).where(ConsumptionHistory.voided.is_(False))) or 0
    predictions = db.scalar(select(func.count(Prediction.id))) or 0
    model = load_active_model()
    evaluation_query = select(PredictionEvaluation, Prediction.payload)
    if model:
        evaluation_query = evaluation_query.join(Prediction, Prediction.id == PredictionEvaluation.prediction_id).where(Prediction.model_version == model['version'])
    else:
        evaluation_query = evaluation_query.join(Prediction, Prediction.id == PredictionEvaluation.prediction_id).where(Prediction.model_version == '__no_active_model__')
    metrics = aggregate_evaluation_metrics(list(db.execute(evaluation_query)))
    if model:
        model_status = 'active'
        message = 'Modelo versionado ativo; previsões ML só são geradas para relacionamentos treinados e validados.'
    else:
        model_status = 'awaiting_data'
        message = 'Aguardando histórico real suficiente para validação temporal; estatísticas descritivas não são previsões ML.'
    pair_count = model['eligible_pairs'] if model else 0
    return {
        'ml_configured': bool(model), 'model_status': model_status,
        'model_version': model.get('version') if model else None,
        'algorithm': model.get('algorithm') if model else None,
        'trained_at': model.get('trained_at') if model else None,
        'training_period': model.get('training_period') if model else None,
        'training_records': model.get('training_records', 0) if model else 0,
        'consumption_records': records, 'active_partners': partners,
        'products_with_history': products, 'stored_predictions': predictions,
        'evaluated_predictions': metrics['count'], 'evaluation_metrics': metrics,
        'validation_metrics': model.get('metrics') if model else None,
        'eligible_partner_products': pair_count,
        'insufficient_partner_products': model.get('insufficient_pairs', 0) if model else 'not_evaluated',
        'message': message,
    }


@router.post('/train')
def train(actor: User = Depends(require_permission('intelligence:train')), db: Session = Depends(get_db)):
    audit(db, actor.id, 'intelligence.training.started', 'intelligence', details={})
    db.commit()
    try:
        result = train_model(db, actor.id)
        action = 'intelligence.training.completed' if result['status'] == 'active' else 'intelligence.training.awaiting_data'
        audit(db, actor.id, action, 'intelligence', details={key: value for key, value in result.items() if key != 'artifact'})
        db.commit()
        return result
    except Exception as error:
        db.rollback()
        audit(db, actor.id, 'intelligence.training.failed', 'intelligence', details={'error_type': type(error).__name__})
        db.commit()
        raise HTTPException(status_code=500, detail='Training failed. Review backend logs and model storage configuration.') from error
