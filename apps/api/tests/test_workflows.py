import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Capability, InputRole
from app.settings import Settings
from app.workflows import Binding, WorkflowError, default_workflow, load_workflow, load_workflows

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


def test_the_dev_workflows_load() -> None:
    workflows = load_workflows(Settings().workflows_dir)
    image = workflows["dev-image-generate"]
    assert image.capability is Capability.IMAGE_GENERATE
    assert image.bindings["prompt"] == Binding("1", "value")
    assert image.bindings["batch_size"] == Binding("5", "value")
    assert image.output_node == "8"


def test_asset_inputs_are_bound_and_counted(tmp_path: Path) -> None:
    graph = video_graph() | {
        "10": node("LoadImage", "in.reference_1", image="a.png"),
        "11": node("LoadImage", "in.reference_2", image="b.png"),
    }
    manifest = VIDEO_MANIFEST.replace("video.from_frame", "video.reference")
    workflow = load_workflow(write(tmp_path / "refs", graph, manifest))
    assert workflow.bindings["start_frame"] == Binding("9", "image")
    assert workflow.roles == {InputRole.START_FRAME: 1, InputRole.REFERENCE: 2}


def retitle(graph: Graph, node_id: str, title: str) -> Graph:
    graph[node_id]["_meta"]["title"] = title
    return graph


BROKEN: list[tuple[str, Callable[[], Graph], str, str]] = [
    ("no output", lambda: retitle(image_graph(), "6", "Save"), IMAGE_MANIFEST, "no node is titled 'out.media'"),
    (
        "two outputs",
        lambda: image_graph() | {"7": node("SaveImage", "out.media", images=["5", 0])},
        IMAGE_MANIFEST,
        "2 nodes are titled 'out.media'",
    ),
    (
        "unknown input",
        lambda: image_graph() | {"7": node("PrimitiveString", "in.negative", value="")},
        IMAGE_MANIFEST,
        "'in.negative' is not an input the app can fill",
    ),
    (
        "input on a node with no value field",
        lambda: image_graph() | {"1": node("CLIPTextEncode", "in.prompt", text="")},
        IMAGE_MANIFEST,
        "'in.prompt' is a CLIPTextEncode node",
    ),
    (
        "asset input on a primitive",
        lambda: video_graph() | {"9": node("PrimitiveString", "in.start_frame", value="")},
        VIDEO_MANIFEST,
        "'in.start_frame' must be a LoadImage or LoadVideo node",
    ),
    ("missing seed", lambda: retitle(image_graph(), "2", "Seed"), IMAGE_MANIFEST, "no node is titled 'in.seed'"),
    (
        "count without a batch size",
        image_graph,
        with_keys(IMAGE_MANIFEST, "max_count = 4"),
        "no node is titled 'in.batch_size'",
    ),
    (
        "capability without its role",
        lambda: retitle(video_graph(), "9", "Start"),
        VIDEO_MANIFEST,
        "video.from_frame needs a start_frame input",
    ),
    (
        "gap in numbered references",
        lambda: (
            video_graph()
            | {
                "10": node("LoadImage", "in.reference_1", image="a.png"),
                "11": node("LoadImage", "in.reference_3", image="b.png"),
            }
        ),
        VIDEO_MANIFEST,
        "reference inputs must be numbered 1 to 2",
    ),
    (
        "unnumbered reference",
        lambda: image_graph() | {"7": node("LoadImage", "in.reference", image="a.png")},
        IMAGE_MANIFEST,
        "'in.reference' is not an input the app can fill",
    ),
    (
        "video without fps",
        video_graph,
        VIDEO_MANIFEST.replace("fps = 24\n", ""),
        "video workflows need fps and durations_s",
    ),
    (
        "image with durations",
        image_graph,
        with_keys(IMAGE_MANIFEST, "durations_s = [5]"),
        "fps, durations_s and audio are for video workflows",
    ),
    (
        "unknown manifest key",
        image_graph,
        with_keys(IMAGE_MANIFEST, 'lora = "x"'),
        "lora: Extra inputs are not permitted",
    ),
]


@pytest.mark.parametrize(("graph", "manifest", "problem"), [b[1:] for b in BROKEN], ids=[b[0] for b in BROKEN])
def test_a_broken_workflow_is_refused_with_the_reason(
    tmp_path: Path, graph: Callable[[], Graph], manifest: str, problem: str
) -> None:
    with pytest.raises(WorkflowError, match="^broken: .*" + problem.replace("(", r"\(")):
        load_workflow(write(tmp_path / "broken", graph(), manifest))


def test_a_missing_file_is_named(tmp_path: Path) -> None:
    folder = write(tmp_path / "broken", image_graph(), IMAGE_MANIFEST)
    (folder / "workflow.json").unlink()
    with pytest.raises(WorkflowError, match="broken: missing workflow.json"):
        load_workflow(folder)


def second_model(manifest: str, default: bool) -> str:
    renamed = manifest.replace('model = "test"', 'model = "other"')
    return with_keys(renamed, "default = true") if default else renamed


def test_a_capability_with_several_workflows_needs_one_default(tmp_path: Path) -> None:
    write(tmp_path / "a", image_graph(), IMAGE_MANIFEST)
    write(tmp_path / "b", image_graph(), second_model(IMAGE_MANIFEST, default=False))
    with pytest.raises(WorkflowError, match="image.generate has 2 workflows and needs exactly one default"):
        load_workflows(tmp_path)


def test_the_default_is_the_marked_workflow_or_the_only_one(tmp_path: Path) -> None:
    write(tmp_path / "a", image_graph(), IMAGE_MANIFEST)
    write(tmp_path / "b", image_graph(), second_model(IMAGE_MANIFEST, default=True))
    write(tmp_path / "c", video_graph(), VIDEO_MANIFEST)
    workflows = load_workflows(tmp_path).values()
    assert default_workflow(workflows, Capability.IMAGE_GENERATE).id == "b"  # type: ignore[union-attr]
    assert default_workflow(workflows, Capability.VIDEO_FROM_FRAME).id == "c"  # type: ignore[union-attr]
    assert default_workflow(workflows, Capability.VIDEO_GENERATE) is None


def test_the_api_lists_workflows_with_what_the_composer_offers(tmp_path: Path) -> None:
    write(tmp_path / "a", image_graph(), IMAGE_MANIFEST)
    write(tmp_path / "b", image_graph(), second_model(IMAGE_MANIFEST, default=True))
    write(tmp_path / "c", video_graph(), VIDEO_MANIFEST)
    settings = Settings(workflows_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        listed = {w["id"]: w for w in client.get("/workflows").json()}
    assert {id: w["default"] for id, w in listed.items()} == {"a": False, "b": True, "c": True}
    assert listed["c"]["resolutions"] == {"720p": ["16:9"]}
    assert listed["c"]["durations_s"] == [5]
    assert listed["c"]["roles"] == {"start_frame": 1}


def test_the_api_does_not_start_with_a_broken_workflow(tmp_path: Path) -> None:
    write(tmp_path / "broken", retitle(image_graph(), "6", "Save"), IMAGE_MANIFEST)
    with pytest.raises(WorkflowError):
        create_app(Settings(workflows_dir=tmp_path))
