from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user, user_permission_keys
from app.core.audit import audit
from app.database.models import PartnerAlert, PartnerOpportunity, User
from app.database.session import get_db
from app.alerts.service import ENTITY_SCOPE, accessible_scopes, refresh_operational_signals

router = APIRouter(tags=['operational-signals'])


class StatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=20)


def _allowed_scopes(db: Session, user: User) -> set[str]:
    scopes = accessible_scopes(db, user)
    if not scopes:
        raise HTTPException(status_code=403, detail='Permission denied.')
    return scopes


def _can_manage(db: Session, user: User, entity_type: str) -> bool:
    if user.is_general_admin:
        return True
    permissions = set(user_permission_keys(db, user))
    if 'alerts:manage' in permissions or 'opportunities:manage' in permissions:
        return True
    write_permission = {
        'inventory_product': 'inventory:adjust',
        'payable': 'finance:write',
        'receivable': 'finance:write',
        'customer': 'customers:update',
        'partner': 'partners:conditions',
    }.get(entity_type)
    return write_permission in permissions


@router.get('/alerts')
def list_alerts(status: str = Query(default='OPEN'), user: User = Depends(current_user), db: Session = Depends(get_db)):
    scopes = _allowed_scopes(db, user)
    _, entities = refresh_operational_signals(db, scopes)
    priority_order = case((PartnerAlert.priority == 'high', 0), (PartnerAlert.priority == 'medium', 1), else_=2)
    records = db.scalars(select(PartnerAlert).where(PartnerAlert.dedupe_key.is_not(None), PartnerAlert.entity_type.in_(entities), PartnerAlert.status == status).order_by(priority_order, PartnerAlert.detected_at.desc()))
    return list(records)


@router.get('/alerts/{alert_id}')
def get_alert(alert_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scopes = _allowed_scopes(db, user)
    _, entities = refresh_operational_signals(db, scopes)
    record = db.get(PartnerAlert, alert_id)
    if record is None or record.dedupe_key is None or record.entity_type not in entities:
        raise HTTPException(status_code=404, detail='Alert not found.')
    return record


@router.patch('/alerts/{alert_id}')
def update_alert(alert_id: str, payload: StatusUpdate, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.status not in {'OPEN', 'RESOLVED', 'IGNORED'}:
        raise HTTPException(status_code=422, detail='Invalid alert status.')
    scopes = _allowed_scopes(db, actor)
    record = db.get(PartnerAlert, alert_id)
    if record is None or record.entity_type not in ENTITY_SCOPE or ENTITY_SCOPE[record.entity_type] not in scopes:
        raise HTTPException(status_code=404, detail='Alert not found.')
    if not _can_manage(db, actor, record.entity_type):
        raise HTTPException(status_code=403, detail='Permission denied.')
    previous = record.status
    record.status = payload.status
    record.resolved_at = datetime.now(timezone.utc) if payload.status != 'OPEN' else None
    audit(db, actor.id, 'alerts.status.update', 'alert', record.id, {'from': previous, 'to': payload.status})
    db.commit()
    db.refresh(record)
    return record


@router.get('/opportunities')
def list_opportunities(status: str = Query(default='OPEN'), user: User = Depends(current_user), db: Session = Depends(get_db)):
    scopes = _allowed_scopes(db, user)
    history_available, entities = refresh_operational_signals(db, scopes)
    records = list(db.scalars(select(PartnerOpportunity).where(PartnerOpportunity.entity_type.in_(entities), PartnerOpportunity.status == status).order_by(PartnerOpportunity.created_at.desc())))
    return {'status': 'ready' if history_available or records else 'insufficient_data', 'items': records}


@router.get('/opportunities/{opportunity_id}')
def get_opportunity(opportunity_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scopes = _allowed_scopes(db, user)
    _, entities = refresh_operational_signals(db, scopes)
    record = db.get(PartnerOpportunity, opportunity_id)
    if record is None or record.dedupe_key is None or record.entity_type not in entities:
        raise HTTPException(status_code=404, detail='Opportunity not found.')
    return record


@router.patch('/opportunities/{opportunity_id}')
def update_opportunity(opportunity_id: str, payload: StatusUpdate, actor: User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.status not in {'OPEN', 'DISMISSED', 'ACTIONED'}:
        raise HTTPException(status_code=422, detail='Invalid opportunity status.')
    scopes = _allowed_scopes(db, actor)
    record = db.get(PartnerOpportunity, opportunity_id)
    if record is None or record.entity_type not in ENTITY_SCOPE or ENTITY_SCOPE[record.entity_type] not in scopes:
        raise HTTPException(status_code=404, detail='Opportunity not found.')
    if not _can_manage(db, actor, record.entity_type):
        raise HTTPException(status_code=403, detail='Permission denied.')
    previous = record.status
    record.status = payload.status
    audit(db, actor.id, 'opportunities.status.update', 'opportunity', record.id, {'from': previous, 'to': payload.status})
    db.commit()
    db.refresh(record)
    return record