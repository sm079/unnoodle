"""Projects: folders people make for their generations. My generations, the default folder, holds every generation and
isn't stored; a generation made in a project is in both."""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts import CurrentUser
from app.db import SessionDep
from app.media import AssetOut
from app.models import Asset, Generation, Project

# Outputs shown on a project's card
COVERS = 3


class ProjectIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    generation_count: int
    # Its newest outputs, newest first
    covers: list[AssetOut]


router = APIRouter()


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectIn, user: CurrentUser, session: SessionDep) -> ProjectOut:
    project = Project(owner_id=user.id, name=body.name)
    session.add(project)
    session.commit()
    return ProjectOut(id=project.id, name=project.name, created_at=project.created_at, generation_count=0, covers=[])


@router.get("/projects")
def list_projects(user: CurrentUser, session: SessionDep) -> list[ProjectOut]:
    """Your projects, newest first."""
    query = select(Project).where(Project.owner_id == user.id).order_by(Project.id.desc())
    return describe(session, session.scalars(query).all())


@router.get("/projects/{project_id}", responses={404: {"description": "No such project"}})
def get_project(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectOut:
    project = session.get(Project, project_id)
    # Someone else's is as missing as one that never existed
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project")
    return describe(session, [project])[0]


def describe(session: Session, projects: Sequence[Project]) -> list[ProjectOut]:
    """The projects with their counts and covers, in two queries however many there are."""
    ids = [p.id for p in projects]
    if not ids:
        return []
    counts = dict(
        session.execute(
            select(Generation.project_id, func.count())
            .where(Generation.project_id.in_(ids))
            .group_by(Generation.project_id)
        ).all()
    )
    # Numbers each project's outputs from the newest, and keeps the first few of each
    rank = func.row_number().over(partition_by=Generation.project_id, order_by=Asset.id.desc())
    ranked = (
        select(Asset.id, Generation.project_id, rank.label("rank"))
        .join(Generation, Asset.generation_id == Generation.id)
        .where(Generation.project_id.in_(ids))
        .subquery()
    )
    covers: defaultdict[uuid.UUID, list[AssetOut]] = defaultdict(list)
    for asset, project_id in session.execute(
        select(Asset, ranked.c.project_id)
        .join(ranked, Asset.id == ranked.c.id)
        .where(ranked.c.rank <= COVERS)
        .order_by(Asset.id.desc())
    ):
        covers[project_id].append(AssetOut.of(asset))
    return [
        ProjectOut(
            id=p.id,
            name=p.name,
            created_at=p.created_at,
            generation_count=counts.get(p.id, 0),
            covers=covers[p.id],
        )
        for p in projects
    ]
