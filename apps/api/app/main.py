from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import accounts, admin, credits, generations, health, media, pipelines, preferences, projects
from app.db import make_engine
from app.settings import Settings


def create_app(settings: Settings | None = None, catalogue: dict[str, pipelines.Pipeline] | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(title="unnoodle API", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    # Loaded once, and checked as they load, so a broken pipeline stops the API from starting. Tests pass their own.
    app.state.pipelines = catalogue if catalogue is not None else pipelines.load_pipelines(settings.pipelines)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.state.media = media.MediaStore(settings.media_dir)

    app.include_router(health.router)
    app.include_router(accounts.router)
    app.include_router(credits.router)
    app.include_router(pipelines.router)
    app.include_router(media.router)
    app.include_router(generations.router)
    app.include_router(projects.router)
    app.include_router(preferences.router)
    app.include_router(admin.router)
    return app


app = create_app()
