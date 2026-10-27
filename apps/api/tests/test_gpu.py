import re
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app import credits
from app.gpu import manager as gpu
from app.gpu.files import FILES
from app.gpu.manager import Config, Manager, ready_pipelines
from app.gpu.runpod import POD_NAME, NoCapacity, Pod
from app.main import create_app
from app.models import Generation, GenerationStatus, GpuSession, GpuStatus
from app.settings import Settings
from app.worker import queue
from tests.conftest import make_admin, sign_up

START = datetime(2026, 10, 20, 9, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))


class Clock:
    def __init__(self) -> None:
        self.at = START

    def now(self) -> datetime:
        return self.at

    def sleep(self, seconds: float) -> None:
        self.at += timedelta(seconds=seconds)


class FakePods:
    def __init__(self) -> None:
        self.pods: dict[str, Pod] = {}
        self.created: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.no_capacity = False

    def create(self, gpu_types: list[str], public_key: str) -> Pod:
        if self.no_capacity:
            raise NoCapacity("no instances currently available")
        n = len(self.created)
        pod = Pod(f"pod{n + 1}", POD_NAME, "RUNNING", 1.19, "203.0.113.7", 22000 + n, gpu_types[0])
        self.created.append((gpu_types[0], public_key))
        self.pods[pod.id] = pod
        return pod

    def get(self, pod_id: str) -> Pod | None:
        return self.pods.get(pod_id)

    def list(self) -> list[Pod]:
        return list(self.pods.values())

    def delete(self, pod_id: str) -> None:
        self.deleted.append(pod_id)
        self.pods.pop(pod_id, None)


class FakeShell:
    def __init__(self) -> None:
        self.ran: list[tuple[str, tuple[str, ...]]] = []
        self.secrets: list[dict[str, str] | None] = []
        self.reachable_pods = True
        self.failing: set[str] = set()
        self.tunnel: str | None = None
        self.heartbeats = 0
        # Called with the script's name as it runs, to look at the database part way through preparing
        self.during: dict[str, object] = {}

    def reachable(self, pod: Pod) -> bool:
        return self.reachable_pods

    def run(self, pod: Pod, script: str, *args: str, secrets: dict[str, str] | None = None) -> tuple[int, str]:
        self.ran.append((script, args))
        self.secrets.append(secrets)
        hook = self.during.get(script)
        if callable(hook):
            hook(args)
        return (1, "failed") if script in self.failing else (0, "")

    def heartbeat(self, pod: Pod) -> bool:
        self.heartbeats += 1
        return self.reachable_pods

    def open_tunnel(self, pod: Pod) -> None:
        self.tunnel = pod.id

    def tunnel_open(self) -> bool:
        return self.tunnel is not None

    def close_tunnel(self) -> None:
        self.tunnel = None


@pytest.fixture
def real_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"pipelines": "real", "gpu": "runpod"})


@pytest.fixture
def client(real_settings: Settings, clock: Clock, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # The GPU's state is worked out on the manager's clock, or a session it launched "today" looks days old
    monkeypatch.setattr("app.gpu.api.now", clock.now)
    with TestClient(create_app(real_settings)) as client:
        sign_up(client)
        yield client


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def pods() -> FakePods:
    return FakePods()


@pytest.fixture
def shell() -> FakeShell:
    return FakeShell()


@pytest.fixture
def manager(engine: Engine, pods: FakePods, shell: FakeShell, clock: Clock, real_settings: Settings) -> Manager:
    config = Config.of(
        real_settings.model_copy(update={"hf_token": SecretStr("hf_test")}), "ssh-ed25519 AAAA unnoodle-gpu"
    )
    return Manager(engine, pods, shell, config, now=clock.now, sleep=clock.sleep, background=False)


def queue_picture(client: TestClient) -> str:
    params = {"aspect_ratio": "1:1", "quality": "low"}
    response = client.post("/generations", json={"media_type": "image", "prompt": "a teapot", "params": params})
    assert response.status_code == 201, response.text
    generation_id: str = response.json()[0]["id"]
    return generation_id


def queue_video(client: TestClient) -> str:
    params = {"aspect_ratio": "9:16", "quality": "low", "duration_s": 5}
    response = client.post("/generations", json={"media_type": "video", "prompt": "a river", "params": params})
    assert response.status_code == 201, response.text
    generation_id: str = response.json()[0]["id"]
    return generation_id


def live(engine: Engine) -> GpuSession | None:
    with Session(engine) as session:
        return gpu.live_session(session)


def last_session(engine: Engine) -> GpuSession:
    with Session(engine) as session:
        found = session.scalars(select(GpuSession).order_by(GpuSession.created_at.desc())).first()
        assert found is not None
        return found


def generation(engine: Engine, generation_id: str) -> Generation:
    with Session(engine) as session:
        found = session.get(Generation, uuid.UUID(generation_id))
        assert found is not None
        return found


def balance(engine: Engine, client: TestClient) -> int:
    with Session(engine) as session:
        return credits.balance(session, uuid.UUID(client.get("/auth/me").json()["id"]))


def test_nothing_waiting_rents_nothing(manager: Manager, pods: FakePods, engine: Engine) -> None:
    manager.tick()
    assert pods.created == []
    assert live(engine) is None


def test_queued_work_rents_a_gpu_and_gets_it_ready_one_pipeline_at_a_time(
    client: TestClient, manager: Manager, pods: FakePods, shell: FakeShell, engine: Engine
) -> None:
    queue_picture(client)
    seen: list[set[str] | None] = []

    def note_ready(_: object) -> None:
        with Session(engine) as session:
            seen.append(ready_pipelines(session))

    shell.during["models.sh"] = note_ready

    manager.tick()  # asks for a GPU
    manager.tick()  # prepares it (in the tick, in tests)

    # Only this app's own key gets in
    assert pods.created == [("NVIDIA GeForce RTX 5090", "ssh-ed25519 AAAA unnoodle-gpu")]
    # The watchdog goes on before anything that takes long, and the quickest model comes first
    assert [script for script, _ in shell.ran] == ["watchdog.sh", "setup.sh", "models.sh", "models.sh", "models.sh"]
    downloads = [args for script, args in shell.ran if script == "models.sh"]
    assert "Comfy-Org/Krea-2" in downloads[0][0]
    assert "black-forest-labs/FLUX.2-klein-9b-fp8" in downloads[1][0]
    assert "Comfy-Org/MiniMax-H3" in downloads[2][0]
    assert shell.secrets[2] == {"HF_TOKEN": "hf_test"}
    # Each pipeline can run as soon as its models are in, before the next download starts
    assert seen == [set(), {"krea2-turbo"}, {"krea2-turbo", "flux2-klein-edit"}]
    session = last_session(engine)
    assert session.status is GpuStatus.READY
    assert set(session.ready) == set(FILES)

    manager.tick()
    assert shell.tunnel == "pod1"
    assert shell.heartbeats == 1


def test_the_worker_takes_only_what_the_gpu_has_models_for(client: TestClient, engine: Engine) -> None:
    video = queue_video(client)
    picture = queue_picture(client)
    claim = queue.claim_next(engine, {"krea2-turbo"})
    assert claim is not None and str(claim.generation_id) == picture
    assert queue.claim_next(engine, {"krea2-turbo"}) is None
    assert generation(engine, video).status is GenerationStatus.QUEUED


def test_an_idle_gpu_is_handed_back(
    client: TestClient, manager: Manager, pods: FakePods, shell: FakeShell, clock: Clock, engine: Engine
) -> None:
    picture = queue_picture(client)
    manager.tick()
    manager.tick()
    with Session(engine) as session, session.begin():
        found = session.get(Generation, uuid.UUID(picture))
        assert found is not None
        queue.end(session, found, GenerationStatus.DONE)

    clock.sleep(4 * 60)
    manager.tick()
    assert live(engine) is not None

    clock.sleep(61)
    manager.tick()
    assert pods.deleted == ["pod1"]
    assert shell.tunnel is None
    stopped = last_session(engine)
    assert stopped.status is GpuStatus.STOPPED
    assert stopped.stop_reason == "Idle for 5 minutes"


def test_work_keeps_the_gpu(client: TestClient, manager: Manager, pods: FakePods, clock: Clock, engine: Engine) -> None:
    queue_picture(client)
    manager.tick()
    manager.tick()
    for _ in range(4):
        clock.sleep(4 * 60)
        manager.tick()
    assert pods.deleted == []


def test_an_admin_can_stop_it_and_what_waited_gets_its_credits_back(
    client: TestClient, manager: Manager, pods: FakePods, engine: Engine
) -> None:
    make_admin(engine, client.get("/auth/me").json()["id"])
    before = balance(engine, client)
    video = queue_video(client)
    manager.tick()
    manager.tick()

    assert client.post("/admin/gpu/stop").status_code == 200
    manager.tick()
    assert pods.deleted == ["pod1"]
    assert last_session(engine).stop_reason == "Stopped by an admin"
    assert generation(engine, video).status is GenerationStatus.FAILED
    assert balance(engine, client) == before
    # Nothing waits, so nothing starts again
    manager.tick()
    assert len(pods.created) == 1


def used(engine: Engine, hours: float) -> None:
    """Records a session that billed this long, ending now."""
    at = queue.now()
    with Session(engine) as session, session.begin():
        session.add(
            GpuSession(
                status=GpuStatus.STOPPED,
                requested_by="queue",
                launched_at=at - timedelta(hours=hours),
                stopped_at=at,
            )
        )


def test_over_the_daily_limit_generating_is_refused_before_paying(client: TestClient, engine: Engine) -> None:
    used(engine, 2)
    before = balance(engine, client)
    params = {"aspect_ratio": "1:1", "quality": "low"}
    response = client.post("/generations", json={"media_type": "image", "prompt": "a teapot", "params": params})
    assert response.status_code == 503
    assert response.json()["detail"] == "The GPU is resting until tomorrow"
    assert balance(engine, client) == before
    assert client.get("/gpu").json()["state"] == "resting"


def test_work_queued_before_the_limit_ran_out_fails_with_its_credits_back(
    client: TestClient, engine: Engine, pods: FakePods, shell: FakeShell, real_settings: Settings
) -> None:
    before = balance(engine, client)
    picture = queue_picture(client)
    used(engine, 2)
    # On the real clock, like the sessions recorded above
    config = Config.of(real_settings, "key")
    Manager(engine, pods, shell, config, background=False).tick()
    assert pods.created == []
    assert generation(engine, picture).error == gpu.RESTING
    assert balance(engine, client) == before


def test_a_pod_that_never_answers_is_replaced_then_given_up_on(
    client: TestClient, manager: Manager, pods: FakePods, shell: FakeShell, clock: Clock, engine: Engine
) -> None:
    before = balance(engine, client)
    picture = queue_picture(client)
    shell.reachable_pods = False
    manager.tick()
    manager.tick()
    assert len(pods.created) == gpu.LAUNCH_ATTEMPTS
    assert pods.pods == {}
    assert last_session(engine).status is GpuStatus.FAILED
    assert generation(engine, picture).error == gpu.NO_GPU
    assert balance(engine, client) == before

    # New work waits out the cooldown rather than renting straight away
    shell.reachable_pods = True
    queue_picture(client)
    manager.tick()
    assert live(engine) is None
    clock.sleep(gpu.COOLDOWN.total_seconds() + 1)
    manager.tick()
    assert live(engine) is not None


def test_no_free_gpu_is_waited_for_then_given_up_on(
    client: TestClient, manager: Manager, pods: FakePods, engine: Engine
) -> None:
    picture = queue_picture(client)
    pods.no_capacity = True
    manager.tick()
    manager.tick()
    assert last_session(engine).stop_reason == "No GPU of those types was free"
    assert generation(engine, picture).error == gpu.NO_GPU


def test_a_pod_whose_watchdog_wont_start_is_not_used(
    client: TestClient, manager: Manager, pods: FakePods, shell: FakeShell, engine: Engine
) -> None:
    queue_picture(client)
    shell.failing.add("watchdog.sh")
    manager.tick()
    manager.tick()
    assert pods.deleted == ["pod1"]
    assert [script for script, _ in shell.ran] == ["watchdog.sh"]
    assert last_session(engine).status is GpuStatus.FAILED


def test_stray_pods_of_this_app_are_deleted_and_no_one_elses(manager: Manager, pods: FakePods) -> None:
    pods.pods["stray"] = Pod("stray", POD_NAME, "RUNNING", 1.19, None, None)
    pods.pods["mine"] = Pod("mine", "comfyui", "RUNNING", 1.19, None, None)
    manager.tick()
    assert pods.deleted == ["stray"]


def test_what_waiting_people_see(client: TestClient, manager: Manager, engine: Engine) -> None:
    gpu_now = client.get("/gpu").json()
    assert gpu_now["state"] == "asleep"
    assert set(gpu_now["eta_s"]) == set(FILES)
    queue_picture(client)
    manager.tick()
    assert client.get("/gpu").json()["state"] == "starting"
    manager.tick()
    assert client.get("/gpu").json() == {"state": "ready", "phase": None, "ready": sorted(FILES), "eta_s": {}}


def test_admins_see_stats_and_can_start_one(client: TestClient, engine: Engine) -> None:
    assert client.get("/admin/gpu").status_code == 403
    make_admin(engine, client.get("/auth/me").json()["id"])
    assert client.post("/admin/gpu/stop").status_code == 404
    started = client.post("/admin/gpu/start")
    assert started.status_code == 202
    assert started.json()["sessions"][0]["requested_by"] == "me@example.com"
    assert client.post("/admin/gpu/start").status_code == 409
    stats = client.get("/admin/gpu").json()
    assert stats["daily_limit_s"] == 7200
    assert stats["idle_stop_s"] == 300


def test_with_gpus_off_nothing_is_said_about_them(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        sign_up(client)
        assert client.get("/gpu").json()["state"] == "off"


def test_every_model_file_the_real_pipelines_load_is_downloaded() -> None:
    source = (Path(__file__).parents[1] / "app" / "catalogues" / "real.py").read_text()
    loaded = set(re.findall(r'"([\w.\-]+\.safetensors)"', source))
    downloaded = {Path(f).name for sources in FILES.values() for s in sources for f in s.files}
    assert loaded and loaded <= downloaded


def test_a_pod_that_went_away_meanwhile_is_replaced(
    client: TestClient, manager: Manager, pods: FakePods, shell: FakeShell, engine: Engine
) -> None:
    queue_picture(client)
    manager.tick()
    manager.tick()
    # Its watchdog deleted it while this process was away
    del pods.pods["pod1"]
    shell.reachable_pods = False
    manager.tick()
    gone = last_session(engine)
    assert gone.status is GpuStatus.STOPPED
    assert gone.stop_reason == "The pod was gone"
    # Or it would count towards today's GPU time for ever
    assert gone.stopped_at is not None
    assert shell.tunnel is None

    # The picture still waits, so the next tick asks for another
    shell.reachable_pods = True
    manager.tick()
    manager.tick()
    assert len(pods.created) == 2
    assert last_session(engine).status is GpuStatus.READY
