"""Running one claimed generation: fill its workflow in, run it on ComfyUI, store what it made."""

import copy
import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from typing import Any, Literal, cast

from PIL import Image, UnidentifiedImageError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.media import IMAGE_FORMATS, MediaStore
from app.models import Asset, AssetSource, Generation, GenerationStatus, InputRole, MediaType
from app.worker import queue
from app.worker.comfy import Comfy, ComfyFailed, ComfyRejected, ComfyUnavailable, OutputFile
from app.workflows import NUMBERED_ROLES, AspectRatio, Workflow

logger = logging.getLogger(__name__)

PROGRESS_EVERY_S = 0.5

Outcome = Literal["done", "failed", "released", "lost"]


class UnfilledInputs(Exception):
    """The workflow has input nodes the request gave nothing for."""


@dataclass(frozen=True)
class Output:
    key: str
    media_type: MediaType
    mime_type: str
    size_bytes: int
    width: int
    height: int


def run_job(
    engine: Engine, claim: queue.Claim, workflows: dict[str, Workflow], store: MediaStore, comfy: Comfy
) -> Outcome:
    with Session(engine, expire_on_commit=False) as session:
        generation = session.get_one(Generation, claim.generation_id)
        workflow = workflows.get(generation.workflow_id)
        if workflow is None:
            return fail(engine, claim, "The workflow this used is no longer installed")
        values = parameter_values(generation, workflow)
        inputs = {name: asset for name, asset in input_names(generation)}
        # Recorded before submitting, so the run can be found in ComfyUI (to cancel it, say) whatever happens next
        prompt_id = str(uuid.uuid4())
        generation.comfy_prompt_id = prompt_id
        session.commit()

    try:
        for name, asset in inputs.items():
            data = store.path(asset.storage_key).read_bytes()
            values[name] = comfy.upload(data, f"{asset.id}{PurePath(asset.storage_key).suffix}")
        graph = fill_graph(workflow, values, f"unnoodle/{generation.id}")
        progress = ProgressWriter(engine, claim)
        files = comfy.run(graph, prompt_id, workflow.output_node, progress.update, progress.beat)
        if not files:
            raise ComfyFailed("The workflow finished without saving anything")
        outputs = [
            store_output(store, comfy, file, f"outputs/{generation.id}/{claim.attempt}-{n}")
            for n, file in enumerate(files)
        ]
    except ComfyUnavailable as error:
        logger.warning("ComfyUI unreachable, putting generation %s back in the queue: %s", generation.id, error)
        queue.release(engine, claim)
        return "released"
    except ComfyRejected as error:
        logger.error("ComfyUI refused workflow %s: %s", workflow.id, error)
        return fail(engine, claim, "This workflow is broken: ComfyUI refused it")
    except UnfilledInputs as error:
        return fail(engine, claim, str(error))
    except ComfyFailed as error:
        logger.info("Generation %s failed in %s: %s", generation.id, error.node_type, error)
        return fail(engine, claim, failure_message(error))
    except Exception:
        logger.exception("Generation %s failed", generation.id)
        return fail(engine, claim, "Something went wrong while running this")
    return finish(engine, claim, outputs)


def parameter_values(generation: Generation, workflow: Workflow) -> dict[str, Any]:
    width, height = workflow.manifest.sizes[generation.resolution][cast(AspectRatio, generation.aspect_ratio)]
    values: dict[str, Any] = {
        "prompt": generation.prompt,
        "seed": generation.seed,
        "width": width,
        "height": height,
        "batch_size": generation.count,
    }
    fps = workflow.manifest.fps
    if fps is not None and generation.duration_s is not None:
        values |= {"fps": fps, "frames": round(generation.duration_s * fps), "audio": generation.audio}
    return values


def input_names(generation: Generation) -> list[tuple[str, Asset]]:
    """The node each attached asset goes to: in.start_frame, or in.reference_1, in.reference_2 for numbered roles."""
    numbers: Counter[InputRole] = Counter()
    names = []
    for i in generation.inputs:
        if i.role in NUMBERED_ROLES:
            numbers[i.role] += 1
            names.append((f"{i.role}_{numbers[i.role]}", i.asset))
        else:
            names.append((str(i.role), i.asset))
    return names


def fill_graph(workflow: Workflow, values: dict[str, Any], filename_prefix: str) -> dict[str, Any]:
    missing = [f"in.{name}" for name in workflow.bindings if name not in values]
    if missing:
        raise UnfilledInputs(f"{workflow.manifest.model_name} needs {', '.join(missing)} filled in as well")
    graph = copy.deepcopy(workflow.graph)
    for name, binding in workflow.bindings.items():
        graph[binding.node_id]["inputs"][binding.field] = values[name]
    saver = graph[workflow.output_node]["inputs"]
    if "filename_prefix" in saver:
        # Groups each generation's files in ComfyUI's output folder
        saver["filename_prefix"] = filename_prefix
    return graph


def store_output(store: MediaStore, comfy: Comfy, file: OutputFile, key_stem: str) -> Output:
    data = comfy.download(file)
    try:
        with Image.open(BytesIO(data)) as image:
            image_format, (width, height) = image.format, image.size
    except UnidentifiedImageError:
        image_format = None
    if image_format not in IMAGE_FORMATS:
        raise ComfyFailed(f"The workflow saved {file.filename}, which the app can't store yet")
    mime_type, extension = IMAGE_FORMATS[image_format]
    key = f"{key_stem}.{extension}"
    store.write(key, data)
    return Output(key, MediaType.IMAGE, mime_type, len(data), width, height)


def failure_message(error: ComfyFailed) -> str:
    if error.exception_type and "OutOfMemory" in error.exception_type:
        return "The GPU ran out of memory. Try a smaller size or fewer outputs."
    first_line = str(error).splitlines()[0] if str(error) else "no reason given"
    return f"{error.node_type} failed: {first_line}" if error.node_type else first_line


class ProgressWriter:
    """Writes progress to the database at most every PROGRESS_EVERY_S, renewing the lease each time."""

    def __init__(self, engine: Engine, claim: queue.Claim) -> None:
        self.engine, self.claim = engine, claim
        self.written_at = 0.0

    def update(self, fraction: float) -> None:
        if fraction >= 1 or time.monotonic() - self.written_at >= PROGRESS_EVERY_S:
            queue.beat(self.engine, self.claim, fraction)
            self.written_at = time.monotonic()

    def beat(self) -> None:
        queue.beat(self.engine, self.claim)


def finish(engine: Engine, claim: queue.Claim, outputs: list[Output]) -> Outcome:
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
                    media_type=output.media_type,
                    source=AssetSource.GENERATION,
                    storage_key=output.key,
                    mime_type=output.mime_type,
                    size_bytes=output.size_bytes,
                    width=output.width,
                    height=output.height,
                    generation_id=generation.id,
                )
            )
        queue.end(generation, GenerationStatus.DONE)
    return "done"


def fail(engine: Engine, claim: queue.Claim, message: str) -> Outcome:
    with Session(engine) as session, session.begin():
        generation = queue.lock_held(session, claim)
        if generation is None:
            return "lost"
        queue.end(generation, GenerationStatus.FAILED, message)
    return "failed"
