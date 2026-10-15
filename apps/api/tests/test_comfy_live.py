"""The worker's ComfyUI client against a real ComfyUI: the dev one, started as the README describes."""

import uuid
from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from app.settings import Settings
from app.worker.comfy import ComfyClient, ComfyFailed, ComfyRejected, ComfyUnavailable, OutputFile
from app.worker.runner import fill_graph
from app.workflows import load_workflows


def dev_image_graph(prompt: str) -> dict[str, Any]:
    workflow = load_workflows(Settings().workflows_dir)["dev-image-generate"]
    values = {"prompt": prompt, "seed": 11, "width": 256, "height": 192, "batch_size": 2}
    return fill_graph(workflow, values, "unnoodle/test")


def run(client: ComfyClient, graph: dict[str, Any], output_node: str) -> tuple[list[OutputFile], list[float]]:
    progress: list[float] = []
    files = client.run(graph, str(uuid.uuid4()), output_node, progress.append, lambda: None)
    return files, progress


def test_a_graph_runs_reporting_progress_and_its_outputs_download(comfyui_url: str) -> None:
    client = ComfyClient(comfyui_url)
    # A prompt never sent before, so ComfyUI can't answer from its cache without running the steps
    files, progress = run(client, dev_image_graph(f"live test {uuid.uuid4()}"), "8")
    assert progress == sorted(progress) and progress[-1] == 1.0
    assert len(files) == 2
    with Image.open(BytesIO(client.download(files[0]))) as image:
        assert image.size == (256, 192)


def test_a_failure_inside_comfyui_is_reported_with_its_type(comfyui_url: str) -> None:
    with pytest.raises(ComfyFailed) as failure:
        run(ComfyClient(comfyui_url), dev_image_graph(f"too big {uuid.uuid4()} #oom"), "8")
    assert failure.value.node_type == "UnnoodleDevSteps"
    assert "OutOfMemory" in str(failure.value.exception_type)


def test_an_uploaded_image_loads_in_a_graph(comfyui_url: str) -> None:
    client = ComfyClient(comfyui_url)
    buffer = BytesIO()
    Image.new("RGB", (48, 32), (250, 0, 0)).save(buffer, format="PNG")
    stored = client.upload(buffer.getvalue(), f"{uuid.uuid4()}.png")
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": stored}, "_meta": {"title": "in.start_frame"}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "unnoodle/test"}},
    }
    files, _ = run(client, graph, "2")
    with Image.open(BytesIO(client.download(files[0]))) as image:
        assert image.size == (48, 32)


def test_a_graph_comfyui_refuses_says_which_node(comfyui_url: str) -> None:
    graph = dev_image_graph("refused")
    del graph["7"]["inputs"]["seed"]
    with pytest.raises(ComfyRejected, match="node 7 \\(UnnoodleDevSteps\\)"):
        run(ComfyClient(comfyui_url), graph, "8")


def test_an_unreachable_comfyui_is_unavailable_not_failed() -> None:
    # Nothing listens on port 1
    with pytest.raises(ComfyUnavailable):
        run(ComfyClient("http://127.0.0.1:1"), dev_image_graph("nowhere"), "8")
