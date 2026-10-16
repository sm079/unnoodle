"""Generations: requests to run a workflow, from being queued to their outputs."""

import secrets
import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from app.accounts import CurrentUser
from app.db import SessionDep
from app.media import AssetOut
from app.models import (
    Asset,
    Capability,
    Generation,
    GenerationInput,
    GenerationStatus,
    InputRole,
    MediaType,
    Project,
    Quality,
    User,
)
from app.routing import RoutingError, capability_for, route
from app.worker import queue
from app.workflows import AspectRatio, Work, Workflow, WorkflowsDep, ratio_of

# Seeds the app picks stay within 32 bits, which every sampler takes. Ones sent in may go up to the largest
# integer a browser holds exactly.
PICKED_SEEDS = 2**32
MAX_SEED = 2**53 - 1

# How many one request can queue. Each is its own run with one output, so a GPU only ever makes one thing at a time.
MAX_QUEUED = 4


class InputIn(BaseModel):
    asset_id: uuid.UUID
    role: InputRole


class Settings(BaseModel):
    quality: Quality = Quality.MEDIUM
    # One the workflow offers, or left out for the shape of the first attachment
    aspect_ratio: AspectRatio | None = None
    # Videos only, in seconds, one the workflow offers
    duration_s: int | None = None


class Params(Settings):
    # How many to make. Each is a generation of its own, queued one after another, with the next seed.
    count: int = Field(default=1, ge=1)
    # Left out for random ones; each generation records the seed it used
    seed: int | None = Field(default=None, ge=0, le=MAX_SEED)


class GenerationIn(BaseModel):
    """What the composer sends. It names no workflow: the inputs' roles decide one."""

    media_type: MediaType
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    inputs: list[InputIn] = Field(default=[], max_length=16)
    params: Params
    # Which model runs it, when several can; left out for the default
    model: str | None = None
    # The project to file it in; left out, it is only in My generations
    project_id: uuid.UUID | None = None


class GenerationInputOut(BaseModel):
    role: InputRole
    asset: AssetOut


class ParamsOut(Settings):
    seed: int


class GenerationOut(BaseModel):
    id: uuid.UUID
    status: GenerationStatus
    capability: Capability
    workflow_id: str
    prompt: str
    project_id: uuid.UUID | None
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
            project_id=g.project_id,
            params=ParamsOut(
                quality=g.quality,
                # Checked against the workflow when the request was accepted
                aspect_ratio=cast(AspectRatio | None, g.aspect_ratio),
                duration_s=None if g.duration_s is None else round(g.duration_s),
                seed=g.seed,
            ),
            inputs=[GenerationInputOut(role=i.role, asset=AssetOut.of(i.asset)) for i in g.inputs],
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
def create_generation(
    body: GenerationIn, user: CurrentUser, session: SessionDep, workflows: WorkflowsDep
) -> list[GenerationOut]:
    """Queues count generations, oldest first in the answer."""
    try:
        assets = attached_assets(session, user, body.inputs)
        attached = [(i.role, assets[i.asset_id].media_type) for i in body.inputs]
        workflow = route(workflows.values(), body.media_type, attached, body.model)
        check_params(workflow, body.params, attached=len(body.inputs))
        if body.project_id is not None:
            project = session.get(Project, body.project_id)
            if project is None or project.owner_id != user.id:
                raise RequestError("That project no longer exists")
    except (RoutingError, RequestError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    p = body.params
    estimated_s = estimate(workflow, p, [assets[i.asset_id] for i in body.inputs])
    seeds = [p.seed + n if p.seed is not None else secrets.randbelow(PICKED_SEEDS) for n in range(p.count)]
    generations = [
        Generation(
            owner_id=user.id,
            capability=capability_for(body.media_type, attached),
            workflow_id=workflow.id,
            prompt=body.prompt,
            project_id=body.project_id,
            quality=p.quality,
            aspect_ratio=p.aspect_ratio,
            duration_s=p.duration_s,
            seed=seed,
            estimated_s=estimated_s,
            inputs=[
                GenerationInput(position=n, role=i.role, asset=assets[i.asset_id]) for n, i in enumerate(body.inputs)
            ],
        )
        for seed in seeds
    ]
    session.add_all(generations)
    queue.notify_queued(session)
    session.commit()
    return [GenerationOut.of(g) for g in generations]


@router.get("/generations")
def list_generations(
    user: CurrentUser,
    session: SessionDep,
    before: uuid.UUID | None = None,
    limit: int = 30,
    project_id: uuid.UUID | None = None,
) -> list[GenerationOut]:
    """Your generations, newest first: all of them (My generations), or one project's. For the next page, pass the id
    of the last one received as before."""
    query = (
        select(Generation).where(Generation.owner_id == user.id).order_by(Generation.id.desc()).limit(min(limit, 100))
    )
    if before is not None:
        # Ids are time-ordered, so "older than" is "smaller id"
        query = query.where(Generation.id < before)
    if project_id is not None:
        query = query.where(Generation.project_id == project_id)
    return [GenerationOut.of(g) for g in session.scalars(query)]


@router.get("/generations/{generation_id}", responses={404: {"description": "No such generation"}})
def get_generation(generation_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> GenerationOut:
    generation = session.get(Generation, generation_id)
    if generation is None or generation.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such generation")
    return GenerationOut.of(generation)


def check_params(workflow: Workflow, params: Params, attached: int) -> None:
    if params.aspect_ratio is None and not attached:
        raise RequestError("Pick a shape")
    if params.aspect_ratio is not None and params.aspect_ratio not in workflow.aspect_ratios:
        raise RequestError("That shape isn't offered here")
    if params.count > MAX_QUEUED:
        raise RequestError(f"You can make up to {MAX_QUEUED} at a time")
    if workflow.media_type is MediaType.VIDEO:
        if params.duration_s not in workflow.frames:
            lengths = [str(s) for s in sorted(workflow.frames)]
            offered = lengths[0] if len(lengths) == 1 else f"{', '.join(lengths[:-1])} or {lengths[-1]}"
            raise RequestError(f"Videos can be {offered} seconds long")
    elif params.duration_s is not None:
        raise RequestError("Only videos have a length")


def estimate(workflow: Workflow, params: Params, attached: list[Asset]) -> float:
    # The same size the worker will work out, from the shape asked for or the first attachment's
    if params.aspect_ratio is not None:
        ratio = ratio_of(params.aspect_ratio)
    else:
        ratio = (attached[0].width, attached[0].height)
    work = Work(
        size=workflow.size(params.quality, ratio),
        frames=None if params.duration_s is None else workflow.frames[params.duration_s],
        photos=sum(a.media_type is MediaType.IMAGE for a in attached),
        # Only clips have a duration
        clips=tuple((a.width, a.height, a.duration_s) for a in attached if a.duration_s is not None),
    )
    return workflow.estimate(work)


def attached_assets(session: SessionDep, user: User, inputs: list[InputIn]) -> dict[uuid.UUID, Asset]:
    """The attached assets by id. Someone else's count as missing, so their ids can't be used to borrow them."""
    ids = {i.asset_id for i in inputs}
    query = select(Asset).where(Asset.owner_id == user.id, Asset.id.in_(ids))
    assets = {a.id: a for a in session.scalars(query)} if ids else {}
    if ids - assets.keys():
        raise RequestError("An attached file no longer exists")
    return assets
