from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Asset, AssetSource, MediaType
from app.settings import Settings
from tests.graphs import write_catalogue


@pytest.fixture
def client(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    """An app with three workflows: text to image, video from a frame, and a character swap."""
    catalogue = write_catalogue(tmp_path / "workflows")
    with TestClient(create_app(settings.model_copy(update={"workflows_dir": catalogue}))) as client:
        yield client


def upload(client: TestClient) -> str:
    buffer = BytesIO()
    Image.new("RGB", (64, 36)).save(buffer, format="PNG")
    response = client.post("/assets", files={"file": ("frame.png", buffer.getvalue(), "image/png")})
    asset_id: str = response.json()["id"]
    return asset_id


def image_request(**changes: Any) -> dict[str, Any]:
    params = {"aspect_ratio": "3:4", "resolution": "1K", "count": 2} | changes.pop("params", {})
    return {"media_type": "image", "prompt": "a greenhouse at dawn", "params": params} | changes


def video_request(inputs: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
    defaults = {"aspect_ratio": "16:9", "resolution": "720p", "duration_s": 5}
    return {"media_type": "video", "prompt": "she turns around", "inputs": inputs, "params": defaults | params}


def test_a_prompt_alone_queues_text_to_image(client: TestClient) -> None:
    response = client.post("/generations", json=image_request())
    assert response.status_code == 201
    g = response.json()
    assert (g["status"], g["capability"], g["workflow_id"]) == ("queued", "image.generate", "t2i")
    assert g["params"]["count"] == 2
    assert 0 <= g["params"]["seed"] < 2**32
    assert (g["inputs"], g["outputs"], g["progress"], g["error"]) == ([], [], None, None)
    assert client.get(f"/generations/{g['id']}").json() == g


def test_a_seed_sent_in_is_kept(client: TestClient) -> None:
    g = client.post("/generations", json=image_request(params={"seed": 2**40})).json()
    assert g["params"]["seed"] == 2**40


def test_an_attached_start_frame_queues_video_from_frame(client: TestClient) -> None:
    frame = upload(client)
    response = client.post("/generations", json=video_request([{"asset_id": frame, "role": "start_frame"}]))
    assert response.status_code == 201
    g = response.json()
    assert (g["capability"], g["workflow_id"]) == ("video.from_frame", "i2v")
    assert [(i["role"], i["asset"]["id"]) for i in g["inputs"]] == [("start_frame", frame)]


def test_generations_are_listed_newest_first_a_page_at_a_time(client: TestClient) -> None:
    ids = [client.post("/generations", json=image_request(prompt=str(n))).json()["id"] for n in range(5)]
    first = client.get("/generations", params={"limit": 2}).json()
    second = client.get("/generations", params={"limit": 2, "before": first[-1]["id"]}).json()
    assert [g["id"] for g in first + second] == ids[::-1][:4]


def test_an_unknown_generation_is_not_found(client: TestClient) -> None:
    response = client.get("/generations/0199e0a0-0000-7000-8000-000000000000")
    assert response.status_code == 404


def video_with_frame(client: TestClient, **params: Any) -> dict[str, Any]:
    return video_request([{"asset_id": upload(client), "role": "start_frame"}], **params)


def swap_with_image_as_source(client: TestClient) -> dict[str, Any]:
    image = upload(client)
    return video_request([{"asset_id": image, "role": "source_video"}, {"asset_id": image, "role": "reference"}])


REFUSED: list[tuple[str, Any, str]] = [
    ("resolution not offered", lambda c: image_request(params={"resolution": "4K"}), "Test offers 1K, not 4K"),
    (
        "ratio not offered",
        lambda c: image_request(params={"aspect_ratio": "16:9"}),
        "Test at 1K offers 3:4, 1:1, not 16:9",
    ),
    ("too many outputs", lambda c: image_request(params={"count": 5}), "Test makes at most 4 at a time"),
    ("image with a duration", lambda c: image_request(params={"duration_s": 5}), "Only videos have a duration"),
    ("duration not offered", lambda c: video_with_frame(c, duration_s=8), "Test makes videos of 5s"),
    ("sound not offered", lambda c: video_with_frame(c, audio=True), "Test doesn't make sound"),
    (
        "role the output type can't use",
        lambda c: image_request(inputs=[{"asset_id": upload(c), "role": "start_frame"}]),
        "A start frame can't be used to make an image",
    ),
    ("unknown model", lambda c: image_request(model="flux"), "flux doesn't do image.generate; these do: test"),
    (
        "capability nothing offers",
        lambda c: video_request([]),
        "No workflow does video.generate yet",
    ),
    (
        "missing file",
        lambda c: video_request([{"asset_id": "0199e0a0-0000-7000-8000-000000000000", "role": "start_frame"}]),
        "An attached file no longer exists",
    ),
    (
        "time on a start frame",
        lambda c: video_request([{"asset_id": upload(c), "role": "start_frame", "position_s": 1}]),
        "Keyframes need a time in the clip, and only keyframes have one",
    ),
    ("image as the source video", swap_with_image_as_source, "A source video has to be a video"),
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


def test_a_video_upload_can_be_the_source_video(client: TestClient, engine: Engine) -> None:
    # Video uploads aren't accepted yet, so the clip goes straight into the table
    with Session(engine) as session:
        clip = Asset(
            media_type=MediaType.VIDEO,
            source=AssetSource.UPLOAD,
            storage_key="uploads/clip.mp4",
            mime_type="video/mp4",
            size_bytes=1,
            width=720,
            height=1280,
            duration_s=6.0,
        )
        session.add(clip)
        session.commit()
        clip_id = str(clip.id)
    face = upload(client)
    inputs = [{"asset_id": clip_id, "role": "source_video"}, {"asset_id": face, "role": "reference"}]
    response = client.post("/generations", json=video_request(inputs))
    assert response.status_code == 201
    assert response.json()["capability"] == "video.character_swap"
