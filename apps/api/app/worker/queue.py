"""The job queue, which is the generations table.

A worker claims the oldest queued generation with SELECT ... FOR UPDATE SKIP LOCKED, so several workers never take
the same one, and marks it running in the same short transaction. From then on the claim is a lease: the worker
refreshes heartbeat_at while it runs the job, and a running generation whose heartbeat has gone stale belongs to a
worker that died, so it is claimed again, up to MAX_ATTEMPTS times.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, Engine, or_, select, text, update
from sqlalchemy.orm import Session

from app.models import Generation, GenerationStatus

STALE_AFTER = timedelta(seconds=60)
MAX_ATTEMPTS = 3

# Sent by the API when it queues a generation, so an idle worker starts at once instead of at its next poll
CHANNEL = "generations_queued"


@dataclass(frozen=True)
class Claim:
    generation_id: uuid.UUID
    # Which attempt this worker holds; finishing checks it still holds the lease
    attempt: int


def now() -> datetime:
    return datetime.now(UTC)


def notify_queued(session: Session) -> None:
    # Postgres delivers it when the transaction commits, so a worker never wakes before the row is visible
    session.execute(text(f"NOTIFY {CHANNEL}"))


def claim_next(engine: Engine) -> Claim | None:
    with Session(engine) as session, session.begin():
        stale = (Generation.status == GenerationStatus.RUNNING) & (Generation.heartbeat_at < now() - STALE_AFTER)
        query = (
            select(Generation)
            .where(or_(Generation.status == GenerationStatus.QUEUED, stale))
            .order_by(Generation.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        while (generation := session.scalars(query).first()) is not None:
            if generation.attempts >= MAX_ATTEMPTS:
                end(generation, GenerationStatus.FAILED, "The worker stopped while running this, too many times")
                session.flush()
                continue
            generation.status = GenerationStatus.RUNNING
            generation.attempts += 1
            generation.started_at = generation.heartbeat_at = now()
            generation.progress = 0
            generation.comfy_prompt_id = None
            return Claim(generation.id, generation.attempts)
    return None


def beat(engine: Engine, claim: Claim, progress: float | None = None) -> None:
    """Renews the lease, and records progress when there is some."""
    values: dict[str, object] = {"heartbeat_at": now()}
    if progress is not None:
        values["progress"] = min(max(progress, 0.0), 1.0)
    with Session(engine) as session, session.begin():
        session.execute(update(Generation).where(*held(claim)).values(values))


def release(engine: Engine, claim: Claim) -> None:
    """Puts a job back in the queue without counting the attempt, for when ComfyUI couldn't be reached."""
    with Session(engine) as session, session.begin():
        session.execute(
            update(Generation)
            .where(*held(claim))
            .values(
                status=GenerationStatus.QUEUED,
                attempts=Generation.attempts - 1,
                progress=None,
                started_at=None,
                heartbeat_at=None,
            )
        )


def lock_held(session: Session, claim: Claim) -> Generation | None:
    """The claimed generation, locked for finishing, or None if this worker has lost the lease to another."""
    query = select(Generation).where(*held(claim)).with_for_update()
    return session.scalars(query).first()


def end(generation: Generation, status: GenerationStatus, error: str | None = None) -> None:
    generation.status = status
    generation.error = error
    generation.progress = None
    generation.heartbeat_at = None
    generation.finished_at = now()


def held(claim: Claim) -> tuple[ColumnElement[bool], ...]:
    return (
        Generation.id == claim.generation_id,
        Generation.status == GenerationStatus.RUNNING,
        Generation.attempts == claim.attempt,
    )
