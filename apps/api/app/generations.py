"""Generations: requests to run a workflow, from being queued to their outputs."""

import secrets
import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from app.db import SessionDep
from app.media import AssetOut
from app.models import Asset, Capability, Generation, GenerationInput, GenerationStatus, InputRole, MediaType
from app.routing import RoutingError, route
from app.worker import queue
from app.workflows import AspectRatio, Workflow, WorkflowsDep

# Seeds the app picks stay within 32 bits, which every sampler takes. Ones sent in may go up to the largest
# integer a browser holds exactly.
PICKED_SEEDS = 2**32
MAX_SEED = 2**53 - 1


class InputIn(BaseModel):
    asset_id: uuid.UUID
    role: InputRole
    # Seconds into the clip. Keyframes only.
    position_s: float | None = Field(default=None, ge=0)


class Params(BaseModel):
    aspect_ratio: AspectRatio
    # As offered by the workflow, e.g. "1K" or "720p"
    resolution: str
    # Videos only
    duration_s: float | None = None
    # Outputs per run
    count: int = Field(default=1, ge=1)
    # Left out for a random one; the generation records the seed it used
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)
    # Videos only, where the workflow offers it
    audio: bool = False


class GenerationIn(BaseModel):
    """What the composer sends. It names no workflow: the inputs' roles decide one."""

    media_type: MediaType
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    inputs: list[InputIn] = Field(default=[], max_length=16)
    params: Params
    # Which model runs it, when several can; left out for the default
    model: str | None = None


class GenerationInputOut(BaseModel):
    role: InputRole
    position_s: float | None
    asset: AssetOut


class ParamsOut(Params):
    seed: int


class GenerationOut(BaseModel):
    id: uuid.UUID
    status: GenerationStatus
    capability: Capability
    workflow_id: str
    prompt: str
    params: ParamsOut
    inputs: list[GenerationInputOut]
    # Filled once the status is done
    outputs: list[AssetOut]
    # 0 to 1 while running
    progress: float | None
    # Set when the status is failed
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, g: Generation) -> GenerationOut:
        return cls(
            id=g.id,
            status=g.status,
            capability=g.capability,
            workflow_id=g.workflow_id,
            prompt=g.prompt,
            params=ParamsOut(
                # Checked against the workflow when the request was accepted
                aspect_ratio=cast(AspectRatio, g.aspect_ratio),
                resolution=g.resolution,
                duration_s=g.duration_s,
                count=g.count,
                seed=g.seed,
                audio=g.audio,
            ),
            inputs=[
                GenerationInputOut(role=i.role, position_s=i.position_s, asset=AssetOut.of(i.asset)) for i in g.inputs
            ],
            outputs=[AssetOut.of(asset) for asset in g.outputs],
            progress=g.progress,
            error=g.error,
            created_at=g.created_at,
            started_at=g.started_at,
            finished_at=g.finished_at,
        )


class RequestError(ValueError):
    """A request that doesn't fit its workflow. The message is written for the person who sent it."""


router = APIRouter()


@router.post("/generations", status_code=status.HTTP_201_CREATED, responses={422: {"description": "Can't be run"}})
def create_generation(body: GenerationIn, session: SessionDep, workflows: WorkflowsDep) -> GenerationOut:
    try:
        workflow = route(workflows.values(), body.media_type, [i.role for i in body.inputs], body.model)
        check_params(workflow, body.params)
        assets = attached_assets(session, body.inputs)
    except (RoutingError, RequestError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    p = body.params
    generation = Generation(
        capability=workflow.capability,
        workflow_id=workflow.id,
        prompt=body.prompt,
        aspect_ratio=p.aspect_ratio,
        resolution=p.resolution,
        duration_s=p.duration_s,
        count=p.count,
        seed=p.seed if p.seed is not None else secrets.randbelow(PICKED_SEEDS),
        audio=p.audio,
        inputs=[
            GenerationInput(position=n, role=i.role, asset=assets[i.asset_id], position_s=i.position_s)
            for n, i in enumerate(body.inputs)
        ],
    )
    session.add(generation)
    queue.notify_queued(session)
    session.commit()
    return GenerationOut.of(generation)


@router.get("/generations")
def list_generations(session: SessionDep, before: uuid.UUID | None = None, limit: int = 30) -> list[GenerationOut]:
    """Newest first. For the next page, pass the id of the last one received as before."""
    query = select(Generation).order_by(Generation.id.desc()).limit(min(limit, 100))
    if before is not None:
        # Ids are time-ordered, so "older than" is "smaller id"
        query = query.where(Generation.id < before)
    return [GenerationOut.of(g) for g in session.scalars(query)]


@router.get("/generations/{generation_id}", responses={404: {"description": "No such generation"}})
def get_generation(generation_id: uuid.UUID, session: SessionDep) -> GenerationOut:
    generation = session.get(Generation, generation_id)
    if generation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such generation")
    return GenerationOut.of(generation)


def check_params(workflow: Workflow, params: Params) -> None:
    m = workflow.manifest
    name = m.model_name
    sizes = m.sizes.get(params.resolution)
    if sizes is None:
        raise RequestError(f"{name} offers {', '.join(m.sizes)}, not {params.resolution}")
    if params.aspect_ratio not in sizes:
        raise RequestError(f"{name} at {params.resolution} offers {', '.join(sizes)}, not {params.aspect_ratio}")
    if params.count > m.max_count:
        raise RequestError(f"{name} makes at most {m.max_count} at a time")
    if workflow.capability.media_type is MediaType.VIDEO:
        if params.duration_s not in m.durations_s:
            offered = ", ".join(f"{d:g}s" for d in m.durations_s)
            raise RequestError(f"{name} makes videos of {offered}")
    elif params.duration_s is not None:
        raise RequestError("Only videos have a duration")
    if params.audio and not m.audio:
        raise RequestError(f"{name} doesn't make sound")


def attached_assets(session: SessionDep, inputs: list[InputIn]) -> dict[uuid.UUID, Asset]:
    for i in inputs:
        if (i.position_s is not None) != (i.role is InputRole.KEYFRAME):
            raise RequestError("Keyframes need a time in the clip, and only keyframes have one")
    ids = {i.asset_id for i in inputs}
    assets = {a.id: a for a in session.scalars(select(Asset).where(Asset.id.in_(ids)))} if ids else {}
    for i in inputs:
        asset = assets.get(i.asset_id)
        if asset is None:
            raise RequestError("An attached file no longer exists")
        needed = MediaType.VIDEO if i.role is InputRole.SOURCE_VIDEO else MediaType.IMAGE
        if asset.media_type is not needed:
            raise RequestError(
                f"A {i.role.replace('_', ' ')} has to be {'a video' if needed is MediaType.VIDEO else 'an image'}"
            )
    return assets
