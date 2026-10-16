from fastapi.testclient import TestClient


def test_smart_queue_is_off_until_turned_on(client: TestClient) -> None:
    assert client.get("/preferences").json() == {"smart_queue": False}
    assert client.patch("/preferences", json={"smart_queue": True}).json() == {"smart_queue": True}
    assert client.get("/preferences").json() == {"smart_queue": True}


def test_a_setting_left_out_stays_as_it_is(client: TestClient) -> None:
    client.patch("/preferences", json={"smart_queue": True})
    assert client.patch("/preferences", json={}).json() == {"smart_queue": True}
