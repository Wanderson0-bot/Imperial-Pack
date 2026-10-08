from sqlalchemy import func, select
from sqlalchemy.orm import Session


def lock_idempotency_key(db: Session, namespace: str, key: str) -> None:
    if db.bind is not None and db.bind.dialect.name == 'postgresql':
        db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f'{namespace}:{key}', 0))))