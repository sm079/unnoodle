from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    # Which catalogue of pipelines to offer (app/catalogues): "dev" runs on the dev renderer without models, "real"
    # needs a renderer with the models, such as one on a rented GPU
    pipelines: Literal["dev", "real"] = "dev"

    # Marks the sign-in cookie Secure, so browsers send it over HTTPS only. On wherever the app is served over HTTPS;
    # off for plain http on this machine.
    secure_cookies: bool = False

    # Uploads and outputs, served under /media to their owners
    media_dir: Path = REPO_ROOT / "apps" / "api" / "media"

    # Where the worker runs pipelines. 8189 is the dev renderer (see the README); a regular install listens on 8188.
    renderer_url: str = "http://127.0.0.1:8189"

    # Renting a GPU when there is work (app.gpu): "off" leaves the renderer to whoever runs it, "runpod" starts one on
    # RunPod for queued generations and hands it back when it has been idle a while
    gpu: Literal["off", "runpod"] = "off"
    runpod_api_key: SecretStr | None = None
    # For the gated FLUX.2 Klein weights on Hugging Face (its licence accepted with the same account)
    hf_token: SecretStr | None = None
    gpu_type: str = "NVIDIA GeForce RTX 5090"
    gpu_idle_stop_s: int = 300
    # GPU time per day, from launch to stop, after which nothing new starts until the next day begins
    gpu_daily_limit_s: int = 7200
    gpu_day_timezone: str = "Asia/Kathmandu"
    # The SSH key the GPU process makes for itself and gives each pod; nothing else uses it
    gpu_keys_dir: Path = REPO_ROOT / "apps" / "api" / ".gpu"
