"""One person never sees, uses or changes another's things, and nothing but the few public endpoints answers without
signing in."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.main import create_app
from app.settings import Settings
from tests.catalogue import catalogue
from tests.conftest import sign_up
from tests.test_generations import edit_request, image_request, upload
from tests.test_projects import finish_with_outputs

# Everything else needs an account
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/pipelines"),
    ("POST", "/auth/sign-up"),
    ("POST", "/auth/sign-in"),
    ("POST", "/auth/sign-out"),
}


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, catalogue())


@pytest.fixture
def mine(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        sign_up(client, email="me@example.com")
        yield client


@pytest.fixture
def theirs(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        sign_up(client, email="them@example.com")
        yield client


def test_every_endpoint_but_the_public_ones_needs_an_account(app: FastAPI) -> None:
    # Every endpoint the API documents, which is every one it has
    routes = [(method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item]
    assert PUBLIC <= set(routes)
    with TestClient(app) as anonymous:
        for method, path in routes:
            if (method, path) in PUBLIC:
                continue
            # Placeholders are filled with a well-formed id; the answer must come before it is looked up
            url = path.replace("{key:path}", "uploads/x.png")
            url = "/".join("0190f0c4-0000-7000-8000-000000000000" if p.startswith("{") else p for p in url.split("/"))
            assert anonymous.request(method, url).status_code == 401, (method, path)


def test_lists_hold_only_your_own(mine: TestClient, theirs: TestClient) -> None:
    upload(mine)
    mine.post("/generations", json=image_request())
    mine.post("/projects", json={"name": "Mine"})
    assert theirs.get("/assets").json() == []
    assert theirs.get("/generations").json() == []
    assert theirs.get("/projects").json() == []
    assert len(mine.get("/assets").json()) == 1


def test_someone_elses_generation_or_project_is_not_found(mine: TestClient, theirs: TestClient) -> None:
    generation_id = mine.post("/generations", json=image_request()).json()[0]["id"]
    project_id = mine.post("/projects", json={"name": "Mine"}).json()["id"]
    assert theirs.get(f"/generations/{generation_id}").status_code == 404
    assert theirs.get(f"/projects/{project_id}").status_code == 404
    # Asking for a project's generations by id gives nothing either
    assert theirs.get("/generations", params={"project_id": project_id}).json() == []


def test_someone_elses_files_are_not_served(mine: TestClient, theirs: TestClient) -> None:
    asset_id = upload(mine)
    url = next(a["url"] for a in mine.get("/assets").json() if a["id"] == asset_id)
    assert mine.get(url).status_code == 200
    assert mine.get(url).headers["cache-control"] == "private, max-age=31536000, immutable"
    # The same answer as for a file that doesn't exist
    assert theirs.get(url).status_code == 404
    assert theirs.get(url).json() == mine.get("/media/uploads/nothing.png").json()


def test_someone_elses_upload_cannot_be_attached(mine: TestClient, theirs: TestClient) -> None:
    asset_id = upload(mine)
    response = theirs.post("/generations", json=edit_request([{"asset_id": asset_id, "role": "reference"}]))
    assert (response.status_code, response.json()["detail"]) == (422, "An attached file no longer exists")


def test_nothing_can_be_filed_in_someone_elses_project(mine: TestClient, theirs: TestClient) -> None:
    project_id = mine.post("/projects", json={"name": "Mine"}).json()["id"]
    response = theirs.post("/generations", json=image_request(project_id=project_id))
    assert (response.status_code, response.json()["detail"]) == (422, "That project no longer exists")
    assert mine.get(f"/projects/{project_id}").json()["generation_count"] == 0


def make_demo(engine: Engine, project_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(text("UPDATE projects SET is_demo = true WHERE id = :id"), {"id": project_id})


def test_a_demo_is_shown_to_everyone_and_its_files_can_be_reused(
    mine: TestClient, theirs: TestClient, engine: Engine
) -> None:
    project_id = mine.post("/projects", json={"name": "Demo"}).json()["id"]
    photo = upload(mine)
    edit = edit_request([{"asset_id": photo, "role": "reference"}]) | {"project_id": project_id}
    generation_id = mine.post("/generations", json=edit).json()[0]["id"]
    [output] = finish_with_outputs(engine, generation_id, 1)
    make_demo(engine, project_id)

    [listed] = theirs.get("/projects").json()
    assert (listed["name"], listed["demo"], listed["mine"], listed["generation_count"]) == ("Demo", True, False, 1)
    assert mine.get(f"/projects/{project_id}").json()["mine"] is True
    assert [g["id"] for g in theirs.get("/generations", params={"project_id": project_id}).json()] == [generation_id]
    shown = theirs.get(f"/generations/{generation_id}").json()
    # Its inputs are served too, and its outputs can be used as inputs
    assert theirs.get(shown["inputs"][0]["asset"]["url"]).status_code == 200
    reuse = theirs.post("/generations", json=edit_request([{"asset_id": output, "role": "reference"}]))
    assert reuse.status_code == 201
    # It isn't theirs, so it stays out of their own lists
    assert [g["id"] for g in theirs.get("/generations").json()] == [reuse.json()[0]["id"]]
    assert theirs.get("/assets").json() == []


def test_only_its_owner_adds_to_a_demo(mine: TestClient, theirs: TestClient, engine: Engine) -> None:
    project_id = mine.post("/projects", json={"name": "Demo"}).json()["id"]
    make_demo(engine, project_id)
    response = theirs.post("/generations", json=image_request(project_id=project_id))
    assert (response.status_code, response.json()["detail"]) == (422, "Only the demo's owner can add to it")
    assert mine.post("/generations", json=image_request(project_id=project_id)).status_code == 201
