"""What someone can see: their own things, plus demo projects, which everyone sees.

A demo project shows what the real models make to people who haven't made anything yet. Everyone can open it, see
its generations and their files, and use those files as inputs; only its owner can file generations into it.
"""

from sqlalchemy import ColumnElement, or_, select

from app.models import Asset, Generation, GenerationInput, Project, User

demo_projects = select(Project.id).where(Project.is_demo)
demo_generations = select(Generation.id).where(Generation.project_id.in_(demo_projects))


def visible_project(user: User) -> ColumnElement[bool]:
    return or_(Project.owner_id == user.id, Project.is_demo)


def visible_generation(user: User) -> ColumnElement[bool]:
    return or_(Generation.owner_id == user.id, Generation.project_id.in_(demo_projects))


def visible_asset(user: User) -> ColumnElement[bool]:
    """Your own, and the outputs and inputs of demo generations."""
    return or_(
        Asset.owner_id == user.id,
        Asset.generation_id.in_(demo_generations),
        Asset.id.in_(select(GenerationInput.asset_id).where(GenerationInput.generation_id.in_(demo_generations))),
    )
