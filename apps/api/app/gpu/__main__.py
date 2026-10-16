"""The GPU process: python -m app.gpu

Rents a GPU on RunPod while generations are waiting, and hands it back when it's idle (app.gpu.manager). Runs only
with UNNOODLE_GPU=runpod; one of it at a time.
"""

import logging
import sys
import time

from app.db import make_engine
from app.gpu.manager import Config, Manager
from app.gpu.remote import SSH, ensure_key
from app.gpu.runpod import RunPod
from app.settings import Settings

logger = logging.getLogger("app.gpu")

TICK_S = 5
# Where the worker reaches the renderer through this process's tunnel (UNNOODLE_RENDERER_URL points here)
TUNNEL_PORT = 8288


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = Settings()
    if settings.gpu != "runpod":
        # Not an error: this deployment runs its renderer some other way
        logger.info("UNNOODLE_GPU isn't runpod, so no GPUs are rented")
        return
    if settings.runpod_api_key is None:
        sys.exit("UNNOODLE_RUNPOD_API_KEY is needed to rent GPUs")
    public_key = ensure_key(settings.gpu_keys_dir)
    manager = Manager(
        make_engine(settings.database_url),
        RunPod(settings.runpod_api_key.get_secret_value()),
        SSH(settings.gpu_keys_dir, TUNNEL_PORT),
        Config.of(settings, public_key),
    )
    logger.info(
        "Started: %s, idle stop after %ds, %ds a day",
        ", ".join(settings.gpu_types),
        settings.gpu_idle_stop_s,
        settings.gpu_daily_limit_s,
    )
    while True:
        try:
            manager.tick()
        except Exception:
            # A database or network hiccup; the next tick tries again
            logger.exception("Tick failed")
        time.sleep(TICK_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped")
