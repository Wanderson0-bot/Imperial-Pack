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
def planning_client(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def test_database():
        with factory() as session:
            yield session

    monkeypatch.setattr(auth_settings, 'initial_admin_email', 'planning-owner@example.com')
    monkeypatch.setattr(auth_settings, 'secret_key', 'test-secret-key-for-planning-suite')
    monkeypatch.setattr(auth_settings, 'cookie_samesite', 'lax')
    monkeypatch.setattr(auth_settings, 'cookie_secure', None)
    monkeypatch.setattr(auth_settings, 'environment', 'development')
    app.dependency_overrides[get_db] = test_database
    with TestClient(app) as client:
        registered = client.post('/api/auth/register', json={
            'name': 'Planning Owner', 'email': 'planning-owner@example.com', 'password': 'long-enough-password',
        })
        assert registered.status_code == 201
        login = client.post('/api/auth/login', json={'email': 'planning-owner@example.com', 'password': 'long-enough-password'})
        assert login.status_code == 200
        yield client, factory
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def create_plan(client, **overrides):
    payload = {
        'title': 'Reposição planejada', 'category': 'inventory', 'priority': 'high',
        'start_date': '2026-10-01', 'due_date': '2026-10-31',
        'tasks': [{'title': 'Conferir saldo', 'sort_order': 0}, {'title': 'Validar fornecedor', 'sort_order': 1}],
    }
    payload.update(overrides)
    return client.post('/api/planning', json=payload)


def test_planning_requires_authentication_and_permission(planning_client):
    client, _ = planning_client
    assert client.get('/api/planning').status_code == 200
    cors_success = client.get('/api/planning/goals', headers={'Origin': 'https://imperial-pack.vercel.app'})
    assert cors_success.status_code == 200
    assert cors_success.headers['access-control-allow-origin'] == 'https://imperial-pack.vercel.app'
    assert cors_success.headers['access-control-allow-credentials'] == 'true'
    client.post('/api/auth/logout')
    unauthenticated = client.get('/api/planning', headers={'Origin': 'https://imperial-pack.vercel.app'})
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers['access-control-allow-origin'] == 'https://imperial-pack.vercel.app'


def test_create_update_complete_plan_and_task_progress(planning_client):
    client, _ = planning_client
    created = create_plan(client)
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan['progress_percent'] == 0
    assert plan['task_count'] == 2

    task_id = plan['tasks'][0]['id']
    completed = client.patch(f"/api/planning/tasks/{task_id}", json={'status': 'completed'})
    assert completed.status_code == 200
    fetched = client.get(f"/api/planning/{plan['id']}").json()
    assert fetched['progress_percent'] == 50
    assert fetched['tasks'][0]['completed_at'] is not None

    reopened = client.patch(f"/api/planning/tasks/{task_id}", json={'status': 'pending'})
    assert reopened.status_code == 200
    fetched = client.get(f"/api/planning/{plan['id']}").json()
    assert fetched['progress_percent'] == 0
    assert fetched['tasks'][0]['completed_at'] is None

    updated = client.patch(f"/api/planning/{plan['id']}", json={'title': 'Reposição revisada', 'status': 'completed'})
    assert updated.status_code == 200
    assert updated.json()['title'] == 'Reposição revisada'
    assert updated.json()['status'] == 'completed'


def test_planning_validates_dates_filters_and_archive(planning_client):
    client, _ = planning_client
    invalid = create_plan(client, start_date='2026-11-01', due_date='2026-10-31')
    assert invalid.status_code == 422
    first = create_plan(client, title='Compra de embalagens', due_date='2026-10-30')
    second = create_plan(client, title='Revisar estoque', due_date='2026-11-15', tasks=[])
    assert first.status_code == second.status_code == 201
    filtered = client.get('/api/planning?category=inventory&priority=high&due_from=2026-10-20&due_to=2026-10-31&search=embalagens')
    assert [row['title'] for row in filtered.json()] == ['Compra de embalagens']
    archived = client.patch(f"/api/planning/{first.json()['id']}", json={'archived': True})
    assert archived.status_code == 200 and archived.json()['archived'] is True
    assert all(row['id'] != first.json()['id'] for row in client.get('/api/planning').json())
    assert any(row['id'] == first.json()['id'] for row in client.get('/api/planning?include_archived=true').json())
    assert second.json()['progress_percent'] == 0


def test_goals_create_update_validate_and_link_to_plan(planning_client):
    client, _ = planning_client
    plan = create_plan(client, tasks=[]).json()
    invalid = client.post('/api/planning/goals', json={'name': 'Receita mensal', 'category': 'finance', 'target_value': 1000, 'current_value': 2, 'unit': 'R$', 'status': 'completed'})
    assert invalid.status_code == 422

    created = client.post('/api/planning/goals', json={'name': 'Clientes conquistados', 'category': 'customers', 'initial_value': 0, 'target_value': 10, 'current_value': 2, 'unit': 'clientes', 'planning_id': plan['id'], 'start_date': '2026-10-01', 'due_date': '2026-11-01'})
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal['progress_percent'] == 20
    changed = client.patch(f"/api/planning/goals/{goal['id']}", json={'current_value': 10, 'status': 'completed'})
    assert changed.status_code == 200
    assert changed.json()['progress_percent'] == 100
    assert changed.json()['status'] == 'completed'


def test_templates_create_independent_plan_tasks(planning_client):
    client, _ = planning_client
    template = next(row for row in client.get('/api/planning/templates').json() if row['key'] == 'stock_replenishment')
    payload = {'title': template['title'], 'description': template['description'], 'category': template['category'], 'tasks': [{'title': title, 'sort_order': index} for index, title in enumerate(template['tasks'])]}
    first = client.post('/api/planning', json=payload).json()
    second = client.post('/api/planning', json=payload).json()
    assert first['id'] != second['id']
    assert set(task['id'] for task in first['tasks']).isdisjoint(task['id'] for task in second['tasks'])
    assert len(first['tasks']) == len(template['tasks'])


def test_low_stock_opportunity_uses_persisted_inventory_and_can_be_dismissed(planning_client):
    client, _ = planning_client
    product = client.post('/api/products', json={'name': 'Produto para oportunidade', 'category_id': None, 'unit': 'un', 'current_cost': 2, 'current_price': 4, 'minimum_stock': 4})
    assert product.status_code == 201, product.text
    assert client.get('/api/products').status_code == 200
    product_id = product.json()['id']
    suggestions = client.get('/api/planning/opportunities').json()
    suggestion = next(item for item in suggestions if item['entity_id'] == product_id)
    assert 'abaixo do mínimo' in suggestion['reason']
    assert client.post(f'/api/planning/opportunities/{product_id}/dismiss').status_code == 204
    assert all(item['entity_id'] != product_id for item in client.get('/api/planning/opportunities').json())


def test_planning_role_without_permission_is_forbidden(planning_client):
    client, _ = planning_client
    role = client.post('/api/users/roles', json={'name': 'planning-denied', 'permissions': []})
    assert role.status_code == 201
    user = client.post('/api/users', json={'name': 'Planning Viewer', 'email': 'planning-viewer@example.com', 'password': 'long-enough-password', 'role_id': role.json()['id']})
    assert user.status_code == 201
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login', json={'email': 'planning-viewer@example.com', 'password': 'long-enough-password'}).status_code == 200
    assert client.get('/api/planning').status_code == 403
