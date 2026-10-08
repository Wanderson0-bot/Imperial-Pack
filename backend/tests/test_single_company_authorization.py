import pytest
"""Role-based authorization without organization or tenant context."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.router import settings as auth_settings
from app.auth.security import create_access_token
from app.database.base import Base
from app.database.models import (
    InventoryBalance,
    Permission,
    Product,
    Role,
    RolePermission,
    User,
    UserSession,
)
from app.database.session import get_db
from app.main import app


@pytest.fixture
def single_company_api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(auth_settings, 'secret_key', 'single-company-api-test-secret-long-enough')

    def test_database():
        with factory() as session:
            yield session

    with factory() as db:
        permissions = {
            key: Permission(key=key, description=key)
            for key in ('products:read', 'inventory:read')
        }
        authorized_role = Role(name='authorized-reader')
        denied_role = Role(name='customer-only-reader')
        db.add_all([*permissions.values(), authorized_role, denied_role])
        db.flush()
        authorized_user = User(
            name='Authorized Reader',
            email='authorized-reader@example.com',
            role_id=authorized_role.id,
        )
        denied_user = User(
            name='Denied Reader',
            email='denied-reader@example.com',
            role_id=denied_role.id,
        )
        db.add_all([
            RolePermission(role_id=authorized_role.id, permission_id=permissions['products:read'].id),
            RolePermission(role_id=authorized_role.id, permission_id=permissions['inventory:read'].id),
        ])
        db.add_all([authorized_user, denied_user])
        db.flush()

        tokens = {}
        for key, user in (('authorized', authorized_user), ('denied', denied_user)):
            token, token_id, expires = create_access_token(user.id, 'single-company-api-test')
            db.add(UserSession(user_id=user.id, token_id=token_id, expires_at=expires))
            tokens[key] = token

        product = Product(
            name='Test product',
            unit='un',
            current_cost=1,
            current_price=2,
            minimum_stock=10,
        )
        db.add(product)
        db.flush()
        db.add(InventoryBalance(product_id=product.id, quantity=5))
        db.commit()
        product_id = product.id

    app.dependency_overrides[get_db] = test_database
    try:
        with TestClient(app) as client:
            yield client, tokens, product_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def test_authorization_uses_user_role_permissions_without_organization_header(single_company_api):
    client, tokens, _alert_id = single_company_api

    products = client.get('/api/products', headers=_headers(tokens['authorized']))
    assert products.status_code == 200
    assert [product['name'] for product in products.json()] == ['Test product']

    denied = client.get('/api/products', headers=_headers(tokens['denied']))
    assert denied.status_code == 403


def test_operational_alert_routes_work_without_organization_context(single_company_api):
    client, tokens, product_id = single_company_api
    headers = _headers(tokens['authorized'])

    alerts = client.get('/api/alerts', headers=headers)
    assert alerts.status_code == 200
    alert = next(
        (item for item in alerts.json() if item['entity_id'] == product_id),
        None,
    )
    assert alert is not None
    assert alert['alert_type'] == 'stock_below_minimum'

    unauthorized_update = client.patch(
        f"/api/alerts/{alert['id']}",
        json={'status': 'RESOLVED'},
        headers=headers,
    )
    assert unauthorized_update.status_code == 403


def test_organizations_api_is_not_registered(single_company_api):
    client, tokens, _alert_id = single_company_api
    response = client.get('/api/organizations', headers=_headers(tokens['authorized']))

    assert response.status_code == 404
