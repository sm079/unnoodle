from collections.abc import Iterator
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Asset, AssetSource, MediaType
from app.settings import Settings
from tests.catalogue import catalogue


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """An app with three workflows: text to image, an edit, and video from a prompt or references."""
    with TestClient(create_app(settings, catalogue())) as client:
        yield client


def upload(client: TestClient) -> str:
    buffer = BytesIO()
    Image.new("RGB", (64, 36)).save(buffer, format="PNG")
    response = client.post("/assets", files={"file": ("frame.png", buffer.getvalue(), "image/png")})
    asset_id: str = response.json()["id"]
    return asset_id


def clip(engine: Engine) -> str:
    # Straight into the table: what matters here is that it is a video
    with Session(engine) as session:
        asset = Asset(
            media_type=MediaType.VIDEO,
            source=AssetSource.UPLOAD,
            storage_key="uploads/clip.mp4",
            mime_type="video/mp4",
            size_bytes=1,
            width=720,
            height=1280,
            duration_s=6.0,
            poster_key="uploads/clip.jpg",
        )
        session.add(asset)
        session.commit()
        return str(asset.id)


def image_request(**changes: Any) -> dict[str, Any]:
    params = {"aspect_ratio": "3:4", "quality": "high", "count": 2} | changes.pop("params", {})
    return {"media_type": "image", "prompt": "a greenhouse at dawn", "params": params} | changes


def edit_request(inputs: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
    return {"media_type": "image", "prompt": "make it night", "inputs": inputs, "params": params}


def video_request(inputs: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
    defaults = {"aspect_ratio": "9:16", "duration_s": 5}
    return {"media_type": "video", "prompt": "she turns around", "inputs": inputs, "params": defaults | params}


def test_a_prompt_alone_queues_text_to_image(client: TestClient) -> None:
    response = client.post("/generations", json=image_request())
    assert response.status_code == 201
    g = response.json()
    assert (g["status"], g["capability"], g["workflow_id"]) == ("queued", "image.generate", "t2i")
    assert {k: g["params"][k] for k in ("quality", "aspect_ratio", "count")} == {
        "quality": "high",
        "aspect_ratio": "3:4",
        "count": 2,
    }
    assert 0 <= g["params"]["seed"] < 2**32
    assert (g["inputs"], g["outputs"], g["progress"], g["error"]) == ([], [], None, None)
    assert client.get(f"/generations/{g['id']}").json() == g


def test_a_seed_sent_in_is_kept(client: TestClient) -> None:
    g = client.post("/generations", json=image_request(params={"seed": 2**40})).json()
    assert g["params"]["seed"] == 2**40


def test_photos_queue_an_edit_in_the_first_ones_shape(client: TestClient) -> None:
    photo, other = upload(client), upload(client)
    inputs = [{"asset_id": photo, "role": "reference"}, {"asset_id": other, "role": "reference"}]
    response = client.post("/generations", json=edit_request(inputs))
    assert response.status_code == 201
    g = response.json()
    assert (g["capability"], g["workflow_id"], g["params"]["aspect_ratio"]) == ("image.edit", "edit", None)
    assert [i["asset"]["id"] for i in g["inputs"]] == [photo, other]


def test_an_edit_can_take_another_shape(client: TestClient) -> None:
    g = client.post("/generations", json=edit_request(photos(client), aspect_ratio="1:1")).json()
    assert g["params"]["aspect_ratio"] == "1:1"


def test_references_queue_video_from_references(client: TestClient, engine: Engine) -> None:
    inputs = [{"asset_id": upload(client), "role": "reference"}, {"asset_id": clip(engine), "role": "reference"}]
    g = client.post("/generations", json=video_request(inputs, duration_s=10)).json()
    assert (g["capability"], g["workflow_id"], g["params"]["duration_s"]) == ("video.reference", "video", 10)


def test_a_prompt_alone_queues_text_to_video(client: TestClient) -> None:
    g = client.post("/generations", json=video_request([])).json()
    assert (g["capability"], g["workflow_id"]) == ("video.generate", "video")


def test_generations_are_listed_newest_first_a_page_at_a_time(client: TestClient) -> None:
    ids = [client.post("/generations", json=image_request(prompt=str(n))).json()["id"] for n in range(5)]
    first = client.get("/generations", params={"limit": 2}).json()
    second = client.get("/generations", params={"limit": 2, "before": first[-1]["id"]}).json()
    assert [g["id"] for g in first + second] == ids[::-1][:4]


def test_an_unknown_generation_is_not_found(client: TestClient) -> None:
    response = client.get("/generations/0199e0a0-0000-7000-8000-000000000000")
    assert response.status_code == 404


def photos(client: TestClient, count: int = 1) -> list[dict[str, Any]]:
    return [{"asset_id": upload(client), "role": "reference"} for _ in range(count)]


REFUSED: list[tuple[str, Any, str]] = [
    ("no shape", lambda c: image_request(params={"aspect_ratio": None}), "Pick a shape"),
    ("shape not offered", lambda c: image_request(params={"aspect_ratio": "16:9"}), "That shape isn't offered here"),
    ("too many outputs", lambda c: image_request(params={"count": 5}), "This makes at most 4 at a time"),
    ("image with a length", lambda c: image_request(params={"duration_s": 5}), "Only videos have a length"),
    ("length not offered", lambda c: video_request([], duration_s=8), "Videos can be 5 or 10 seconds long"),
    ("too many photos", lambda c: edit_request(photos(c, 4)), "Making a picture from photos takes at most 3 photos"),
    ("unknown model", lambda c: image_request(model="flux"), "Making a picture isn't available with that model"),
    (
        "too many references",
        lambda c: video_request([{"asset_id": upload(c), "role": "reference"} for _ in range(3)]),
        "Making a video takes at most 2 photos",
    ),
    (
        "missing file",
        lambda c: video_request([{"asset_id": "0199e0a0-0000-7000-8000-000000000000", "role": "reference"}]),
        "An attached file no longer exists",
    ),
]


@pytest.mark.parametrize(("request_for", "message"), [r[1:] for r in REFUSED], ids=[r[0] for r in REFUSED])
def test_requests_that_dont_fit_are_refused_with_the_reason(client: TestClient, request_for: Any, message: str) -> None:
    response = client.post("/generations", json=request_for(client))
    assert response.status_code == 422
    assert response.json() == {"detail": message}
    assert client.get("/generations").json() == []


def test_a_blank_prompt_is_refused(client: TestClient) -> None:
    response = client.post("/generations", json=image_request(prompt="   "))
    assert response.status_code == 422
