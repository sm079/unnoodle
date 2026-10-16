"""One person never sees, uses or changes another's things, and nothing but the few public endpoints answers without
signing in."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from tests.catalogue import catalogue
from tests.conftest import sign_up
from tests.test_generations import edit_request, image_request, upload

# Everything else needs an account
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/workflows"),
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
