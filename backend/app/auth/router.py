from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.audit import audit
from app.core.config import get_settings
from app.database.models import Permission, Role, RolePermission, User, UserSession
from app.database.session import get_db, set_auth_lookup_context, set_bootstrap_context, set_user_context
from app.auth.bootstrap import PERMISSIONS
from app.auth.dependencies import current_user, oauth2_scheme, user_permission_keys
from app.auth.security import decode_access_token
from app.auth.schemas import InitialRegistrationInput, LoginInput, TokenOutput, UserOutput
from app.auth.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix='/auth', tags=['auth'])
oauth = OAuth()
settings = get_settings()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name='google', client_id=settings.google_client_id, client_secret=settings.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


def issue_session(user: User, db: Session) -> TokenOutput:
    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    token, token_id, expires = create_access_token(user.id, 'web')
    set_user_context(db, user.id, user.is_general_admin)
    db.add(UserSession(user_id=user.id, token_id=token_id, expires_at=expires))
    user.last_login_at = datetime.now(timezone.utc)
    audit(db, user.id, 'auth.login', 'user', user.id)
    db.commit()
    return TokenOutput(access_token=token, expires_in=int((expires - expires_at).total_seconds()))

def user_output(user: User, db: Session) -> UserOutput:
    role = db.get(Role, user.role_id)
    return UserOutput(
        id=user.id,
        name=user.name,
        email=user.email,
        role=role.name if role else '',
        permissions=user_permission_keys(db, user),
        is_general_admin=user.is_general_admin,
    )


@router.get('/setup-status')
def setup_status(db: Session = Depends(get_db)) -> dict[str, bool]:
    set_auth_lookup_context(db, True)
    available = settings.bootstrap_admin_email is not None and db.scalar(select(User.id).limit(1)) is None
    set_auth_lookup_context(db, False)
    return {
        'initial_registration_available': available,
        'google_oauth_configured': bool(
            settings.google_client_id
            and settings.google_client_secret
            and settings.google_redirect_uri
        ),
    }


@router.post('/register', response_model=UserOutput, status_code=201)
def register_initial_admin(payload: InitialRegistrationInput, db: Session = Depends(get_db)) -> UserOutput:
    expected_email = settings.bootstrap_admin_email
    if not expected_email:
        raise HTTPException(status_code=403, detail='Initial registration is not configured.')
    if str(payload.email).lower() != expected_email:
        raise HTTPException(status_code=403, detail='This email is not authorized for initial registration.')
    set_auth_lookup_context(db, True)
    set_bootstrap_context(db, True)
    if db.bind and db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:lock_key)'), {'lock_key': 731204918})
    if db.scalar(select(User.id).limit(1)):
        raise HTTPException(status_code=409, detail='Initial registration is already complete.')

    admin_role = db.scalar(select(Role).where(Role.name == 'general_admin', Role.is_system.is_(True)))
    if admin_role is None:
        admin_role = Role(name='general_admin', description='Sócio administrador geral', is_system=True)
        db.add(admin_role)
        db.flush()

    existing_permissions = {permission.key for permission in db.scalars(select(Permission))}
    missing_permissions = [Permission(key=key, description=description) for key, description in PERMISSIONS.items() if key not in existing_permissions]
    if missing_permissions:
        db.add_all(missing_permissions)
        db.flush()

    all_permissions = list(db.scalars(select(Permission)))
    db.add_all(RolePermission(role_id=admin_role.id, permission_id=permission.id) for permission in all_permissions)

    user = User(name=payload.name.strip(), email=expected_email, password_hash=hash_password(payload.password), role_id=admin_role.id, is_active=True, is_general_admin=True)
    db.add(user)
    db.flush()
    set_user_context(db, user.id, user.is_general_admin)
    set_auth_lookup_context(db, False)
    set_bootstrap_context(db, False)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail='Initial registration is already complete.') from error
    db.refresh(user)
    return user_output(user, db)


@router.post('/login', response_model=TokenOutput)
def login(payload: LoginInput, response: Response, request: Request, db: Session = Depends(get_db)) -> TokenOutput:
    set_auth_lookup_context(db, True)
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials or inactive account.')
    issued = issue_session(user, db)
    response.set_cookie('ip_access', issued.access_token, httponly=True, secure=settings.secure_cookies, samesite=settings.cookie_samesite, max_age=issued.expires_in)
    return issued


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, token: str | None = Depends(oauth2_scheme), user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    token = token or request.cookies.get('ip_access')
    if token:
        claims = decode_access_token(token)
        session = db.scalar(select(UserSession).where(UserSession.token_id == claims.get('jti'), UserSession.user_id == user.id))
        if session:
            session.revoked_at = datetime.now(timezone.utc)
    audit(db, user.id, 'auth.logout', 'user', user.id)
    db.commit()
    response.delete_cookie('ip_access', httponly=True, secure=settings.secure_cookies, samesite=settings.cookie_samesite)
    response.status_code = 204
    return response


@router.get('/me', response_model=UserOutput)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserOutput:
    return user_output(user, db)


@router.get('/google')
async def google_login(request: Request):
    if not (settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri):
        raise HTTPException(status_code=503, detail='Google OAuth is not configured.')
    return await oauth.google.authorize_redirect(request, settings.google_redirect_uri)


@router.get('/google/callback', name='google_callback')
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not (settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri):
        raise HTTPException(status_code=503, detail='Google OAuth is not configured.')
    token = await oauth.google.authorize_access_token(request)
    claims = token.get('userinfo') or await oauth.google.userinfo(token=token)
    email = str(claims.get('email', '')).lower()
    if not claims.get('email_verified') or email not in settings.allowed_emails:
        raise HTTPException(status_code=403, detail='This Google account is not authorized.')
    set_auth_lookup_context(db, True)
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=403, detail='No active Imperial Pack account is assigned to this email.')
    issued = issue_session(user, db)
    destination = RedirectResponse(settings.cors_origins[0])
    destination.set_cookie('ip_access', issued.access_token, httponly=True, secure=settings.secure_cookies, samesite=settings.cookie_samesite, max_age=issued.expires_in)
    return destination
