from collections.abc import Callable, Iterator
from datetime import timedelta
from io import BytesIO
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Engine, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.main import create_app
from app.media import MediaStore
from app.models import Generation, GenerationStatus
from app.settings import Settings
from app.worker import queue
from app.worker.comfy import ComfyFailed, ComfyRejected, ComfyUnavailable, OutputFile
from app.worker.runner import Outcome, run_job
from app.workflows import Workflow
from tests.catalogue import catalogue, node_of
from tests.clips import clip, needs_ffmpeg


@pytest.fixture
def workflows() -> dict[str, Workflow]:
    return catalogue()


@pytest.fixture
def client(settings: Settings, workflows: dict[str, Workflow]) -> Iterator[TestClient]:
    with TestClient(create_app(settings, workflows)) as client:
        yield client


def png(size: tuple[int, int] = (64, 36)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def queue_image(client: TestClient, prompt: str = "a greenhouse at dawn") -> str:
    params = {"aspect_ratio": "3:4", "quality": "medium", "seed": 7}
    response = client.post("/generations", json={"media_type": "image", "prompt": prompt, "params": params})
    assert response.status_code == 201
    generation_id: str = response.json()[0]["id"]
    return generation_id


def queue_video(client: TestClient, prompt: str, photos: int) -> list[str]:
    """Queues a video from photos, in the first one's shape, and returns the photos' ids."""
    ids = [client.post("/assets", files={"file": ("ref.png", png(), "image/png")}).json()["id"] for _ in range(photos)]
    body = {
        "media_type": "video",
        "prompt": prompt,
        "inputs": [{"asset_id": i, "role": "reference"} for i in ids],
        "params": {"aspect_ratio": None if photos else "9:16", "quality": "low", "duration_s": 10},
    }
    assert client.post("/generations", json=body).status_code == 201
    return ids


def load(engine: Engine, generation_id: str) -> Generation:
    with Session(engine) as session:
        return session.get_one(Generation, generation_id)


def set_fields(engine: Engine, generation_id: str, **values: Any) -> None:
    with Session(engine) as session, session.begin():
        session.execute(update(Generation).where(Generation.id == generation_id).values(**values))


# The queue


def test_the_oldest_queued_generation_is_claimed_first(client: TestClient, engine: Engine) -> None:
    first, second = queue_image(client, "first"), queue_image(client, "second")
    claim = queue.claim_next(engine)
    assert claim is not None
    assert (str(claim.generation_id), claim.attempt) == (first, 1)
    claimed = load(engine, first)
    assert claimed.status is GenerationStatus.RUNNING
    assert claimed.progress == 0
    assert claimed.started_at is not None and claimed.heartbeat_at is not None
    assert load(engine, second).status is GenerationStatus.QUEUED


def test_a_generation_locked_by_another_worker_is_skipped(client: TestClient, engine: Engine) -> None:
    first, second = queue_image(client, "first"), queue_image(client, "second")
    with Session(engine) as other_worker, other_worker.begin():
        # Another worker is in the middle of claiming the first one
        other_worker.execute(select(Generation).where(Generation.id == first).with_for_update())
        claim = queue.claim_next(engine)
    assert claim is not None and str(claim.generation_id) == second


def test_nothing_to_claim(client: TestClient, engine: Engine) -> None:
    assert queue.claim_next(engine) is None


def test_a_running_generation_whose_worker_went_quiet_is_claimed_again(client: TestClient, engine: Engine) -> None:
    generation_id = queue_image(client)
    assert queue.claim_next(engine) is not None
    assert queue.claim_next(engine) is None  # still fresh

    set_fields(engine, generation_id, heartbeat_at=queue.now() - queue.STALE_AFTER - timedelta(seconds=1))
    claim = queue.claim_next(engine)
    assert claim is not None and claim.attempt == 2


def test_a_generation_that_keeps_killing_workers_fails(client: TestClient, engine: Engine) -> None:
    doomed, waiting = queue_image(client, "doomed"), queue_image(client, "waiting")
    stale = queue.now() - queue.STALE_AFTER - timedelta(seconds=1)
    set_fields(engine, doomed, status=GenerationStatus.RUNNING, attempts=queue.MAX_ATTEMPTS, heartbeat_at=stale)
    claim = queue.claim_next(engine)
    assert claim is not None and str(claim.generation_id) == waiting
    failed = load(engine, doomed)
    assert failed.status is GenerationStatus.FAILED
    assert failed.error == "The worker stopped while running this, too many times"


def test_a_released_generation_goes_back_without_using_an_attempt(client: TestClient, engine: Engine) -> None:
    generation_id = queue_image(client)
    claim = queue.claim_next(engine)
    assert claim is not None
    queue.release(engine, claim)
    released = load(engine, generation_id)
    assert (released.status, released.attempts, released.started_at) == (GenerationStatus.QUEUED, 0, None)


def test_a_worker_that_lost_its_lease_changes_nothing(client: TestClient, engine: Engine) -> None:
    generation_id = queue_image(client)
    claim = queue.claim_next(engine)
    assert claim is not None
    set_fields(engine, generation_id, attempts=2, progress=0.1)  # another worker took it over
    queue.beat(engine, claim, 0.9)
    assert load(engine, generation_id).progress == 0.1


def test_queueing_a_generation_wakes_the_workers(client: TestClient, test_database_url: str) -> None:
    url = make_url(test_database_url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(url, autocommit=True) as listener:
        listener.execute(f"LISTEN {queue.CHANNEL}")
        queue_image(client)
        received = [n.channel for n in listener.notifies(timeout=5, stop_after=1)]
    assert received == [queue.CHANNEL]


# Running a job


class FakeComfy:
    """ComfyUI in memory: records what it was sent and plays back progress, files or an error."""

    def __init__(
        self,
        files: int = 2,
        error: Exception | None = None,
        during: Callable[[], None] = lambda: None,
        output: bytes | None = None,
    ) -> None:
        self.files, self.error, self.during = files, error, during
        # What each output file holds: a picture unless a test says otherwise
        self.output = output if output is not None else png((896, 1152))
        self.uploads: dict[str, bytes] = {}
        self.graphs: list[dict[str, Any]] = []

    def upload(self, data: bytes, name: str) -> str:
        self.uploads[name] = data
        return f"unnoodle/{name}"

    def run(
        self,
        graph: dict[str, Any],
        prompt_id: str,
        output_node: str,
        on_progress: Callable[[float], None],
        on_quiet: Callable[[], None],
    ) -> list[OutputFile]:
        self.graphs.append(graph)
        on_progress(0.5)
        self.during()
        on_quiet()
        if self.error is not None:
            raise self.error
        return [OutputFile(f"out_{n}.png", "unnoodle", "output") for n in range(self.files)]

    def download(self, file: OutputFile) -> bytes:
        return self.output


def run(engine: Engine, workflows: dict[str, Workflow], settings: Settings, comfy: FakeComfy) -> Outcome:
    claim = queue.claim_next(engine)
    assert claim is not None
    return run_job(engine, claim, workflows, MediaStore(settings.media_dir), comfy)


def test_a_finished_run_stores_its_outputs(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client)
    assert run(engine, workflows, settings, FakeComfy(files=2)) == "done"

    g = client.get(f"/generations/{generation_id}").json()
    assert (g["status"], g["progress"], g["error"]) == ("done", None, None)
    assert g["finished_at"] is not None
    assert [(o["width"], o["height"], o["source"]) for o in g["outputs"]] == [(896, 1152, "generation")] * 2
    for output in g["outputs"]:
        assert client.get(output["url"]).status_code == 200


@needs_ffmpeg
def test_a_video_is_stored_with_a_poster(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    queue_video(client, "a fox runs", photos=0)
    assert run(engine, workflows, settings, FakeComfy(files=1, output=clip(2, size=(320, 576)))) == "done"
    [output] = client.get("/generations").json()[0]["outputs"]
    assert (output["media_type"], output["width"], output["height"]) == ("video", 320, 576)
    assert output["duration_s"] == pytest.approx(2, abs=0.1)
    assert output["url"].endswith(".mp4") and output["thumbnail_url"].endswith(".jpg")
    assert client.get(output["thumbnail_url"]).headers["content-type"] == "image/jpeg"


def test_a_file_that_is_neither_picture_nor_video_fails_the_run(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client)
    assert run(engine, workflows, settings, FakeComfy(output=b"not media")) == "failed"
    assert (
        client.get(f"/generations/{generation_id}").json()["error"] == "This made a kind of file the app can't show yet"
    )


def test_the_graph_is_built_from_the_request(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client, "a greenhouse at dawn")
    comfy = FakeComfy()
    run(engine, workflows, settings, comfy)
    graph = comfy.graphs[0]
    # Medium quality is a megapixel, here at 3:4
    assert node_of(graph, "EmptyImage") == {"width": 880, "height": 1184, "batch_size": 1, "color": 0}
    assert node_of(graph, "Job") == {"prompt": "a greenhouse at dawn", "seed": 7, "frames": None}
    assert node_of(graph, "SaveImage")["filename_prefix"] == f"unnoodle/{generation_id}"


def test_attached_files_are_uploaded_into_the_graph(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    photos = queue_video(client, "@photo2 waves at @photo1", photos=2)
    comfy = FakeComfy(files=1)
    run(engine, workflows, settings, comfy)
    assert list(comfy.uploads) == [f"{p}.png" for p in photos]
    graph = comfy.graphs[0]
    loads = [n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage"]
    assert loads == [f"unnoodle/{p}.png" for p in photos]
    # Ten seconds is the frame count the workflow gives it, and the prompt names the photos as the model expects
    assert node_of(graph, "Job")["frames"] == 243
    # The first photo's shape (64 by 36) at low quality's area, on the workflow's 32-pixel grid
    assert (node_of(graph, "EmptyImage")["width"], node_of(graph, "EmptyImage")["height"]) == (960, 544)
    assert node_of(graph, "Job")["prompt"] == "image 2 waves at image 1"


def test_progress_is_recorded_while_running(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client)
    seen: list[float | None] = []
    run(engine, workflows, settings, FakeComfy(during=lambda: seen.append(load(engine, generation_id).progress)))
    assert seen == [0.5]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            ComfyFailed("CUDA out of memory", "KSampler", "torch.OutOfMemoryError"),
            "This was too big to make. Try a lower quality, a shorter length or fewer at a time.",
        ),
        (
            ComfyFailed("bad shape\nTraceback ...", "VAEDecode", "RuntimeError"),
            "Something went wrong while making this. Try again.",
        ),
        (ComfyFailed("This was stopped before it finished"), "This was stopped before it finished"),
        (ComfyRejected("node 7: missing input"), "Something is wrong on our side, so this couldn't start"),
        (ValueError("a bug"), "Something went wrong while making this. Try again."),
    ],
    ids=["out of memory", "node error", "ours", "refused graph", "unexpected"],
)
def test_a_failed_run_records_why(
    client: TestClient,
    engine: Engine,
    workflows: dict[str, Workflow],
    settings: Settings,
    error: Exception,
    message: str,
) -> None:
    generation_id = queue_image(client)
    assert run(engine, workflows, settings, FakeComfy(error=error)) == "failed"
    g = client.get(f"/generations/{generation_id}").json()
    assert (g["status"], g["error"], g["outputs"], g["progress"]) == ("failed", message, [], None)


def test_an_unreachable_comfyui_puts_the_job_back(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client)
    outcome = run(engine, workflows, settings, FakeComfy(error=ComfyUnavailable("connection refused")))
    assert outcome == "released"
    assert load(engine, generation_id).status is GenerationStatus.QUEUED


def test_outputs_of_a_run_whose_lease_was_lost_are_dropped(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client)
    took_over = FakeComfy(during=lambda: set_fields(engine, generation_id, attempts=2))
    assert run(engine, workflows, settings, took_over) == "lost"
    g = load(engine, generation_id)
    assert (g.status, g.attempts) == (GenerationStatus.RUNNING, 2)
    assert client.get(f"/generations/{generation_id}").json()["outputs"] == []
