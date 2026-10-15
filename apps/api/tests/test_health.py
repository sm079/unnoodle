from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

# Nothing listens on port 1, so connections are refused straight away, like a database that is down
UNREACHABLE_DB = "postgresql+psycopg://unnoodle:unnoodle@127.0.0.1:1/unnoodle"


def client(database_url: str) -> TestClient:
    return TestClient(create_app(Settings(database_url=database_url)))


def test_health_reports_a_database_that_is_down() -> None:
    with client(UNREACHABLE_DB) as c:
        response = c.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "down"}


def test_health_reports_a_reachable_database(test_database_url: str) -> None:
    with client(test_database_url) as c:
        response = c.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
