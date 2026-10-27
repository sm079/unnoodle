"""Running one claimed generation: fill its pipeline in, run it on the renderer, store what it made."""

import logging
import time
import uuid
from pathlib import PurePath
from typing import Literal

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.media import MediaStore, Stored, store_image, store_video
from app.models import Asset, AssetSource, Generation, GenerationStatus, InputRole
from app.pipelines import Job, JobInput, Pipeline, ratio_of
from app.video import VideoError
from app.worker import queue
from app.worker.renderer import OutputFile, Renderer, RendererFailed, RendererRejected, RendererUnavailable

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
    engine: Engine, claim: queue.Claim, pipelines: dict[str, Pipeline], store: MediaStore, renderer: Renderer
) -> Outcome:
    with Session(engine, expire_on_commit=False) as session:
        generation = session.get_one(Generation, claim.generation_id)
        pipeline = pipelines.get(generation.pipeline_id)
        if pipeline is None:
            return fail(engine, claim, "The pipeline this used is no longer installed")
        attached = [(i.role, i.asset) for i in generation.inputs]
        # Recorded before submitting, so the run can be found in the renderer (to cancel it, say) whatever happens next
        prompt_id = str(uuid.uuid4())
        generation.run_id = prompt_id
        session.commit()

    try:
        renderer.use(pipeline.id)
        inputs = tuple(upload(store, renderer, role, asset) for role, asset in attached)
        graph = pipeline.build(job_for(generation, pipeline, inputs))
        assert graph.output_node is not None, f"{pipeline.id} built a graph that saves nothing"
        progress = ProgressWriter(engine, claim, time_limit_s(generation.estimated_s))
        files = renderer.run(graph.nodes, prompt_id, graph.output_node, progress.update, progress.beat)
        if not files:
            raise RendererFailed("This finished without making anything")
        outputs = [
            store_output(store, renderer, file, f"outputs/{generation.id}/{claim.attempt}-{n}")
            for n, file in enumerate(files)
        ]
    except TooLong:
        logger.warning("Generation %s went past its time limit; stopping it", generation.id)
        try:
            renderer.stop(prompt_id)
        except RendererUnavailable as error:
            logger.warning("Couldn't stop generation %s in the renderer: %s", generation.id, error)
        return fail(engine, claim, "This took much longer than it should, so it was stopped. Try again.")
    except RendererUnavailable as error:
        logger.warning("Renderer unreachable, putting generation %s back in the queue: %s", generation.id, error)
        queue.release(engine, claim)
        return "released"
    except RendererRejected as error:
        logger.error("Renderer refused pipeline %s: %s", pipeline.id, error)
        return fail(engine, claim, "Something is wrong on our side, so this couldn't start")
    except RendererFailed as error:
        logger.info("Generation %s failed in %s: %s", generation.id, error.node_type, error)
        return fail(engine, claim, failure_message(error))
    except Exception:
        logger.exception("Generation %s failed", generation.id)
        return fail(engine, claim, "Something went wrong while making this. Try again.")
    return finish(engine, claim, outputs)


def upload(store: MediaStore, renderer: Renderer, role: InputRole, asset: Asset) -> JobInput:
    data = store.path(asset.storage_key).read_bytes()
    name = renderer.upload(data, f"{asset.id}{PurePath(asset.storage_key).suffix}")
    return JobInput(role, asset.media_type, name, (asset.width, asset.height))


def job_for(generation: Generation, pipeline: Pipeline, inputs: tuple[JobInput, ...]) -> Job:
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
        megapixels=pipeline.megapixels[generation.quality],
        size=pipeline.size(generation.quality, ratio),
        frames=None if duration_s is None else pipeline.frames[round(duration_s)],
        inputs=inputs,
        filename_prefix=f"unnoodle/{generation.id}",
        estimated_s=generation.estimated_s,
    )


def store_output(store: MediaStore, renderer: Renderer, file: OutputFile, key_stem: str) -> Stored:
    data = renderer.download(file)
    try:
        return store_image(store, data, key_stem) or store_video(store, data, key_stem, clip=False)
    except VideoError as error:
        logger.error("Can't store %s: %s", file.filename, error)
        raise RendererFailed("This made a kind of file the app can't show yet") from error


def failure_message(error: RendererFailed) -> str:
    """What the person sees. The renderer's own messages name nodes and tensors, so they go to the log instead."""
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
    once the run has gone past its time limit: the renderer reports progress, or goes quiet, often enough for that to be
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
