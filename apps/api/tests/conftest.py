from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

import app.models  # noqa: F401  (registers the tables on Base.metadata)
from app.db import Base, make_engine
from app.main import create_app
from app.settings import ENV_FILE, Settings

API_DIR = Path(__file__).resolve().parents[1]


class PytestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNNOODLE_TEST_", env_file=ENV_FILE, extra="ignore")

    database_url: str | None = None


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """The test database, created if it doesn't exist yet."""
    url = PytestSettings().database_url
    if url is None:
        pytest.skip("set UNNOODLE_TEST_DATABASE_URL to run against Postgres")
    create_database_if_missing(url)
    return url


@pytest.fixture(scope="session")
def migrated_engine(test_database_url: str) -> Iterator[Engine]:
    """The test database, migrated to the latest revision once per run."""
    engine = make_engine(test_database_url)
    config = Config(API_DIR / "alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def engine(migrated_engine: Engine) -> Iterator[Engine]:
    """The migrated test database, emptied after each test."""
    yield migrated_engine
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with migrated_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture
def settings(engine: Engine, test_database_url: str, tmp_path: Path) -> Settings:
    """Settings for an app on the test database, with its media in a fresh folder."""
    return Settings(database_url=test_database_url, media_dir=tmp_path / "media")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


def create_database_if_missing(url: str) -> None:
    target = make_url(url)
    # CREATE DATABASE can't run inside a transaction, hence autocommit
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        admin.dispose()
