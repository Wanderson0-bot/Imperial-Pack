from decimal import Decimal

import pytest
from pydantic import ValidationError
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
from app.products.schemas import ProductCreate, ProductUpdate


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
        product_create_permission = Permission(key='products:create', description='Create products')
        authorized_role = Role(name='pricing-authorized')
        denied_role = Role(name='pricing-denied')
        db.add_all([permission, product_create_permission, authorized_role, denied_role])
        db.flush()
        authorized_user = User(name='Pricing User', email='pricing@example.com', role_id=authorized_role.id)
        denied_user = User(name='Denied User', email='denied-pricing@example.com', role_id=denied_role.id)
        db.add_all([
            RolePermission(role_id=authorized_role.id, permission_id=permission.id),
            RolePermission(role_id=authorized_role.id, permission_id=product_create_permission.id),
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


def test_recommendation_rounding_never_exceeds_maximum_markup(pricing_api):
    client, tokens, product_id, factory = pricing_api
    with factory() as db:
        product = db.get(Product, product_id)
        product.current_cost = Decimal('70.02')
        product.target_margin_percent = Decimal('50')
        db.commit()

    response = client.post(
        f'/api/pricing/products/{product_id}/recalculate',
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 200
    review = response.json()
    assert Decimal(review['suggested_price']) == Decimal('140.04')
    assert Decimal(review['suggested_price']) <= Decimal(review['maximum_price'])


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


def test_negative_target_margin_is_valid_but_stays_within_numeric_and_markup_limits():
    created = ProductCreate(
        name='Loss Product',
        unit='un',
        current_cost=Decimal('70'),
        current_price=Decimal('60'),
        target_margin_percent=Decimal('-25'),
        minimum_stock=0,
    )
    assert created.target_margin_percent == Decimal('-25')
    assert ProductUpdate(target_margin_percent=Decimal('-25')).target_margin_percent == Decimal('-25')
    assert ProductUpdate(target_margin_percent=Decimal('50')).target_margin_percent == Decimal('50')

    with pytest.raises(ValidationError):
        ProductUpdate(target_margin_percent=Decimal('-10000'))
    with pytest.raises(ValidationError):
        ProductUpdate(target_margin_percent=Decimal('50.0001'))


def test_approved_price_below_cost_allows_negative_margin(pricing_api):
    client, tokens, product_id, factory = pricing_api

    response = client.post(
        '/api/pricing/approve',
        json={'product_id': product_id, 'new_price': '60.00'},
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 200
    assert Decimal(response.json()['margin_percent']) == Decimal('-16.6667')
    with factory() as db:
        assert db.get(Product, product_id).current_price == Decimal('60.00')


def test_product_creation_allows_negative_margin_and_custom_negative_target(pricing_api):
    client, tokens, _, _ = pricing_api

    response = client.post(
        '/api/products',
        json={
            'name': 'Loss Product',
            'unit': 'un',
            'current_cost': '70.00',
            'current_price': '60.00',
            'target_margin_percent': '-25',
            'minimum_stock': '0',
        },
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()['margin_percent']) == Decimal('-16.6667')
    assert Decimal(response.json()['target_margin_percent']) == Decimal('-25')


def test_product_creation_still_rejects_price_above_maximum_markup(pricing_api):
    client, tokens, _, _ = pricing_api

    response = client.post(
        '/api/products',
        json={
            'name': 'Over-cap Product',
            'unit': 'un',
            'current_cost': '70.00',
            'current_price': '140.01',
            'target_margin_percent': '30',
            'minimum_stock': '0',
        },
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 422


def test_approved_price_still_observes_maximum_markup(pricing_api):
    client, tokens, product_id, _ = pricing_api

    response = client.post(
        '/api/pricing/approve',
        json={'product_id': product_id, 'new_price': '140.01'},
        headers=_headers(tokens['authorized']),
    )

    assert response.status_code == 422
