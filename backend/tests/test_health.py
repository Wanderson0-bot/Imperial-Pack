from fastapi.testclient import TestClient

from app import main


def test_health_checks_database_connection(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement):
            assert str(statement) == 'SELECT 1'

    class Engine:
        def connect(self):
            return Connection()

    monkeypatch.setattr(main.settings, 'database_url', 'postgresql+psycopg://test')
    monkeypatch.setattr(main, 'get_engine', Engine)
    response = TestClient(main.app).get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['database_configured'] is True
    assert data['database_connected'] is True
    assert isinstance(data['authentication_configured'], bool)


def test_health_reports_database_connection_failure(monkeypatch):
    from sqlalchemy.exc import OperationalError

    class Engine:
        def connect(self):
            raise OperationalError('SELECT 1', {}, Exception('unavailable'))

    monkeypatch.setattr(main.settings, 'database_url', 'postgresql+psycopg://test')
    monkeypatch.setattr(main, 'get_engine', Engine)
    response = TestClient(main.app).get('/health')
    assert response.status_code == 200
    assert response.json()['database_connected'] is False
