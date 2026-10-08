from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    return bool(hashed) and password_hash.verify(password, hashed)


def create_access_token(user_id: str, session_id: str) -> tuple[str, str, datetime]:
    settings = get_settings()
    if not settings.secret_key:
        raise HTTPException(status_code=503, detail='SECRET_KEY is not configured.')
    token_id = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {'sub': user_id, 'sid': session_id, 'jti': token_id, 'iat': datetime.now(timezone.utc), 'exp': expires}
    return jwt.encode(payload, settings.secret_key, algorithm='HS256'), token_id, expires


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    if not settings.secret_key:
        raise HTTPException(status_code=503, detail='SECRET_KEY is not configured.')
    try:
        return jwt.decode(token, settings.secret_key, algorithms=['HS256'])
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired session.') from error
