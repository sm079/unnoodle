"""Small workflow folders for tests: just the bound nodes a capability needs, with no model behind them."""

import json
from pathlib import Path
from typing import Any

Graph = dict[str, Any]

IMAGE_MANIFEST = """
capability = "image.generate"
model = "test"
model_name = "Test"
description = "A test workflow"

[sizes.1K]
"1:1" = [1024, 1024]
"""

VIDEO_MANIFEST = """
capability = "video.from_frame"
model = "test"
model_name = "Test"
description = "A test workflow"
fps = 24
durations_s = [5]

[sizes.720p]
"16:9" = [1280, 720]
"""


def with_keys(manifest: str, keys: str) -> str:
    """Adds top-level keys to a manifest. In TOML they have to come before the first [table]."""
    return manifest.replace("\n[", f"{keys}\n\n[", 1)


def node(class_type: str, title: str, **inputs: Any) -> dict[str, Any]:
    return {"class_type": class_type, "inputs": inputs, "_meta": {"title": title}}


def image_graph() -> Graph:
    return {
        "1": node("PrimitiveStringMultiline", "in.prompt", value=""),
        "2": node("PrimitiveInt", "in.seed", value=0),
        "3": node("PrimitiveInt", "in.width", value=1024),
        "4": node("PrimitiveInt", "in.height", value=1024),
        "5": node("EmptyImage", "Canvas", width=["3", 0], height=["4", 0], batch_size=1, color=0),
        "6": node("SaveImage", "out.media", images=["5", 0], filename_prefix="test"),
    }


def video_graph() -> Graph:
    return image_graph() | {
        "7": node("PrimitiveInt", "in.frames", value=121),
        "8": node("PrimitiveInt", "in.fps", value=24),
        "9": node("LoadImage", "in.start_frame", image="start.png"),
    }


def write(folder: Path, graph: Graph, manifest: str) -> Path:
    folder.mkdir(parents=True)
    (folder / "workflow.json").write_text(json.dumps(graph), encoding="utf-8")
    (folder / "manifest.toml").write_text(manifest, encoding="utf-8")
    return folder
