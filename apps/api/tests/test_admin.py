import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Asset, Generation
from app.moderation import banned_in, tokens
from app.settings import Settings
from tests.catalogue import catalogue
from tests.conftest import make_admin, sign_up
from tests.test_generations import edit_request, image_request, upload
from tests.test_projects import finish_with_outputs


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, catalogue())


@pytest.fixture
def admin(app: FastAPI, engine: Engine) -> Iterator[TestClient]:
    with TestClient(app) as client:
        make_admin(engine, sign_up(client, email="admin@example.com"))
        yield client


@pytest.fixture
def person(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        sign_up(client, email="person@example.com", credits=50)
        yield client


@pytest.mark.parametrize(
    ("prompt", "found"),
    [
        ("a NÜDE portrait", "nude"),
        ("nuuuude on a beach", "nude"),
        ("n u d e", "nude"),
        ("nud3", "nude"),
        ("$ex scene", "sex"),
        ("nudes", "nude"),
        ("NSFW!!", "nsfw"),
        ("with the naked eye", "naked eye"),
        ("a nudibranch under the sea", None),
        ("make @photo1 wear a hat, 4k", None),
        ("Wow! a nice sunset", None),
    ],
)
def test_banned_words_are_found_however_they_are_typed(prompt: str, found: str | None) -> None:
    assert banned_in(prompt, ["nude", "sex", "nsfw", "naked eye"]) == found


def test_words_are_evened_out_for_comparing() -> None:
    assert tokens("Café au LAIT") == ["cafe", "au", "lait"]
    # Single letters in a row spell a word
    assert tokens("a b c, then more") == ["abc", "then", "more"]


def test_a_prompt_with_a_banned_word_is_refused(admin: TestClient, person: TestClient) -> None:
    # The migration's starting list may be there too, depending on which test ran first
    assert "nude" in admin.post("/admin/banned-words", json={"word": " Nude "}).json()
    response = person.post("/generations", json=image_request(prompt="a nuuude portrait"))
    assert (response.status_code, response.json()["detail"]) == (
        422,
        '"nude" isn\'t allowed in prompts here. Try saying it another way.',
    )
    assert person.get("/credits").json()["balance"] == 50
    assert "nude" not in admin.delete("/admin/banned-words/nude").json()
    assert person.post("/generations", json=image_request(prompt="a nuuude portrait")).status_code == 201


def test_only_admins_reach_the_admin_endpoints(person: TestClient) -> None:
    for method, path in [
        ("GET", "/admin/generations"),
        ("GET", "/admin/users"),
        ("GET", "/admin/invite-codes"),
        ("GET", "/admin/banned-words"),
        ("POST", "/admin/banned-words"),
    ]:
        assert person.request(method, path, json={"word": "x"}).status_code == 403, path


def test_admins_see_everyones_generations_with_who_made_them(admin: TestClient, person: TestClient) -> None:
    mine = person.post("/generations", json=image_request()).json()[0]["id"]
    listed = admin.get("/admin/generations").json()
    assert [(g["id"], g["owner_email"]) for g in listed] == [(mine, "person@example.com")]


def test_deleting_a_generation_removes_its_outputs_files_and_unshared_uploads(
    admin: TestClient, person: TestClient, engine: Engine, settings: Settings
) -> None:
    photo, shared = upload(person), upload(person)
    first = person.post(
        "/generations",
        json=edit_request([{"asset_id": photo, "role": "reference"}, {"asset_id": shared, "role": "reference"}]),
    ).json()[0]["id"]
    second = person.post("/generations", json=edit_request([{"asset_id": shared, "role": "reference"}])).json()[0]["id"]
    [output] = finish_with_outputs(engine, first, 1)
    with Session(engine) as session:
        output_key = session.get_one(Asset, uuid.UUID(output)).storage_key
        photo_key = session.get_one(Asset, uuid.UUID(photo)).storage_key
    (settings.media_dir / output_key).parent.mkdir(parents=True, exist_ok=True)
    (settings.media_dir / output_key).write_bytes(b"png")

    assert admin.delete(f"/admin/generations/{first}").status_code == 204
    assert person.get(f"/generations/{first}").status_code == 404
    assert not (settings.media_dir / output_key).exists()
    assert not (settings.media_dir / photo_key).exists()
    with Session(engine) as session:
        left = set(session.scalars(select(Asset.id)))
        assert left == {uuid.UUID(shared)}
        assert session.get(Generation, uuid.UUID(second)) is not None
    # Credits taken for it stay taken
    assert person.get("/credits").json()["balance"] == 50 - 2
    assert admin.delete(f"/admin/generations/{first}").status_code == 404


def test_admins_grant_credits_and_see_balances(admin: TestClient, person: TestClient) -> None:
    person_id = person.get("/auth/me").json()["id"]
    person.post("/generations", json=image_request())
    granted = admin.post(f"/admin/users/{person_id}/credits", json={"amount": 25, "note": "welcome"}).json()
    assert (granted["balance"], granted["generation_count"]) == (50 - 2 + 25, 1)
    users = {u["email"]: u for u in admin.get("/admin/users").json()}
    assert users["person@example.com"]["balance"] == 73
    assert users["admin@example.com"]["is_admin"] is True
    assert admin.post(f"/admin/users/{person_id}/credits", json={"amount": 0}).status_code == 422
    assert admin.post(f"/admin/users/{uuid.uuid7()}/credits", json={"amount": 5}).status_code == 404


def test_admins_make_invite_codes_and_see_their_uses(admin: TestClient, person: TestClient) -> None:
    made = admin.post("/admin/invite-codes", json={"code": "spring-26", "credits": 40, "max_uses": 3, "days": 7})
    assert made.status_code == 201
    assert (made.json()["code"], made.json()["uses"]) == ("SPRING-26", 0)
    assert made.json()["expires_at"] is not None
    assert admin.post("/admin/invite-codes", json={"code": "SPRING-26", "credits": 1, "max_uses": 1}).status_code == 409
    assert admin.post("/admin/invite-codes", json={"code": "no spaces", "credits": 1, "max_uses": 1}).status_code == 422
    person.post("/credits/redeem", json={"code": "spring-26"})
    [listed] = admin.get("/admin/invite-codes").json()
    assert (listed["code"], listed["uses"], listed["max_uses"]) == ("SPRING-26", 1, 3)
