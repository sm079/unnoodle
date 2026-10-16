"""The rented GPU as people see it: where it is for anyone waiting on it, and stats and a stop button for admins."""

import statistics
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts import AdminUser, CurrentUser, SettingsDep
from app.db import SessionDep
from app.gpu.files import FILES
from app.gpu.manager import LIVE, USABLE, live_session, used_today
from app.models import GpuSession, GpuStatus
from app.settings import Settings
from app.worker.queue import now

# How long after being asked for each pipeline's models are usually in, until there are sessions to go by
GUESS = {"krea2-turbo": 300.0, "flux2-klein-edit": 420.0, "minimax-h3": 660.0}
# The most recent sessions the guesses are taken from
RECENT = 10

GpuState = Literal["off", "asleep", "starting", "ready", "resting"]


class GpuOut(BaseModel):
    """off: no GPU is rented here (a renderer is run by hand); asleep: none is up, and the next generation starts one;
    starting: one is being got ready; ready: it runs what's in ready; resting: today's GPU time is used up."""

    state: GpuState
    # While starting: "waiting-for-gpu", "launching", "setup", or "models:<pipeline>"
    phase: str | None
    ready: list[str]
    # About how many seconds until each pipeline that isn't ready yet can run
    eta_s: dict[str, float]


class GpuSessionOut(BaseModel):
    id: uuid.UUID
    status: GpuStatus
    phase: str | None
    ready: dict[str, str]
    requested_by: str
    gpu_type: str | None
    cost_per_hour: float | None
    stop_reason: str | None
    stop_requested: bool
    created_at: datetime
    launched_at: datetime | None
    active_at: datetime | None
    stopped_at: datetime | None
    # Billed so far, in seconds and dollars
    billed_s: float
    cost: float | None


class AdminGpuOut(BaseModel):
    enabled: bool
    gpu: GpuOut
    used_today_s: float
    daily_limit_s: float
    idle_stop_s: float
    # Until the idle stop, while a usable GPU has nothing to do
    idle_left_s: float | None
    sessions: list[GpuSessionOut]


def resting(session: Session, settings: Settings) -> bool:
    used = used_today(session, now(), ZoneInfo(settings.gpu_day_timezone))
    return used.total_seconds() >= settings.gpu_daily_limit_s


def gpu_state(session: Session, settings: Settings) -> GpuOut:
    if settings.gpu == "off":
        return GpuOut(state="off", phase=None, ready=[], eta_s={})
    live = live_session(session)
    if resting(session, settings):
        return GpuOut(state="resting", phase=None, ready=[], eta_s={})
    if live is None:
        return GpuOut(state="asleep", phase=None, ready=[], eta_s=estimates(session))
    elapsed = (now() - live.created_at).total_seconds()
    eta = {p: max(30.0, s - elapsed) for p, s in estimates(session).items() if p not in live.ready}
    state: GpuState = "ready" if live.status is GpuStatus.READY else "starting"
    return GpuOut(state=state, phase=live.phase, ready=sorted(live.ready), eta_s=eta)


def estimates(session: Session) -> dict[str, float]:
    """Seconds from asking for a GPU until each pipeline could run, the median of recent sessions."""
    recent = session.scalars(
        select(GpuSession).where(GpuSession.ready != {}).order_by(GpuSession.created_at.desc()).limit(RECENT)
    ).all()
    out = {}
    for pipeline in FILES:
        seen = [
            (datetime.fromisoformat(s.ready[pipeline]) - s.created_at).total_seconds()
            for s in recent
            if pipeline in s.ready
        ]
        out[pipeline] = statistics.median(seen) if seen else GUESS[pipeline]
    return out


def session_out(s: GpuSession, at: datetime) -> GpuSessionOut:
    billed = ((s.stopped_at or at) - s.launched_at).total_seconds() if s.launched_at else 0.0
    return GpuSessionOut(
        id=s.id,
        status=s.status,
        phase=s.phase,
        ready=s.ready,
        requested_by=s.requested_by,
        gpu_type=s.gpu_type,
        cost_per_hour=s.cost_per_hour,
        stop_reason=s.stop_reason,
        stop_requested=s.stop_requested,
        created_at=s.created_at,
        launched_at=s.launched_at,
        active_at=s.active_at,
        stopped_at=s.stopped_at,
        billed_s=billed,
        cost=round(billed / 3600 * s.cost_per_hour, 2) if s.cost_per_hour is not None else None,
    )


router = APIRouter()


@router.get("/gpu")
def get_gpu(_: CurrentUser, session: SessionDep, settings: SettingsDep) -> GpuOut:
    return gpu_state(session, settings)


@router.get("/admin/gpu", responses={403: {"description": "Not an admin"}})
def get_admin_gpu(_: AdminUser, session: SessionDep, settings: SettingsDep) -> AdminGpuOut:
    at = now()
    live = live_session(session)
    idle_left = None
    if live is not None and live.status in USABLE and live.active_at is not None:
        idle_left = max(0.0, settings.gpu_idle_stop_s - (at - live.active_at).total_seconds())
    sessions = session.scalars(select(GpuSession).order_by(GpuSession.created_at.desc()).limit(RECENT)).all()
    return AdminGpuOut(
        enabled=settings.gpu != "off",
        gpu=gpu_state(session, settings),
        used_today_s=used_today(session, at, ZoneInfo(settings.gpu_day_timezone)).total_seconds(),
        daily_limit_s=settings.gpu_daily_limit_s,
        idle_stop_s=settings.gpu_idle_stop_s,
        idle_left_s=idle_left,
        sessions=[session_out(s, at) for s in sessions],
    )


@router.post(
    "/admin/gpu/start",
    status_code=status.HTTP_202_ACCEPTED,
    responses={403: {"description": "Not an admin"}, 409: {"description": "Already up"}, 503: {"description": "Off"}},
)
def start_gpu(user: AdminUser, session: SessionDep, settings: SettingsDep) -> AdminGpuOut:
    """Asks for a GPU now, before anything is queued (it stops again after the idle time)."""
    if settings.gpu == "off":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Renting GPUs is off here")
    if resting(session, settings):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Today's GPU time is used up")
    if live_session(session) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A GPU is already up or on its way")
    session.add(GpuSession(status=GpuStatus.REQUESTED, requested_by=user.email))
    session.commit()
    return get_admin_gpu(user, session, settings)


@router.post(
    "/admin/gpu/stop",
    responses={403: {"description": "Not an admin"}, 404: {"description": "None up"}},
)
def stop_gpu(user: AdminUser, session: SessionDep, settings: SettingsDep) -> AdminGpuOut:
    """Hands the GPU back now. Anything waiting for it fails with its credits back."""
    live = session.scalars(select(GpuSession).where(GpuSession.status.in_(LIVE)).with_for_update()).first()
    if live is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No GPU is up")
    live.stop_requested = True
    session.commit()
    return get_admin_gpu(user, session, settings)
