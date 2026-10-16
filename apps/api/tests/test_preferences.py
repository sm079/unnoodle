from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import make_admin


def test_smart_queue_is_off_until_an_admin_turns_it_on(client: TestClient, engine: Engine) -> None:
    assert client.get("/preferences").json() == {"smart_queue": False}
    make_admin(engine, client.get("/auth/me").json()["id"])
    assert client.patch("/preferences", json={"smart_queue": True}).json() == {"smart_queue": True}
    assert client.get("/preferences").json() == {"smart_queue": True}


def test_a_setting_left_out_stays_as_it_is(client: TestClient, engine: Engine) -> None:
    make_admin(engine, client.get("/auth/me").json()["id"])
    client.patch("/preferences", json={"smart_queue": True})
    assert client.patch("/preferences", json={}).json() == {"smart_queue": True}


def test_only_an_admin_changes_settings_since_they_affect_everyone(client: TestClient) -> None:
    response = client.patch("/preferences", json={"smart_queue": True})
    assert response.status_code == 403
    assert client.get("/preferences").json() == {"smart_queue": False}
