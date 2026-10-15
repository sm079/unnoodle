from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env, shared with docker compose. A missing file is skipped, so deployed environments use real env vars.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    # extra="ignore": the shared .env also holds the compose variables, which aren't ours
    model_config = SettingsConfigDict(env_prefix="UNNOODLE_", env_file=ENV_FILE, extra="ignore")

    # Matches the docker compose defaults. 127.0.0.1 rather than localhost: compose publishes the port on IPv4 only,
    # and trying ::1 first costs every new connection its full connect timeout
    database_url: str = "postgresql+psycopg://unnoodle:unnoodle@127.0.0.1:5432/unnoodle"
