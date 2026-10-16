"""The worker: python -m app.worker

Takes queued generations one at a time and runs them on the renderer. Several workers can share a queue (and a renderer
each, or one between them); the claim in app.worker.queue keeps them from taking the same job.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db import make_engine
from app.gpu.manager import ready_pipelines
from app.media import MediaStore
from app.pipelines import load_pipelines
from app.settings import Settings
from app.worker import queue
from app.worker.renderer import RendererClient
from app.worker.runner import run_job

logger = logging.getLogger("app.worker")

# Fallback for missed notifications, and how often stale leases are looked for
POLL_S = 5
# How long to wait before trying an unreachable renderer again
BACKOFF_S = 5


@contextmanager
def wake_on_queued(database_url: str) -> Iterator[Callable[[float], None]]:
    """Yields a wait function that returns when the API queues something, or after the timeout."""
    # psycopg wants a plain libpq URL, without SQLAlchemy's "+psycopg" driver suffix
    url = make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(f"LISTEN {queue.CHANNEL}")

        def wait(timeout: float) -> None:
            for _ in connection.notifies(timeout=timeout, stop_after=1):
                pass

        yield wait


def gpu_pipelines(engine: Engine) -> set[str]:
    with Session(engine) as session:
        return ready_pipelines(session) or set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # One line per request to the renderer would bury the worker's own
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    engine = make_engine(settings.database_url)
    pipelines = load_pipelines(settings.pipelines)
    store = MediaStore(settings.media_dir)
    renderer = RendererClient(settings.renderer_url)
    logger.info("Started with %d pipelines; renderer at %s", len(pipelines), settings.renderer_url)

    with wake_on_queued(settings.database_url) as wait:
        while True:
            # With a rented GPU, only what its models are in for; nothing while there's none
            ready = gpu_pipelines(engine) if settings.gpu == "runpod" else None
            claim = None if ready == set() else queue.claim_next(engine, ready)
            if claim is None:
                wait(POLL_S)
                continue
            logger.info("Running generation %s (attempt %d)", claim.generation_id, claim.attempt)
            started = time.monotonic()
            try:
                outcome = run_job(engine, claim, pipelines, store, renderer)
            except KeyboardInterrupt:
                # Back in the queue for the next worker rather than waiting out a stale lease
                queue.release(engine, claim)
                raise
            logger.info("Generation %s %s in %.1fs", claim.generation_id, outcome, time.monotonic() - started)
            if outcome == "released":
                time.sleep(BACKOFF_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped")
