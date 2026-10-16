"""Running one claimed generation: fill its workflow in, run it on ComfyUI, store what it made."""

import logging
import time
import uuid
from pathlib import PurePath
from typing import Literal

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.media import MediaStore, Stored, store_image, store_video
from app.models import Asset, AssetSource, Generation, GenerationStatus, InputRole
from app.video import VideoError
from app.worker import queue
from app.worker.comfy import Comfy, ComfyFailed, ComfyRejected, ComfyUnavailable, OutputFile
from app.workflows import Job, JobInput, Workflow, ratio_of

logger = logging.getLogger(__name__)

PROGRESS_EVERY_S = 0.5

# A run is stopped after this many times its estimate, and never sooner than MIN_TIME_LIMIT_S, which leaves room to
# load a model, which the estimates leave out
TIME_LIMIT_FACTOR = 3
MIN_TIME_LIMIT_S = 120


class TooLong(Exception):
    """A run that went past its time limit."""


Outcome = Literal["done", "failed", "released", "lost"]


def run_job(
    engine: Engine, claim: queue.Claim, workflows: dict[str, Workflow], store: MediaStore, comfy: Comfy
) -> Outcome:
    with Session(engine, expire_on_commit=False) as session:
        generation = session.get_one(Generation, claim.generation_id)
        workflow = workflows.get(generation.workflow_id)
        if workflow is None:
            return fail(engine, claim, "The workflow this used is no longer installed")
        attached = [(i.role, i.asset) for i in generation.inputs]
        # Recorded before submitting, so the run can be found in ComfyUI (to cancel it, say) whatever happens next
        prompt_id = str(uuid.uuid4())
        generation.comfy_prompt_id = prompt_id
        session.commit()

    try:
        inputs = tuple(upload(store, comfy, role, asset) for role, asset in attached)
        graph = workflow.build(job_for(generation, workflow, inputs))
        assert graph.output_node is not None, f"{workflow.id} built a graph that saves nothing"
        progress = ProgressWriter(engine, claim, time_limit_s(generation.estimated_s))
        files = comfy.run(graph.nodes, prompt_id, graph.output_node, progress.update, progress.beat)
        if not files:
            raise ComfyFailed("This finished without making anything")
        outputs = [
            store_output(store, comfy, file, f"outputs/{generation.id}/{claim.attempt}-{n}")
            for n, file in enumerate(files)
        ]
    except TooLong:
        logger.warning("Generation %s went past its time limit; stopping it", generation.id)
        try:
            comfy.stop(prompt_id)
        except ComfyUnavailable as error:
            logger.warning("Couldn't stop generation %s in ComfyUI: %s", generation.id, error)
        return fail(engine, claim, "This took much longer than it should, so it was stopped. Try again.")
    except ComfyUnavailable as error:
        logger.warning("ComfyUI unreachable, putting generation %s back in the queue: %s", generation.id, error)
        queue.release(engine, claim)
        return "released"
    except ComfyRejected as error:
        logger.error("ComfyUI refused workflow %s: %s", workflow.id, error)
        return fail(engine, claim, "Something is wrong on our side, so this couldn't start")
    except ComfyFailed as error:
        logger.info("Generation %s failed in %s: %s", generation.id, error.node_type, error)
        return fail(engine, claim, failure_message(error))
    except Exception:
        logger.exception("Generation %s failed", generation.id)
        return fail(engine, claim, "Something went wrong while making this. Try again.")
    return finish(engine, claim, outputs)


def upload(store: MediaStore, comfy: Comfy, role: InputRole, asset: Asset) -> JobInput:
    data = store.path(asset.storage_key).read_bytes()
    name = comfy.upload(data, f"{asset.id}{PurePath(asset.storage_key).suffix}")
    return JobInput(role, asset.media_type, name, (asset.width, asset.height))


def job_for(generation: Generation, workflow: Workflow, inputs: tuple[JobInput, ...]) -> Job:
    if generation.aspect_ratio is not None:
        ratio = ratio_of(generation.aspect_ratio)
    else:
        # The shape of the first attachment; a request without any had to name a shape
        first = generation.inputs[0].asset
        ratio = (first.width, first.height)
    duration_s = generation.duration_s
    return Job(
        prompt=generation.prompt,
        seed=generation.seed,
        megapixels=workflow.megapixels[generation.quality],
        size=workflow.size(generation.quality, ratio),
        frames=None if duration_s is None else workflow.frames[round(duration_s)],
        inputs=inputs,
        filename_prefix=f"unnoodle/{generation.id}",
        estimated_s=generation.estimated_s,
    )


def store_output(store: MediaStore, comfy: Comfy, file: OutputFile, key_stem: str) -> Stored:
    data = comfy.download(file)
    try:
        return store_image(store, data, key_stem) or store_video(store, data, key_stem, clip=False)
    except VideoError as error:
        logger.error("Can't store %s: %s", file.filename, error)
        raise ComfyFailed("This made a kind of file the app can't show yet") from error


def failure_message(error: ComfyFailed) -> str:
    """What the person sees. ComfyUI's own messages name nodes and tensors, so they go to the log instead."""
    if error.exception_type and "OutOfMemory" in error.exception_type:
        return "This was too big to make. Try a lower quality, a shorter length or fewer at a time."
    if error.node_type is None and str(error):
        # Ours, already in plain words
        return str(error).splitlines()[0]
    return "Something went wrong while making this. Try again."


def time_limit_s(estimated_s: float) -> float:
    return max(TIME_LIMIT_FACTOR * estimated_s, MIN_TIME_LIMIT_S)


class ProgressWriter:
    """Writes progress to the database at most every PROGRESS_EVERY_S, renewing the lease each time. Raises TooLong
    once the run has gone past its time limit: ComfyUI reports progress, or goes quiet, often enough for that to be
    checked here."""

    def __init__(self, engine: Engine, claim: queue.Claim, time_limit_s: float) -> None:
        self.engine, self.claim = engine, claim
        self.written_at = 0.0
        self.deadline = time.monotonic() + time_limit_s

    def update(self, fraction: float) -> None:
        self.check_time()
        if fraction >= 1 or time.monotonic() - self.written_at >= PROGRESS_EVERY_S:
            queue.beat(self.engine, self.claim, fraction)
            self.written_at = time.monotonic()

    def beat(self) -> None:
        self.check_time()
        queue.beat(self.engine, self.claim)

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            raise TooLong


def finish(engine: Engine, claim: queue.Claim, outputs: list[Stored]) -> Outcome:
    with Session(engine) as session, session.begin():
        generation = queue.lock_held(session, claim)
        if generation is None:
            logger.warning(
                "Lost the lease on generation %s before finishing; its outputs are dropped", claim.generation_id
            )
            return "lost"
        for output in outputs:
            session.add(
                Asset(
                    owner_id=generation.owner_id,
                    source=AssetSource.GENERATION,
                    generation_id=generation.id,
                    **output.fields(),
                )
            )
        queue.end(session, generation, GenerationStatus.DONE)
    return "done"


def fail(engine: Engine, claim: queue.Claim, message: str) -> Outcome:
    with Session(engine) as session, session.begin():
        generation = queue.lock_held(session, claim)
        if generation is None:
            return "lost"
        queue.end(session, generation, GenerationStatus.FAILED, message)
    return "failed"
