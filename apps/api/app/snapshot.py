"""A read-only copy of the demo project for the web app's /demo page, which works without the API.

    uv run python -m app.snapshot ../web

Asks this API, in-process, what a new account would see: the real pipelines, the demo project and its generations,
and a balance of 0 with the prices. The answers are written to src/lib/demo-snapshot.json under the paths the web app
requests them by, and every file they point to is copied under public/demo, made smaller on the way so the copy stays a
few megabytes: pictures as WebP at most 1280 px, videos re-encoded at a lower bitrate. Run it again after the demo
project changes, and commit both.
"""

import argparse
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from PIL import Image

from app.accounts import current_user
from app.main import create_app
from app.models import User
from app.settings import Settings

MEDIA = "/media/"
PUBLIC = "/demo/"
LONG_EDGE = 1280
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.snapshot", description="Copy the demo project for /demo")
    parser.add_argument("web", type=Path, help="the web app's folder (apps/web)")
    args = parser.parse_args(argv)

    settings = Settings(pipelines="real")
    app = create_app(settings)
    # Someone who owns nothing, so the answers are what any new account gets
    visitor = User(id=uuid.uuid4(), email="visitor@example.com", is_admin=False)
    app.dependency_overrides[current_user] = lambda: visitor

    with TestClient(app) as client:

        def get(path: str) -> Any:
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        projects = [p for p in get("/projects") if p["demo"]]
        answers: dict[str, Any] = {
            "/pipelines": get("/pipelines"),
            "/projects": projects,
            "/generations": [],
            "/assets": [],
            "/credits": get("/credits"),
        }
        for project in projects:
            path = f"/generations?{urlencode({'project_id': project['id']})}"
            answers[path] = get(path)

    out = args.web / "public" / PUBLIC.strip("/")
    shutil.rmtree(out, ignore_errors=True)
    copied: dict[str, str] = {}

    def relink(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: relink(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relink(v) for v in value]
        if isinstance(value, str) and value.startswith(MEDIA):
            if value not in copied:
                copied[value] = copy(settings.media_dir / value.removeprefix(MEDIA), out, value.removeprefix(MEDIA))
            return copied[value]
        return value

    snapshot = relink(answers)
    target = args.web / "src" / "lib" / "demo-snapshot.json"
    target.write_bytes((json.dumps(snapshot, indent=2) + "\n").encode())

    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"{len(copied)} files, {size / 1e6:.1f} MB in {out}; answers in {target}")


def copy(source: Path, out: Path, key: str) -> str:
    """Copies one stored file under out, smaller where that's worth it, and returns the URL it's served at."""
    if source.suffix in VIDEO_EXTENSIONS:
        key = str(Path(key).with_suffix(".mp4"))
        target = out / key
        target.parent.mkdir(parents=True, exist_ok=True)
        # Sound stays: the video model makes it, and it's part of what the demo shows
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(source), "-c:v", "libx264", "-preset", "slow", "-crf", "30"]
            + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(target)],
            check=True,
        )
    else:
        key = str(Path(key).with_suffix(".webp"))
        target = out / key
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.thumbnail((LONG_EDGE, LONG_EDGE))
            image.save(target, "WEBP", quality=78, method=6)
    return PUBLIC + key.replace("\\", "/")


if __name__ == "__main__":
    main()
