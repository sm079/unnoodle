import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.settings import ENV_FILE


class PytestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNNOODLE_TEST_", env_file=ENV_FILE, extra="ignore")

    database_url: str | None = None


@pytest.fixture
def test_database_url() -> str:
    url = PytestSettings().database_url
    if url is None:
        pytest.skip("set UNNOODLE_TEST_DATABASE_URL to run against Postgres")
    return url
