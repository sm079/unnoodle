from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import generations, health, media, projects, workflows
from app.db import make_engine
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="unnoodle API", lifespan=lifespan)
    app.state.engine = engine
    # Loaded once, and checked as they load, so a broken workflow stops the API from starting
    app.state.workflows = workflows.load_workflows(settings.workflows_dir)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.state.media = media.MediaStore(settings.media_dir)

    app.include_router(health.router)
    app.include_router(workflows.router)
    app.include_router(media.router)
    app.include_router(generations.router)
    app.include_router(projects.router)
    app.mount(media.MEDIA_URL, StaticFiles(directory=settings.media_dir), name="media")
    return app


app = create_app()
