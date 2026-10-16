import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import credits
from app.main import create_app
from app.models import CreditEntry, CreditKind, Generation, GenerationStatus, InviteCode, MediaType, Quality
from app.settings import Settings
from app.worker import queue
from tests.catalogue import catalogue
from tests.conftest import grant, sign_up
from tests.test_generations import clip, image_request, upload, video_request


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, catalogue())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Signed in, with no credits."""
    with TestClient(app) as client:
        sign_up(client, credits=0)
        yield client


def me(client: TestClient) -> str:
    user_id: str = client.get("/auth/me").json()["id"]
    return user_id


def balance(client: TestClient) -> int:
    value: int = client.get("/credits").json()["balance"]
    return value


@pytest.mark.parametrize(
    ("media_type", "quality", "duration_s", "clips", "cost"),
    [
        (MediaType.IMAGE, Quality.LOW, None, 0, 1),
        (MediaType.IMAGE, Quality.MEDIUM, None, 0, 1),
        (MediaType.IMAGE, Quality.HIGH, None, 0, 2),
        (MediaType.VIDEO, Quality.LOW, 5, 0, 10),
        (MediaType.VIDEO, Quality.MEDIUM, 10, 0, 40),
        (MediaType.VIDEO, Quality.HIGH, 15, 0, 120),
        (MediaType.VIDEO, Quality.LOW, 5, 2, 30),
    ],
)
def test_prices_are_fixed(
    media_type: MediaType, quality: Quality, duration_s: int | None, clips: int, cost: int
) -> None:
    # The same cases as apps/web/src/lib/credits.test.ts
    assert credits.cost_of(media_type, quality, duration_s, clips) == cost


def test_a_new_account_has_no_credits_and_sees_the_prices(client: TestClient) -> None:
    assert client.get("/credits").json() == {
        "balance": 0,
        "prices": {
            "image": {"low": 1, "medium": 1, "high": 2},
            "video_per_5s": {"low": 10, "medium": 20, "high": 40},
            "per_clip": 10,
        },
    }


def test_queuing_takes_the_cost_of_each(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 10)
    response = client.post("/generations", json=image_request(params={"quality": "high", "count": 3}))
    assert response.status_code == 201
    assert balance(client) == 4
    with Session(engine) as session:
        charges = session.scalars(select(CreditEntry).where(CreditEntry.kind == CreditKind.CHARGE)).all()
    assert sorted(str(c.generation_id) for c in charges) == sorted(g["id"] for g in response.json())
    assert {c.amount for c in charges} == {-2}


def test_a_video_with_clips_costs_more(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 100)
    inputs = [
        {"asset_id": upload(client), "role": "reference"},
        {"asset_id": clip(client, engine), "role": "reference"},
    ]
    assert client.post("/generations", json=video_request(inputs, aspect_ratio=None, quality="low")).status_code == 201
    assert balance(client) == 100 - 10 - 10


def test_without_enough_credits_nothing_is_queued(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 3)
    response = client.post("/generations", json=image_request(params={"quality": "high", "count": 2}))
    assert (response.status_code, response.json()["detail"]) == (402, "This needs 4 credits and you have 3")
    assert client.get("/generations").json() == []
    assert balance(client) == 3


def test_a_failed_generation_gives_its_credits_back(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 5)
    # Two at high quality, 2 each
    [failed, done] = [g["id"] for g in client.post("/generations", json=image_request(params={"count": 2})).json()]
    assert balance(client) == 1
    with Session(engine) as session, session.begin():
        queue.end(session, session.get_one(Generation, uuid.UUID(failed)), GenerationStatus.FAILED, "It broke")
        queue.end(session, session.get_one(Generation, uuid.UUID(done)), GenerationStatus.DONE)
    assert balance(client) == 3


def test_a_generation_is_refunded_once(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 5)
    [generation_id] = [g["id"] for g in client.post("/generations", json=image_request()).json()]
    with pytest.raises(IntegrityError), Session(engine) as session, session.begin():
        generation = session.get_one(Generation, uuid.UUID(generation_id))
        credits.refund(session, generation)
        credits.refund(session, generation)


def test_someone_can_only_have_so_many_waiting(client: TestClient, engine: Engine) -> None:
    grant(engine, me(client), 100)
    for _ in range(2):
        assert client.post("/generations", json=image_request(params={"count": 4})).status_code == 201
    response = client.post("/generations", json=image_request())
    assert (response.status_code, response.json()["detail"]) == (
        429,
        "You can have up to 8 waiting at once. Let some finish first.",
    )
    # Eight at high quality, 2 each
    assert balance(client) == 84


def invite(engine: Engine, code: str, credits: int = 50, max_uses: int = 2, expires_at: datetime | None = None) -> None:
    with Session(engine) as session:
        session.add(InviteCode(code=code, credits=credits, max_uses=max_uses, expires_at=expires_at))
        session.commit()


def test_an_invite_code_gives_credits_once_each_to_so_many_people(
    app: FastAPI, client: TestClient, engine: Engine
) -> None:
    invite(engine, "WELCOME", credits=50, max_uses=2)
    assert client.post("/credits/redeem", json={"code": " welcome "}).json()["balance"] == 50
    again = client.post("/credits/redeem", json={"code": "WELCOME"})
    assert (again.status_code, again.json()["detail"]) == (409, "You've already used that code")
    with TestClient(app) as second, TestClient(app) as third:
        sign_up(second, email="two@example.com", credits=0)
        assert second.post("/credits/redeem", json={"code": "WELCOME"}).status_code == 200
        sign_up(third, email="three@example.com", credits=0)
        late = third.post("/credits/redeem", json={"code": "WELCOME"})
        assert (late.status_code, late.json()["detail"]) == (404, "That code has been used up")
    assert balance(client) == 50


@pytest.mark.parametrize("code", ["NOPE", "OLD"])
def test_an_unknown_or_expired_code_does_nothing(client: TestClient, engine: Engine, code: str) -> None:
    invite(engine, "OLD", expires_at=datetime.now(UTC) - timedelta(minutes=1))
    response = client.post("/credits/redeem", json={"code": code})
    assert (response.status_code, response.json()["detail"]) == (404, "That code doesn't work")
    assert balance(client) == 0


@pytest.mark.parametrize(
    ("kind", "amount"),
    [(CreditKind.CHARGE, 5), (CreditKind.REFUND, -5), (CreditKind.INVITE, -5), (CreditKind.GRANT, 0)],
)
def test_the_ledger_refuses_entries_that_move_the_wrong_way(
    client: TestClient, engine: Engine, kind: CreditKind, amount: int
) -> None:
    with pytest.raises(IntegrityError), Session(engine) as session:
        session.add(CreditEntry(user_id=uuid.UUID(me(client)), amount=amount, kind=kind))
        session.commit()


def test_the_command_line_grants_credits_and_makes_codes(
    client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("UNNOODLE_DATABASE_URL", settings.database_url)
    credits.main(["grant", "ME@example.com", "30", "--note", "testing"])
    credits.main(["grant", "me@example.com", "-5"])
    assert balance(client) == 25
    credits.main(["invite", "spring", "--credits", "10", "--uses", "1", "--days", "7"])
    assert client.post("/credits/redeem", json={"code": "SPRING"}).json()["balance"] == 35
    credits.main(["balance", "me@example.com"])
    assert capsys.readouterr().out.splitlines()[-1] == "me@example.com has 35 credits"
