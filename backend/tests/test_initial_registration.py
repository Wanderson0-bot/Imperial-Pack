import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.router import settings as auth_settings
from app.database.base import Base
from app.database.session import get_db
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def test_database():
        with factory() as session:
            yield session

    monkeypatch.setattr(auth_settings, 'initial_admin_email', 'owner@example.com')
    monkeypatch.setattr(auth_settings, 'secret_key', 'test-secret-key-for-initial-registration')
    monkeypatch.setattr(auth_settings, 'cookie_samesite', 'none')
    monkeypatch.setattr(auth_settings, 'cookie_secure', None)
    monkeypatch.setattr(auth_settings, 'environment', 'development')
    app.dependency_overrides[get_db] = test_database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def test_initial_registration_is_allowlisted_and_only_available_once(client):
    status = client.get('/api/auth/setup-status')
    assert status.json() == {
        'initial_registration_available': True,
        'google_oauth_configured': False,
    }
    assert client.get('/api/auth/google').status_code == 503

    rejected = client.post('/api/auth/register', json={
        'name': 'Unauthorized',
        'email': 'other@example.com',
        'password': 'long-enough-password',
    })
    assert rejected.status_code == 403

    created = client.post('/api/auth/register', json={
        'name': 'Initial Administrator',
        'email': 'owner@example.com',
        'password': 'long-enough-password',
    })
    assert created.status_code == 201
    assert created.json()['is_general_admin'] is True

    assert client.get('/api/auth/setup-status').json() == {
        'initial_registration_available': False,
        'google_oauth_configured': False,
    }
    repeated = client.post('/api/auth/register', json={
        'name': 'Second User',
        'email': 'owner@example.com',
        'password': 'another-long-password',
    })
    assert repeated.status_code == 409

    login = client.post('/api/auth/login', json={
        'email': 'owner@example.com',
        'password': 'long-enough-password',
    })
    assert login.status_code == 200
    cookie = login.headers['set-cookie'].lower()
    assert 'httponly' in cookie
    assert 'samesite=none' in cookie
    assert 'secure' in cookie

    session_cookie = f"ip_access={login.json()['access_token']}"
    current_user = client.get('/api/auth/me', headers={'Cookie': session_cookie})
    assert current_user.status_code == 200
    assert current_user.json()['email'] == 'owner@example.com'

    logout = client.post('/api/auth/logout', headers={'Cookie': session_cookie})
    assert logout.status_code == 204
    revoked_user = client.get('/api/auth/me', headers={'Cookie': session_cookie})
    assert revoked_user.status_code == 401


def test_cors_allows_local_frontend_with_credentials(client):
    response = client.options('/api/auth/login', headers={
        'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type,authorization',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert response.headers['access-control-allow-credentials'] == 'true'
    assert 'authorization' in response.headers['access-control-allow-headers'].lower()