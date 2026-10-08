from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.router import settings as auth_settings
from app.auth.security import create_access_token
from app.database.base import Base
from app.database.models import AuditLog, Permission, PricingHistory, Product, Role, RolePermission, User, UserSession
from app.database.session import get_db
from app.main import app


@pytest.fixture
def pricing_api(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(auth_settings, 'secret_key', 'pricing-api-test-secret-long-enough')

    def test_database():
        with factory() as session:
            yield session

    with factory() as db:
        permission = Permission(key='pricing:approve', description='Approve prices')
        authorized_role = Role(name='pricing-authorized')
        denied_role = Role(name='pricing-denied')
        db.add_all([permission, authorized_role, denied_role])
        db.flush()
        authorized_user = User(name='Pricing User', email='pricing@example.com', role_id=authorized_role.id)
        denied_user = User(name='Denied User', email='denied-pricing@example.com', role_id=denied_role.id)
        db.add_all([
            RolePermission(role_id=authorized_role.id, permission_id=permission.id),
            authorized_user,
            denied_user,
        ])
        db.flush()
        tokens = {}
        for key, user in (('authorized', authorized_user), ('denied', denied_user)):
            token, token_id, expires = create_access_token(user.id, 'pricing-api-test-secret-long-enough')
            db.add(UserSession(user_id=user.id, token_id=token_id, expires_at=expires))
            tokens[key] = token
        product = Product(
            name='Pricing Test Product',
            unit='un',
            current_cost=Decimal('70'),
            current_price=Decimal('100'),
            minimum_stock=0,
        )
        db.add(product)
        db.commit()
        product_id = product.id

    app.dependency_overrides[get_db] = test_database
    try:
        with TestClient(app) as client:
            yield client, tokens, product_id, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def test_individual_recalculation_returns_only_requested_product_without_changing_price(pricing_api):
    client, tokens, product_id, factory = pricing_api

    response = client.post(
        f'/api/pricing/products/{product_id}/recalculate',
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 200
    review = response.json()
    assert review['product_id'] == product_id
    assert Decimal(review['suggested_price']) == Decimal('100.00')
    assert Decimal(review['current_price']) == Decimal('100')
    with factory() as db:
        product = db.get(Product, product_id)
        assert product.current_price == Decimal('100')
        assert db.scalar(select(PricingHistory.id).where(PricingHistory.product_id == product_id)) is None


def test_individual_recalculation_requires_pricing_approval_permission(pricing_api):
    client, tokens, product_id, _ = pricing_api

    response = client.post(
        f'/api/pricing/products/{product_id}/recalculate',
        headers=_headers(tokens['denied']),
    )

    assert response.status_code == 403


def test_individual_recalculation_returns_not_found_for_missing_product(pricing_api):
    client, tokens, _, _ = pricing_api

    response = client.post(
        '/api/pricing/products/missing-product/recalculate',
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 404


def test_individual_recommended_price_approval_updates_product_and_audit(pricing_api):
    client, tokens, product_id, factory = pricing_api

    response = client.post(
        '/api/pricing/approve',
        json={'product_id': product_id, 'new_price': '100.00'},
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 200
    assert Decimal(response.json()['current_price']) == Decimal('100.00')
    with factory() as db:
        product = db.get(Product, product_id)
        history = db.scalar(select(PricingHistory).where(PricingHistory.product_id == product_id))
        audit_entry = db.scalar(select(AuditLog).where(
            AuditLog.action == 'pricing.approve',
            AuditLog.entity_id == product_id,
        ))
        assert product.current_price == Decimal('100.00')
        assert history is not None
        assert history.source == 'APPROVED_SINGLE'
        assert audit_entry is not None
