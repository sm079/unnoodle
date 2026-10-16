"""Renting a GPU only while there is work for it.

The GPU process (python -m app.gpu) calls Manager.tick every few seconds. A tick looks at the queue and the live
session (app.models.GpuSession) and decides:

- Queued work and no GPU: ask for one, unless today's limit is used up (the work fails and gets its credits back) or
  the last attempt failed only moments ago.
- A GPU being prepared: launching, setting up and downloading models happen in a thread (Preparation), one pipeline's
  models at a time, so a picture can run before the video model is in.
- A usable GPU: keep the tunnel to its renderer open, tell the pod's watchdog this process is alive, note when it last
  had work, and hand it back after settings.gpu_idle_stop_s with none.
- Stopped by an admin, or over the daily limit: hand it back and fail what was waiting for it, with credits back.

Every few minutes it also deletes any pod with this app's name that isn't the live session's, so a crash between
renting and recording can't leave one billing. The pod's watchdog (remote/watchdog.sh) covers this process itself
going away.
"""

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, func, or_, select, update
from sqlalchemy.orm import Session

from app.gpu.files import FILES
from app.gpu.remote import Shell
from app.gpu.runpod import POD_NAME, NoCapacity, Pod, Pods, RunPodError
from app.models import Generation, GenerationStatus, GpuSession, GpuStatus
from app.settings import Settings
from app.worker import queue

logger = logging.getLogger(__name__)

# The renderer release the real pipelines were checked against
RELEASE = "v0.39.1"
LIVE = (GpuStatus.REQUESTED, GpuStatus.LAUNCHING, GpuStatus.PREPARING, GpuStatus.READY)
USABLE = (GpuStatus.PREPARING, GpuStatus.READY)

HEARTBEAT_EVERY = timedelta(minutes=1)
# The pod deletes itself after this long without a heartbeat (remote/watchdog.sh)
WATCHDOG_S = 600
ORPHANS_EVERY = timedelta(minutes=3)
# After a failed attempt, queued work waits this long before another GPU is rented for it
COOLDOWN = timedelta(minutes=10)
LAUNCH_ATTEMPTS = 3
# How long to keep asking for a GPU type that has none free
CAPACITY_WAIT_S = 600
SSH_WAIT_S = 360

RESTING = "The GPU is resting until tomorrow. Your credits are back."
STOPPED = "The GPU was stopped before this ran. Your credits are back."
NO_GPU = "Couldn't get a GPU just now. Your credits are back; try again in a few minutes."


@dataclass(frozen=True)
class Config:
    gpu_types: list[str]
    idle_stop: timedelta
    daily_limit: timedelta
    timezone: ZoneInfo
    public_key: str
    hf_token: str | None

    @classmethod
    def of(cls, settings: Settings, public_key: str) -> Config:
        return cls(
            gpu_types=settings.gpu_types,
            idle_stop=timedelta(seconds=settings.gpu_idle_stop_s),
            daily_limit=timedelta(seconds=settings.gpu_daily_limit_s),
            timezone=ZoneInfo(settings.gpu_day_timezone),
            public_key=public_key,
            hf_token=settings.hf_token.get_secret_value() if settings.hf_token else None,
        )


def live_session(session: Session) -> GpuSession | None:
    return session.scalars(select(GpuSession).where(GpuSession.status.in_(LIVE))).first()


def used_today(session: Session, now: datetime, timezone: ZoneInfo) -> timedelta:
    """GPU time billed since the day began where the app's people are."""
    day = now.astimezone(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = session.scalars(
        select(GpuSession).where(
            GpuSession.launched_at.is_not(None),
            or_(GpuSession.stopped_at.is_(None), GpuSession.stopped_at > day),
        )
    ).all()
    used = timedelta()
    for s in sessions:
        assert s.launched_at is not None
        start = max(s.launched_at, day)
        end = s.stopped_at or now
        if end > start:
            used += end - start
    return used


def ready_pipelines(session: Session) -> set[str] | None:
    """What the worker may run: the pipelines whose models are on the live GPU, or None when there is no usable one."""
    live = live_session(session)
    if live is None or live.status not in USABLE:
        return None
    return set(live.ready)


class Manager:
    def __init__(
        self,
        engine: Engine,
        pods: Pods,
        shell: Shell,
        config: Config,
        now: Callable[[], datetime] = queue.now,
        sleep: Callable[[float], None] = time.sleep,
        background: bool = True,
    ) -> None:
        self.engine = engine
        self.pods = pods
        self.shell = shell
        self.config = config
        self.now = now
        self.sleep = sleep
        # Tests run preparation in the tick itself
        self.background = background
        self.preparation: Preparation | None = None
        self.last_heartbeat: datetime | None = None
        self.last_orphan_check: datetime | None = None

    def tick(self) -> None:
        now = self.now()
        with Session(self.engine) as session:
            live = live_session(session)
            self.check_orphans(now, live)
            if live is None:
                self.close_down()
                self.maybe_request(session, now)
                return
            over = used_today(session, now, self.config.timezone) >= self.config.daily_limit
            if live.stop_requested:
                return self.stop(session, live, "Stopped by an admin", then_fail=STOPPED)
            if over:
                fail_waiting(session, RESTING)
                if not running(session):
                    return self.stop(session, live, "Daily GPU limit reached")
            if live.status in (GpuStatus.REQUESTED, GpuStatus.LAUNCHING, GpuStatus.PREPARING):
                self.ensure_preparing(live.id)
            if live.status in USABLE and live.ready:
                self.keep_alive(session, live, now)

    # What to do with no GPU

    def maybe_request(self, session: Session, now: datetime) -> None:
        if not waiting(session):
            return
        if used_today(session, now, self.config.timezone) >= self.config.daily_limit:
            fail_waiting(session, RESTING)
            return
        last = session.scalars(select(GpuSession).order_by(GpuSession.created_at.desc()).limit(1)).first()
        if (
            last is not None
            and last.status is GpuStatus.FAILED
            and last.stopped_at
            and now - last.stopped_at < COOLDOWN
        ):
            return
        session.add(GpuSession(status=GpuStatus.REQUESTED, requested_by="queue"))
        session.commit()
        logger.info("Work is waiting; asking for a GPU")

    # Keeping a usable GPU

    def keep_alive(self, session: Session, live: GpuSession, now: datetime) -> None:
        pod = self.pod_of(live)
        if not self.shell.tunnel_open():
            self.shell.open_tunnel(pod)
        if self.last_heartbeat is None or now - self.last_heartbeat >= HEARTBEAT_EVERY:
            if self.shell.heartbeat(pod):
                self.last_heartbeat = now
            else:
                logger.warning("No heartbeat to pod %s", live.pod_id)
        if running(session) or waiting(session):
            set_session(self.engine, live.id, active_at=now)
        elif live.active_at is not None and now - live.active_at >= self.config.idle_stop:
            minutes = round(self.config.idle_stop.total_seconds() / 60)
            self.stop(session, live, f"Idle for {minutes} minutes")

    def pod_of(self, live: GpuSession) -> Pod:
        assert live.pod_id is not None and live.ip is not None and live.ssh_port is not None
        return Pod(live.pod_id, POD_NAME, "RUNNING", live.cost_per_hour, live.ip, live.ssh_port)

    # Handing it back

    def stop(self, session: Session, live: GpuSession, reason: str, then_fail: str | None = None) -> None:
        logger.info("Stopping the GPU: %s", reason)
        if self.preparation is not None:
            self.preparation.cancel.set()
        self.shell.close_tunnel()
        if live.pod_id is not None:
            try:
                self.pods.delete(live.pod_id)
            except RunPodError:
                # Tried again next tick, since the session stays live
                logger.exception("Couldn't delete pod %s", live.pod_id)
                return
        set_session(
            self.engine, live.id, status=GpuStatus.STOPPED, phase=None, stop_reason=reason, stopped_at=self.now()
        )
        if then_fail is not None:
            fail_waiting(session, then_fail, include_running=True)
        self.last_heartbeat = None

    def close_down(self) -> None:
        self.shell.close_tunnel()
        self.preparation = None

    def check_orphans(self, now: datetime, live: GpuSession | None) -> None:
        if self.last_orphan_check is not None and now - self.last_orphan_check < ORPHANS_EVERY:
            return
        self.last_orphan_check = now
        try:
            for pod in self.pods.list():
                if pod.name == POD_NAME and (live is None or pod.id != live.pod_id):
                    logger.warning("Deleting pod %s, which no session owns", pod.id)
                    self.pods.delete(pod.id)
        except RunPodError:
            logger.exception("Checking for stray pods failed")

    # Preparing

    def ensure_preparing(self, session_id: uuid.UUID) -> None:
        if self.preparation is not None and self.preparation.session_id == session_id and not self.preparation.done:
            return
        self.preparation = Preparation(self, session_id)
        if self.background:
            threading.Thread(target=self.preparation.run, name="gpu-preparation", daemon=True).start()
        else:
            self.preparation.run()


class Preparation:
    """Rents a pod and gets it ready, one step at a time, giving up when cancelled. Picks up where it was when this
    process restarted part way: a recorded pod is reused, and setup and downloads skip what's already done."""

    def __init__(self, manager: Manager, session_id: uuid.UUID) -> None:
        self.manager = manager
        self.session_id = session_id
        self.cancel = threading.Event()
        self.done = False

    def run(self) -> None:
        try:
            self.prepare()
        except Exception:
            logger.exception("Preparing the GPU failed")
            self.fail(NO_GPU, "Preparing the GPU failed; see the GPU process log")
        finally:
            self.done = True

    def prepare(self) -> None:
        m = self.manager
        with Session(m.engine) as session:
            live = session.get(GpuSession, self.session_id)
            assert live is not None
            pod = m.pod_of(live) if live.pod_id and live.ip and live.ssh_port else None
            done = dict(live.ready)
        if pod is None or not m.shell.reachable(pod):
            pod = self.launch()
            if pod is None:
                return
        set_session(m.engine, self.session_id, status=GpuStatus.PREPARING, phase="setup")
        code, output = m.shell.run(pod, "watchdog.sh", str(WATCHDOG_S))
        if code != 0:
            # Without it a GPU process that goes away leaves the pod billing, so this pod isn't used
            logger.error("The pod's watchdog didn't start:\n%s", output[-2000:])
            return self.fail(NO_GPU, "The pod's watchdog didn't start")
        code, output = m.shell.run(pod, "setup.sh", RELEASE)
        if code != 0 or self.cancel.is_set():
            logger.error("Setting up the renderer failed:\n%s", output[-2000:])
            return self.fail(NO_GPU, "Setting up the renderer failed")
        for pipeline, sources in FILES.items():
            if pipeline in done:
                continue
            set_session(m.engine, self.session_id, phase=f"models:{pipeline}")
            secrets = {"HF_TOKEN": m.config.hf_token} if m.config.hf_token else None
            code, output = m.shell.run(pod, "models.sh", *(s.spec for s in sources), secrets=secrets)
            if self.cancel.is_set():
                return
            if code != 0:
                logger.error("Downloading the models for %s failed:\n%s", pipeline, output[-2000:])
                return self.fail(NO_GPU, f"Downloading the models for {pipeline} failed")
            done[pipeline] = m.now().isoformat()
            # Ready to run from here; the first one also starts the idle clock
            with Session(m.engine) as session:
                live = session.get(GpuSession, self.session_id)
                assert live is not None
                set_session(m.engine, self.session_id, ready=dict(done), active_at=live.active_at or m.now())
        set_session(m.engine, self.session_id, status=GpuStatus.READY, phase=None)
        logger.info("The GPU is ready")

    def launch(self) -> Pod | None:
        m = self.manager
        for attempt in range(1, LAUNCH_ATTEMPTS + 1):
            set_session(m.engine, self.session_id, status=GpuStatus.LAUNCHING, phase="launching")
            created = self.create()
            if created is None:
                return None
            set_session(
                m.engine,
                self.session_id,
                phase="launching",
                pod_id=created.id,
                gpu_type=created.gpu_type,
                cost_per_hour=created.cost_per_hour,
                launched_at=m.now(),
            )
            pod = self.wait_for_ssh(created.id)
            if pod is not None:
                set_session(m.engine, self.session_id, ip=pod.ip, ssh_port=pod.ssh_port)
                return pod
            if self.cancel.is_set():
                return None
            # Usually stuck pulling the template on a host without it cached; it bills meanwhile, so replace it
            logger.warning("Pod %s never answered over SSH (attempt %d of %d)", created.id, attempt, LAUNCH_ATTEMPTS)
            m.pods.delete(created.id)
        self.fail(NO_GPU, "No pod answered over SSH")
        return None

    def create(self) -> Pod | None:
        m = self.manager
        waited = 0.0
        while not self.cancel.is_set():
            try:
                return m.pods.create(m.config.gpu_types, m.config.public_key)
            except NoCapacity as error:
                logger.info("No GPU free yet: %s", str(error)[:300])
                if waited >= CAPACITY_WAIT_S:
                    self.fail(NO_GPU, "No GPU of those types was free")
                    return None
                set_session(m.engine, self.session_id, phase="waiting-for-gpu")
                m.sleep(30)
                waited += 30
        return None

    def wait_for_ssh(self, pod_id: str) -> Pod | None:
        m = self.manager
        waited = 0.0
        while waited < SSH_WAIT_S and not self.cancel.is_set():
            pod = m.pods.get(pod_id)
            if pod is not None and pod.ip and pod.ssh_port and m.shell.reachable(pod):
                return pod
            m.sleep(5)
            waited += 5
        return None

    def fail(self, message: str, reason: str) -> None:
        m = self.manager
        with Session(m.engine) as session:
            live = session.get(GpuSession, self.session_id)
            if live is None or live.status not in LIVE:
                return
            if live.pod_id is not None:
                try:
                    m.pods.delete(live.pod_id)
                except RunPodError:
                    logger.exception("Couldn't delete pod %s; the stray check will", live.pod_id)
            set_session(
                m.engine, self.session_id, status=GpuStatus.FAILED, phase=None, stop_reason=reason, stopped_at=m.now()
            )
            # What can still run elsewhere is nothing: with no GPU, all of it fails
            fail_waiting(session, message, include_running=True)
        logger.error("GPU session failed: %s", reason)


def set_session(engine: Engine, session_id: uuid.UUID, **values: object) -> None:
    """Changes only the columns given, and only while the session is live: the tick and the preparation thread never
    undo each other's changes, and a preparation that was cancelled can't bring a stopped session back."""
    with Session(engine) as session, session.begin():
        session.execute(
            update(GpuSession).where(GpuSession.id == session_id, GpuSession.status.in_(LIVE)).values(values)
        )


def waiting(session: Session) -> bool:
    return session.scalar(select(func.count()).where(Generation.status == GenerationStatus.QUEUED)) != 0


def running(session: Session) -> bool:
    return session.scalar(select(func.count()).where(Generation.status == GenerationStatus.RUNNING)) != 0


def fail_waiting(session: Session, message: str, include_running: bool = False) -> None:
    """Ends the generations no GPU will run, with their credits back."""
    statuses = [GenerationStatus.QUEUED, GenerationStatus.RUNNING] if include_running else [GenerationStatus.QUEUED]
    generations = session.scalars(select(Generation).where(Generation.status.in_(statuses)).with_for_update()).all()
    for generation in generations:
        queue.end(session, generation, GenerationStatus.FAILED, message)
    session.commit()
    if generations:
        logger.info("Failed %d waiting generations: %s", len(generations), message)
