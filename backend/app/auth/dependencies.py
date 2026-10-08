from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import get_db, set_auth_lookup_context, set_user_context
from app.database.models import Permission, RolePermission, User, UserSession
from app.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login', auto_error=False)


def current_user(request: Request, token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    token = token or request.cookies.get('ip_access')
    if not token:
        raise HTTPException(status_code=401, detail='Authentication required.')
    claims = decode_access_token(token)
    set_auth_lookup_context(db, True)
    session = db.scalar(select(UserSession).where(UserSession.token_id == claims.get('jti'), UserSession.user_id == claims.get('sub'), UserSession.revoked_at.is_(None)))
    user = db.get(User, claims.get('sub'))
    if not session or not user or not user.is_active:
        raise HTTPException(status_code=401, detail='Session is not active.')
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail='Session is not active.')
    set_auth_lookup_context(db, False)
    set_user_context(db, user.id, user.is_general_admin)
    return user


def require_permission(permission_key: str):
    def dependency(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
        if user.is_general_admin:
            return user
        role_id = user.role_id
        if not role_id:
            raise HTTPException(status_code=403, detail='Permission denied.')
        has_permission = db.scalar(
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id, Permission.key == permission_key)
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail='Permission denied.')
        return user
    return dependency


def user_permission_keys(db: Session, user: User) -> list[str]:
    if not user.role_id:
        return []
    return list(db.scalars(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == user.role_id)
        .order_by(Permission.key)
    ))
