import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Asset, AssetSource, MediaType
from app.settings import Settings
from tests.catalogue import catalogue
from tests.test_generations import image_request


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings, catalogue())) as client:
        yield client


def finish_with_outputs(engine: Engine, generation_id: str, count: int) -> list[str]:
    """Stores outputs for a generation, as the worker would, and returns their ids oldest first."""
    with Session(engine) as session:
        outputs = [
            Asset(
                media_type=MediaType.IMAGE,
                source=AssetSource.GENERATION,
                storage_key=f"outputs/{generation_id}/{n}.png",
                mime_type="image/png",
                size_bytes=1,
                width=64,
                height=64,
                generation_id=uuid.UUID(generation_id),
            )
            for n in range(count)
        ]
        session.add_all(outputs)
        session.commit()
        return [str(a.id) for a in outputs]


def test_a_new_project_is_empty(client: TestClient) -> None:
    response = client.post("/projects", json={"name": "  Short film "})
    assert response.status_code == 201
    project = response.json()
    assert (project["name"], project["generation_count"], project["covers"]) == ("Short film", 0, [])
    assert client.get(f"/projects/{project['id']}").json() == project


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_a_project_needs_a_name_that_fits(client: TestClient, name: str) -> None:
    assert client.post("/projects", json={"name": name}).status_code == 422


def test_projects_are_listed_newest_first(client: TestClient) -> None:
    names = ["Short film", "Moodboard", "Posters"]
    for name in names:
        client.post("/projects", json={"name": name})
    assert [p["name"] for p in client.get("/projects").json()] == names[::-1]


def test_an_unknown_project_is_not_found(client: TestClient) -> None:
    assert client.get("/projects/0199e0a0-0000-7000-8000-000000000000").status_code == 404


def test_a_generation_made_in_a_project_is_in_it_and_in_my_generations(client: TestClient) -> None:
    project = client.post("/projects", json={"name": "Short film"}).json()["id"]
    loose = client.post("/generations", json=image_request(prompt="loose")).json()
    filed = client.post("/generations", json=image_request(prompt="filed", project_id=project)).json()
    assert (loose["project_id"], filed["project_id"]) == (None, project)

    everything = client.get("/generations").json()
    assert [g["id"] for g in everything] == [filed["id"], loose["id"]]
    in_project = client.get("/generations", params={"project_id": project}).json()
    assert [g["id"] for g in in_project] == [filed["id"]]


def test_a_generation_for_a_missing_project_is_refused(client: TestClient) -> None:
    request = image_request(project_id="0199e0a0-0000-7000-8000-000000000000")
    response = client.post("/generations", json=request)
    assert response.status_code == 422
    assert response.json() == {"detail": "That project no longer exists"}


def test_a_project_counts_its_generations_and_shows_its_newest_outputs(client: TestClient, engine: Engine) -> None:
    film, posters = (client.post("/projects", json={"name": name}).json()["id"] for name in ("Short film", "Posters"))
    first = client.post("/generations", json=image_request(project_id=film)).json()["id"]
    second = client.post("/generations", json=image_request(project_id=film)).json()["id"]
    client.post("/generations", json=image_request())
    older = finish_with_outputs(engine, first, 2)
    newer = finish_with_outputs(engine, second, 2)

    listed = {p["name"]: p for p in client.get("/projects").json()}
    assert listed["Short film"]["generation_count"] == 2
    assert [a["id"] for a in listed["Short film"]["covers"]] == [newer[1], newer[0], older[1]]
    assert (listed["Posters"]["generation_count"], listed["Posters"]["covers"]) == (0, [])
    assert client.get(f"/projects/{posters}").json() == listed["Posters"]
