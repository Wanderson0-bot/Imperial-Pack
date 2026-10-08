from collections.abc import Generator
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import get_settings

_engine = None
_session_factory = None


def set_user_context(session: Session, user_id: str, is_general_admin: bool = False) -> None:
    session.info['user_id'] = user_id
    session.info['is_general_admin'] = is_general_admin
    if session.bind and session.bind.dialect.name == 'postgresql':
        session.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {'user_id': user_id})
        session.execute(text("SELECT set_config('app.is_general_admin', :is_admin, true)"), {'is_admin': 'true' if is_general_admin else 'false'})


def set_auth_lookup_context(session: Session, enabled: bool) -> None:
    session.info['auth_lookup'] = enabled
    if session.bind and session.bind.dialect.name == 'postgresql':
        session.execute(text("SELECT set_config('app.auth_lookup', :enabled, true)"), {'enabled': 'true' if enabled else 'false'})


def set_bootstrap_context(session: Session, enabled: bool) -> None:
    session.info['bootstrap'] = enabled
    if session.bind and session.bind.dialect.name == 'postgresql':
        session.execute(text("SELECT set_config('app.bootstrap', :enabled, true)"), {'enabled': 'true' if enabled else 'false'})


def get_engine():
    global _engine, _session_factory
    url = get_settings().database_url
    if not url:
        raise HTTPException(status_code=503, detail='DATABASE_URL is not configured.')
    if _engine is None:
        _engine = create_engine(url, pool_pre_ping=True)
        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_db() -> Generator[Session, None, None]:
    get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
