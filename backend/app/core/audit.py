from sqlalchemy.orm import Session
from app.database.models import AuditLog


def audit(db: Session, actor_id: str | None, action: str, entity_type: str, entity_id: str | None = None, details: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))
