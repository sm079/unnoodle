"""The worker's ComfyUI client and the workflows' graphs against a real ComfyUI: the dev one, started as the README
describes."""

import uuid
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from app.catalogues import dev, real
from app.graph import Graph
from app.media import MediaStore, store_video
from app.models import InputRole, MediaType
from app.worker.comfy import ComfyClient, ComfyFailed, ComfyRejected, ComfyUnavailable, OutputFile
from app.workflows import Job, JobInput
from tests.clips import clip, needs_ffmpeg

# The inputs of loader nodes that name a model file, which the dev ComfyUI doesn't have
MODEL_FILES = {"unet_name", "clip_name", "vae_name", "lora_name"}


def job(prompt: str, *photos: str, size: tuple[int, int] = (256, 192)) -> Job:
    return Job(
        prompt=prompt,
        seed=11,
        megapixels=0.05,
        size=size,
        frames=None,
        inputs=tuple(JobInput(InputRole.REFERENCE, MediaType.IMAGE, photo) for photo in photos),
        filename_prefix="unnoodle/test",
    )


def run(client: ComfyClient, graph: Graph) -> tuple[list[OutputFile], list[float]]:
    assert graph.output_node is not None
    progress: list[float] = []
    files = client.run(graph.nodes, str(uuid.uuid4()), graph.output_node, progress.append, lambda: None)
    return files, progress


def upload_png(client: ComfyClient, size: tuple[int, int], colour: tuple[int, int, int]) -> str:
    buffer = BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return client.upload(buffer.getvalue(), f"{uuid.uuid4()}.png")


def test_a_graph_runs_reporting_progress_and_its_outputs_download(comfyui_url: str) -> None:
    client = ComfyClient(comfyui_url)
    # A prompt never sent before, so ComfyUI can't answer from its cache without running the steps
    files, progress = run(client, dev.image(job(f"live test {uuid.uuid4()}")))
    assert progress == sorted(progress) and progress[-1] == 1.0
    assert len(files) == 1
    with Image.open(BytesIO(client.download(files[0]))) as image:
        assert image.size == (256, 192)


def test_uploaded_photos_load_into_an_edit(comfyui_url: str) -> None:
    client = ComfyClient(comfyui_url)
    photo = upload_png(client, (480, 320), (250, 0, 0))
    reference = upload_png(client, (64, 64), (0, 0, 250))
    files, _ = run(client, dev.edit(job(f"edit {uuid.uuid4()}", photo, reference, size=(288, 192))))
    with Image.open(BytesIO(client.download(files[0]))) as image:
        assert image.size == (288, 192)


def test_a_failure_inside_comfyui_is_reported_with_its_type(comfyui_url: str) -> None:
    with pytest.raises(ComfyFailed) as failure:
        run(ComfyClient(comfyui_url), dev.image(job(f"too big {uuid.uuid4()} #oom")))
    assert failure.value.node_type == "UnnoodleDevSteps"
    assert "OutOfMemory" in str(failure.value.exception_type)


def test_a_run_can_be_stopped_while_it_sets_up(comfyui_url: str) -> None:
    client = ComfyClient(comfyui_url, quiet_after_s=0.5)
    graph = dev.image(replace(job(f"slow {uuid.uuid4()}"), estimated_s=600))
    assert graph.output_node is not None
    prompt_id = str(uuid.uuid4())
    # Set-up reports nothing, so the client goes quiet; the first time it does, stop the run
    with pytest.raises(ComfyFailed, match="stopped before it finished"):
        client.run(graph.nodes, prompt_id, graph.output_node, lambda _: None, lambda: client.stop(prompt_id))


def test_a_graph_comfyui_refuses_says_which_node(comfyui_url: str) -> None:
    graph = dev.image(job("refused"))
    [node_id] = [k for k, n in graph.nodes.items() if n["class_type"] == "UnnoodleDevSteps"]
    del graph.nodes[node_id]["inputs"]["seed"]
    with pytest.raises(ComfyRejected, match=f"node {node_id} \\(UnnoodleDevSteps\\)"):
        run(ComfyClient(comfyui_url), graph)


def test_an_unreachable_comfyui_is_unavailable_not_failed() -> None:
    # Nothing listens on port 1
    with pytest.raises(ComfyUnavailable):
        run(ComfyClient("http://127.0.0.1:1"), dev.image(job("nowhere")))


def complaints(comfyui_url: str, graph: Graph) -> list[dict[str, Any]]:
    """What ComfyUI says is wrong with a graph, without running it: every model is missing, so it never runs."""
    response = httpx.post(f"{comfyui_url}/prompt", json={"prompt": graph.nodes}, timeout=30)
    assert response.status_code == 400, "the dev ComfyUI ran a real workflow: does it have the models?"
    body = response.json()
    return [
        error | {"class_type": node["class_type"]}
        for node in body.get("node_errors", {}).values()
        for error in node["errors"]
    ]


@pytest.mark.parametrize("references", [0, 2])
def test_the_real_graphs_are_valid_apart_from_the_models(comfyui_url: str, references: int) -> None:
    client = ComfyClient(comfyui_url)
    photos = [upload_png(client, (64, 48), (0, 120, 0)) for _ in range(references + 1)]
    for graph in (real.krea2(job("a fox")), real.klein(job("@photo1 in the coat from @photo2", *photos))):
        found = complaints(comfyui_url, graph)
        assert found, "expected the model files to be missing"
        for error in found:
            assert (error["type"], error["extra_info"]["input_name"] in MODEL_FILES) == ("value_not_in_list", True), (
                error
            )


def video_job(prompt: str, photos: list[str], clips: list[str], frames: int) -> Job:
    attached = [JobInput(InputRole.REFERENCE, MediaType.IMAGE, p) for p in photos]
    # Sized like a video made at high quality, so the graph scales them down too
    attached += [JobInput(InputRole.REFERENCE, MediaType.VIDEO, c, (1280, 720)) for c in clips]
    return replace(job(prompt, size=(256, 448)), frames=frames, inputs=tuple(attached))


@needs_ffmpeg
def test_a_video_from_a_photo_and_a_clip_runs_and_is_stored(comfyui_url: str, tmp_path: Path) -> None:
    client = ComfyClient(comfyui_url)
    photo = upload_png(client, (64, 48), (0, 120, 0))
    reference = client.upload(clip(2), f"{uuid.uuid4()}.mp4")
    files, _ = run(client, dev.video(video_job(f"video {uuid.uuid4()}", [photo], [reference], frames=8)))
    [file] = files
    stored = store_video(MediaStore(tmp_path), client.download(file), "out", clip=False)
    # Eight frames at the stand-in's four a second
    assert (stored.media_type, stored.width, stored.height) == (MediaType.VIDEO, 256, 448)
    assert stored.duration_s == pytest.approx(2, abs=0.3)
    assert stored.poster_key is not None and (tmp_path / stored.poster_key).stat().st_size > 0


@needs_ffmpeg
@pytest.mark.parametrize(("photos", "clips"), [(0, 0), (2, 1)])
def test_the_real_video_graph_is_valid_apart_from_the_models(comfyui_url: str, photos: int, clips: int) -> None:
    client = ComfyClient(comfyui_url)
    photo_names = [upload_png(client, (64, 48), (0, 120, 0)) for _ in range(photos)]
    clip_names = [client.upload(clip(2), f"{uuid.uuid4()}.mp4") for _ in range(clips)]
    graph = real.minimax_h3(video_job("@photo1 waves like @clip1", photo_names, clip_names, frames=124))
    found = complaints(comfyui_url, graph)
    assert found, "expected the model files to be missing"
    for error in found:
        assert (error["type"], error["extra_info"]["input_name"] in MODEL_FILES) == ("value_not_in_list", True), error
