import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_a_strong_secret_key():
    with pytest.raises(ValidationError, match='SECRET_KEY must contain at least 32 bytes'):
        Settings(environment='production', secret_key='short', cookie_secure=True)


def test_production_requires_secure_cookies():
    with pytest.raises(ValidationError, match='COOKIE_SECURE must be true in production'):
        Settings(environment='production', secret_key='a' * 32, cookie_secure=False)


def test_development_allows_a_short_local_secret():
    settings = Settings(environment='development', secret_key='local-test-key')

    assert settings.secret_key == 'local-test-key'
