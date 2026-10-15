"""The worker: python -m app.worker

Takes queued generations one at a time and runs them on ComfyUI. Several workers can share a queue (and a ComfyUI each,
or one between them); the claim in app.worker.queue keeps them from taking the same job.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import psycopg
from sqlalchemy.engine import make_url

from app.db import make_engine
from app.media import MediaStore
from app.settings import Settings
from app.worker import queue
from app.worker.comfy import ComfyClient
from app.worker.runner import run_job
from app.workflows import load_workflows

logger = logging.getLogger("app.worker")

# Fallback for missed notifications, and how often stale leases are looked for
POLL_S = 5
# How long to wait before trying an unreachable ComfyUI again
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # One line per request to ComfyUI would bury the worker's own
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    engine = make_engine(settings.database_url)
    workflows = load_workflows(settings.workflows)
    store = MediaStore(settings.media_dir)
    comfy = ComfyClient(settings.comfyui_url)
    logger.info("Started with %d workflows; ComfyUI at %s", len(workflows), settings.comfyui_url)

    with wake_on_queued(settings.database_url) as wait:
        while True:
            claim = queue.claim_next(engine)
            if claim is None:
                wait(POLL_S)
                continue
            logger.info("Running generation %s (attempt %d)", claim.generation_id, claim.attempt)
            started = time.monotonic()
            try:
                outcome = run_job(engine, claim, workflows, store, comfy)
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
