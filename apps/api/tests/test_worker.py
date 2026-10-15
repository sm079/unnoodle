from collections.abc import Callable, Iterator
from datetime import timedelta
from io import BytesIO
from pathlib import Path
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
from app.workflows import Workflow, load_workflows
from tests.graphs import write_catalogue


@pytest.fixture
def catalogue(tmp_path: Path) -> Path:
    return write_catalogue(tmp_path / "workflows")


@pytest.fixture
def workflows(catalogue: Path) -> dict[str, Workflow]:
    return load_workflows(catalogue)


@pytest.fixture
def client(settings: Settings, catalogue: Path) -> Iterator[TestClient]:
    with TestClient(create_app(settings.model_copy(update={"workflows_dir": catalogue}))) as client:
        yield client


def png(size: tuple[int, int] = (64, 36)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def queue_image(client: TestClient, prompt: str = "a greenhouse at dawn", count: int = 2) -> str:
    params = {"aspect_ratio": "3:4", "resolution": "1K", "count": count, "seed": 7}
    response = client.post("/generations", json={"media_type": "image", "prompt": prompt, "params": params})
    assert response.status_code == 201
    generation_id: str = response.json()["id"]
    return generation_id


def queue_video_from_frame(client: TestClient) -> tuple[str, str]:
    frame = client.post("/assets", files={"file": ("frame.png", png(), "image/png")}).json()["id"]
    body = {
        "media_type": "video",
        "prompt": "she turns around",
        "inputs": [{"asset_id": frame, "role": "start_frame"}],
        "params": {"aspect_ratio": "16:9", "resolution": "720p", "duration_s": 5},
    }
    generation_id: str = client.post("/generations", json=body).json()["id"]
    return generation_id, frame


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
    ) -> None:
        self.files, self.error, self.during = files, error, during
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
        return png((896, 1152))


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


def test_the_request_is_written_into_the_bound_nodes(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    generation_id = queue_image(client, "a greenhouse at dawn", count=3)
    comfy = FakeComfy()
    run(engine, workflows, settings, comfy)
    graph = comfy.graphs[0]
    bound = {
        graph[node_id]["_meta"]["title"]: graph[node_id]["inputs"]["value"] for node_id in ("1", "2", "3", "4", "7")
    }
    assert bound == {
        "in.prompt": "a greenhouse at dawn",
        "in.seed": 7,
        "in.width": 896,
        "in.height": 1152,
        "in.batch_size": 3,
    }
    assert graph["6"]["inputs"]["filename_prefix"] == f"unnoodle/{generation_id}"
    # The stored workflow itself is untouched
    assert workflows["t2i"].graph["1"]["inputs"]["value"] == ""


def test_attached_files_are_uploaded_and_bound(
    client: TestClient, engine: Engine, workflows: dict[str, Workflow], settings: Settings
) -> None:
    _, frame = queue_video_from_frame(client)
    comfy = FakeComfy(files=1)
    run(engine, workflows, settings, comfy)
    assert list(comfy.uploads) == [f"{frame}.png"]
    graph = comfy.graphs[0]
    assert graph["9"]["inputs"]["image"] == f"unnoodle/{frame}.png"
    assert (graph["7"]["inputs"]["value"], graph["8"]["inputs"]["value"]) == (120, 24)  # 5 s at 24 fps


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
            "The GPU ran out of memory. Try a smaller size or fewer outputs.",
        ),
        (ComfyFailed("bad shape\nTraceback ...", "VAEDecode", "RuntimeError"), "VAEDecode failed: bad shape"),
        (ComfyRejected("node 7: missing input"), "This workflow is broken: ComfyUI refused it"),
        (ValueError("a bug"), "Something went wrong while running this"),
    ],
    ids=["out of memory", "node error", "refused graph", "unexpected"],
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
