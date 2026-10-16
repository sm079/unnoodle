import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app import users
from app.accounts import COOKIE
from app.main import create_app
from app.models import FailedSignIn, User, UserSession
from app.settings import Settings
from tests.conftest import sign_up


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Signed out."""
    with TestClient(create_app(settings)) as client:
        yield client


def sign_in(client: TestClient, email: str = "me@example.com", password: str = "correct horse") -> int:
    return client.post("/auth/sign-in", json={"email": email, "password": password}).status_code


def test_signing_up_signs_you_in(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    user_id = sign_up(client, email="  Me@Example.com ")
    assert client.get("/auth/me").json() == {"id": user_id, "email": "me@example.com", "is_admin": False}


def test_the_cookie_is_out_of_reach_of_scripts_and_other_sites(client: TestClient) -> None:
    response = client.post("/auth/sign-up", json={"email": "me@example.com", "password": "correct horse"})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    # On plain http here; Secure is a setting for where the app is served over HTTPS
    assert "secure" not in cookie.replace("samesite", "")


def test_the_cookie_is_secure_when_set_to_be(settings: Settings) -> None:
    with TestClient(create_app(settings.model_copy(update={"secure_cookies": True}))) as client:
        response = client.post("/auth/sign-up", json={"email": "me@example.com", "password": "correct horse"})
    assert "; secure" in response.headers["set-cookie"].lower()


def test_an_email_has_one_account_however_it_is_typed(client: TestClient) -> None:
    sign_up(client)
    response = client.post("/auth/sign-up", json={"email": "ME@example.com", "password": "another one"})
    assert (response.status_code, response.json()["detail"]) == (409, "There's already an account with that email")


@pytest.mark.parametrize(
    ("email", "password"),
    [("not an email", "correct horse"), ("me@example", "correct horse"), ("me@example.com", "short")],
)
def test_sign_up_needs_an_email_and_a_long_enough_password(client: TestClient, email: str, password: str) -> None:
    assert client.post("/auth/sign-up", json={"email": email, "password": password}).status_code == 422


def test_signing_out_and_back_in(client: TestClient) -> None:
    sign_up(client)
    assert client.post("/auth/sign-out").status_code == 204
    assert client.get("/auth/me").status_code == 401
    assert sign_in(client, email="ME@example.com") == 200
    assert client.get("/auth/me").json()["email"] == "me@example.com"


def test_signing_out_ends_the_session_not_just_the_cookie(client: TestClient, engine: Engine) -> None:
    sign_up(client)
    token = client.cookies[COOKIE]
    client.post("/auth/sign-out")
    client.cookies.set(COOKIE, token)
    assert client.get("/auth/me").status_code == 401


def test_a_wrong_password_and_an_unknown_email_get_the_same_answer(client: TestClient) -> None:
    sign_up(client)
    client.post("/auth/sign-out")
    wrong = client.post("/auth/sign-in", json={"email": "me@example.com", "password": "wrong horse"})
    unknown = client.post("/auth/sign-in", json={"email": "who@example.com", "password": "correct horse"})
    assert (
        (wrong.status_code, wrong.json())
        == (unknown.status_code, unknown.json())
        == (
            401,
            {"detail": "Wrong email or password"},
        )
    )


def test_the_token_is_stored_only_as_a_hash(client: TestClient, engine: Engine) -> None:
    sign_up(client)
    with Session(engine) as session:
        stored = session.scalars(select(UserSession.token_hash)).all()
    assert len(stored) == 1
    assert stored[0] != client.cookies[COOKIE]


def test_a_session_runs_out(client: TestClient, engine: Engine) -> None:
    sign_up(client)
    with Session(engine) as session:
        session.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        session.commit()
    assert client.get("/auth/me").status_code == 401


def test_an_account_without_a_password_cannot_sign_in(client: TestClient, engine: Engine) -> None:
    # Such as the one that owns what was made before there were accounts
    with Session(engine) as session:
        session.add(User(email="owner@unnoodle.local", is_admin=True))
        session.commit()
    assert sign_in(client, email="owner@unnoodle.local", password="") == 401
    assert sign_in(client, email="owner@unnoodle.local", password="correct horse") == 401


def run_users(monkeypatch: pytest.MonkeyPatch, settings: Settings, *args: str, password: str = "") -> None:
    monkeypatch.setenv("UNNOODLE_DATABASE_URL", settings.database_url)
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    users.main(list(args))


def test_the_command_line_makes_an_admin_and_resets_a_password(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_users(monkeypatch, settings, "create", "Boss@example.com", "--admin", password="first password")
    assert sign_in(client, email="boss@example.com", password="first password") == 200
    assert client.get("/auth/me").json()["is_admin"] is True

    run_users(monkeypatch, settings, "set-password", "boss@example.com", password="second password")
    # Setting a password signs the account out everywhere
    assert client.get("/auth/me").status_code == 401
    assert sign_in(client, email="boss@example.com", password="first password") == 401
    assert sign_in(client, email="boss@example.com", password="second password") == 200

    run_users(monkeypatch, settings, "admin", "boss@example.com", "--remove")
    assert client.get("/auth/me").json()["is_admin"] is False


def test_the_command_line_refuses_a_short_password(
    settings: Settings, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit, match="at least 8"):
        run_users(monkeypatch, settings, "create", "me@example.com", password="short")
    with Session(engine) as session:
        assert session.scalars(select(User)).first() is None


def test_too_many_wrong_passwords_lock_the_email_for_a_while(client: TestClient, engine: Engine) -> None:
    sign_up(client)
    client.post("/auth/sign-out")
    for _ in range(5):
        assert sign_in(client, password="wrong horse") == 401
    # Refused even with the right password, until the window passes
    locked = client.post("/auth/sign-in", json={"email": "me@example.com", "password": "correct horse"})
    assert locked.status_code == 429
    assert locked.json()["detail"] == "Too many wrong passwords. Try again in 15 minutes."
    assert locked.headers["retry-after"] == "900"
    # Another address isn't affected
    assert sign_in(client, email="other@example.com", password="anything") == 401

    with Session(engine) as session:
        session.execute(update(FailedSignIn).values(created_at=datetime.now(UTC) - timedelta(minutes=15)))
        session.commit()
    assert sign_in(client) == 200


def test_an_email_without_an_account_is_limited_the_same_way(client: TestClient) -> None:
    # So the limit doesn't reveal which addresses have accounts either
    for _ in range(5):
        assert sign_in(client, email="nobody@example.com") == 401
    assert sign_in(client, email="nobody@example.com") == 429


def test_signing_in_clears_the_wrong_passwords_before_it(client: TestClient) -> None:
    sign_up(client)
    client.post("/auth/sign-out")
    for _ in range(4):
        sign_in(client, password="wrong horse")
    assert sign_in(client) == 200
    client.post("/auth/sign-out")
    for _ in range(4):
        assert sign_in(client, password="wrong horse") == 401
    assert sign_in(client) == 200
