import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.router import settings as auth_settings
from app.database.base import Base
from app.database.models import AuditLog, Permission, Role, RolePermission, User
from app.database.session import get_db
from app.main import app


@pytest.fixture
def users_api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def test_database():
        with factory() as session:
            yield session

    monkeypatch.setattr(auth_settings, 'initial_admin_email', 'owner@example.com')
    monkeypatch.setattr(auth_settings, 'secret_key', 'test-secret-key-for-user-security')
    app.dependency_overrides[get_db] = test_database
    with TestClient(app) as client:
        registered = client.post('/api/auth/register', json={
            'name': 'Initial Administrator',
            'email': 'owner@example.com',
            'password': 'long-enough-password',
        })
        assert registered.status_code == 201
        admin_login = client.post('/api/auth/login', json={'email': 'owner@example.com', 'password': 'long-enough-password'})
        assert admin_login.status_code == 200

        with factory() as db:
            role = Role(name='users-create', description='Create users')
            no_permission_role = Role(name='no-permissions')
            permission = db.scalar(select(Permission).where(Permission.key == 'users:create'))
            manage_permission = db.scalar(select(Permission).where(Permission.key == 'users:manage'))
            db.add_all([role, no_permission_role])
            db.flush()
            db.add_all([
                RolePermission(role_id=role.id, permission_id=permission.id),
                RolePermission(role_id=role.id, permission_id=manage_permission.id),
            ])
            db.commit()
            role_id = role.id
            no_permission_role_id = no_permission_role.id

        yield client, role_id, no_permission_role_id, factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def create_user(client: TestClient, role_id: str, email: str, is_general_admin: bool = False):
    return client.post('/api/users', json={
        'name': 'Test User',
        'email': email,
        'password': 'long-enough-password',
        'role_id': role_id,
        'is_general_admin': is_general_admin,
    })


def test_user_without_create_permission_cannot_promote_user(users_api):
    client, role_id, no_permission_role_id, _ = users_api
    created = create_user(client, no_permission_role_id, 'ordinary@example.com')
    assert created.status_code == 201
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={'email': 'ordinary@example.com', 'password': 'long-enough-password'}).status_code == 200

    promoted = create_user(client, role_id, 'unauthorized@example.com', is_general_admin=True)

    assert promoted.status_code == 403


def test_user_with_create_permission_cannot_promote_user(users_api):
    client, role_id, _, _ = users_api
    created = create_user(client, role_id, 'operator@example.com')
    assert created.status_code == 201
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={'email': 'operator@example.com', 'password': 'long-enough-password'}).status_code == 200

    promoted = create_user(client, role_id, 'unauthorized-admin@example.com', is_general_admin=True)

    assert promoted.status_code == 403


def test_general_admin_can_create_another_general_admin(users_api):
    client, role_id, _, _ = users_api

    created = create_user(client, role_id, 'second-admin@example.com', is_general_admin=True)

    assert created.status_code == 201
    assert created.json()['is_general_admin'] is True


def test_general_admin_can_still_create_a_regular_user(users_api):
    client, role_id, _, _ = users_api

    created = create_user(client, role_id, 'regular@example.com')

    assert created.status_code == 201
    assert created.json()['is_general_admin'] is False


def test_general_admin_can_remove_user_and_preserve_audit(users_api):
    client, role_id, _, factory = users_api
    created = create_user(client, role_id, 'remove-me@example.com')
    user_id = created.json()['id']

    removed = client.delete(f'/api/users/{user_id}')

    assert removed.status_code == 204
    assert all(user['id'] != user_id for user in client.get('/api/users').json())
    assert client.post('/api/auth/login', json={
        'email': 'remove-me@example.com',
        'password': 'long-enough-password',
    }).status_code == 401
    with factory() as db:
        audit_entry = db.scalar(select(AuditLog).where(
            AuditLog.action == 'users.delete',
            AuditLog.entity_id == user_id,
        ))
        actor = db.scalar(select(User).where(User.email == 'owner@example.com'))
        assert audit_entry is not None
        assert audit_entry.actor_id == actor.id
        assert audit_entry.details['email'] == 'remove-me@example.com'


def test_non_general_admin_cannot_remove_user_even_with_users_manage(users_api):
    client, role_id, _, _ = users_api
    target = create_user(client, role_id, 'target@example.com')
    operator = create_user(client, role_id, 'operator@example.com')
    assert target.status_code == 201
    assert operator.status_code == 201
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={
        'email': 'operator@example.com',
        'password': 'long-enough-password',
    }).status_code == 200

    removed = client.delete(f"/api/users/{target.json()['id']}")

    assert removed.status_code == 403


def test_general_admin_cannot_remove_own_account(users_api):
    client, _, _, _ = users_api
    owner_id = next(
        user['id'] for user in client.get('/api/users').json()
        if user['email'] == 'owner@example.com'
    )

    removed = client.delete(f'/api/users/{owner_id}')

    assert removed.status_code == 409