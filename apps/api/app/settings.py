from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

# The repo-root .env, shared with docker compose. A missing file is skipped, so deployed environments use real env vars.
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    # extra="ignore": the shared .env also holds the compose variables, which aren't ours
    model_config = SettingsConfigDict(env_prefix="UNNOODLE_", env_file=ENV_FILE, extra="ignore")

    # Matches the docker compose defaults. 127.0.0.1 rather than localhost: compose publishes the port on IPv4 only,
    # and trying ::1 first costs every new connection its full connect timeout
    database_url: str = "postgresql+psycopg://unnoodle:unnoodle@127.0.0.1:5432/unnoodle"

    # Which catalogue of workflows to offer (app/catalogues): "dev" runs on the dev ComfyUI without models, "real"
    # needs a ComfyUI with the models, such as one on a rented GPU
    workflows: Literal["dev", "real"] = "dev"

    # Uploads and outputs, served under /media
    media_dir: Path = REPO_ROOT / "apps" / "api" / "media"

    # Where the worker runs workflows. 8189 is the dev ComfyUI (see the README); a regular install listens on 8188.
    comfyui_url: str = "http://127.0.0.1:8189"
