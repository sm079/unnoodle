from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, shared with docker compose. A missing file is skipped, so deployed environments use real env vars.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    # extra="ignore": the shared .env also holds the compose variables, which aren't ours
    model_config = SettingsConfigDict(env_prefix="UNNOODLE_", env_file=ENV_FILE, extra="ignore")

    # Matches the docker compose defaults
    database_url: str = "postgresql+psycopg://unnoodle:unnoodle@localhost:5432/unnoodle"
