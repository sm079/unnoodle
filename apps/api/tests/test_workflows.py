from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.catalogues import real
from app.main import create_app
from app.models import Capability, InputRole, MediaType, Quality
from app.settings import Settings
from app.workflows import Job, JobInput, WorkflowError, check_catalogue, load_workflows, size_for
from tests.catalogue import IMAGE, VIDEO, catalogue, node_of

PHOTO, CLIP = MediaType.IMAGE, MediaType.VIDEO
EDIT_TARGET, REFERENCE = InputRole.EDIT_TARGET, InputRole.REFERENCE


@pytest.mark.parametrize("name", ["dev", "real"])
def test_the_catalogues_load(name: str) -> None:
    workflows = load_workflows(name)
    capabilities = {c for w in workflows.values() for c in w.capabilities}
    assert {Capability.IMAGE_GENERATE, Capability.IMAGE_EDIT} <= capabilities


def test_an_unknown_catalogue_is_refused() -> None:
    with pytest.raises(WorkflowError, match="no catalogue called 'nope'"):
        load_workflows("nope")


@pytest.mark.parametrize(
    ("megapixels", "aspect_ratio", "multiple", "size"),
    [
        # As ComfyUI's Resolution Selector gives them
        (1.0, "1:1", 8, (1024, 1024)),
        (0.4, "2:3", 8, (528, 792)),
        (1.0, "16:9", 16, (1360, 768)),
        (2.0, "21:9", 16, (2208, 944)),
        (0.4, "9:16", 32, (480, 864)),
    ],
)
def test_sizes_follow_the_resolution_selector(
    megapixels: float, aspect_ratio: str, multiple: int, size: tuple[int, int]
) -> None:
    assert size_for(megapixels, aspect_ratio, multiple) == size


def job(*inputs: tuple[InputRole, MediaType], prompt: str = "a prompt", **fields: Any) -> Job:
    attached = tuple(
        JobInput(role, kind, f"unnoodle/{n}.{'png' if kind is PHOTO else 'mp4'}")
        for n, (role, kind) in enumerate(inputs)
    )
    defaults: dict[str, Any] = {
        "seed": 7,
        "megapixels": 1.0,
        "size": (1024, 1024),
        "count": 1,
        "frames": None,
        "filename_prefix": "unnoodle/test",
    }
    return Job(prompt=prompt, inputs=attached, **(defaults | fields))


def test_mentions_of_attachments_are_reworded_for_the_model() -> None:
    prompt = "the woman in photo 1 wearing the dress from Photo 2, moving like clip 1, not like photo 3 or clip2"
    j = job((EDIT_TARGET, PHOTO), (REFERENCE, CLIP), (REFERENCE, PHOTO), prompt=prompt)
    assert j.prompt_with(photo="<Picture {n}>", clip="<Video {n}>") == (
        "the woman in <Picture 1> wearing the dress from <Picture 2>, moving like <Video 1>, not like photo 3 or clip2"
    )


BROKEN: list[tuple[str, dict[str, Any], str]] = [
    ("model id", {"model": "Krea 2"}, "model 'Krea 2' must be lowercase"),
    (
        "images and videos",
        {"capabilities": frozenset({Capability.IMAGE_GENERATE, Capability.VIDEO_GENERATE})},
        "must all make images or all make videos",
    ),
    ("edit without a photo", {"capabilities": frozenset({Capability.IMAGE_EDIT})}, "image.edit needs it to accept"),
    ("missing quality", {"megapixels": {Quality.LOW: 0.5}}, "megapixels for low, medium and high"),
    ("shape from nothing", {"aspect_ratios": None}, "only a workflow that edits a photo can take its shape"),
    ("image with lengths", {"frames": {5: 124}}, "lengths and sound are for videos"),
]


@pytest.mark.parametrize(("change", "message"), [b[1:] for b in BROKEN], ids=[b[0] for b in BROKEN])
def test_a_broken_workflow_is_refused_with_the_reason(change: dict[str, Any], message: str) -> None:
    with pytest.raises(WorkflowError, match=f"^t2i: .*{message}"):
        check_catalogue([replace(IMAGE, **change)])


def test_a_video_workflow_needs_lengths() -> None:
    with pytest.raises(WorkflowError, match="needs the lengths it offers"):
        check_catalogue([replace(VIDEO, frames={})])


def test_a_capability_with_several_workflows_needs_one_default() -> None:
    other = replace(IMAGE, id="other", model="other")
    with pytest.raises(
        WorkflowError, match=r"image.generate has 2 workflows and needs exactly one default, found \[\]"
    ):
        check_catalogue([IMAGE, other])
    check_catalogue([IMAGE, replace(other, default=True)])


def test_the_api_lists_workflows_with_what_the_composer_offers(settings: Settings) -> None:
    with TestClient(create_app(settings, catalogue())) as client:
        listed = {w["id"]: w for w in client.get("/workflows").json()}
    assert listed["t2i"]["aspect_ratios"] == ["1:1", "3:4"]
    assert listed["edit"]["aspect_ratios"] == []
    assert listed["edit"]["accepts"] == [
        {"role": "edit_target", "media_type": "image", "most": 1},
        {"role": "reference", "media_type": "image", "most": 2},
    ]
    video = listed["video"]
    assert (video["capabilities"], video["default_for"]) == (["video.generate", "video.reference"],) * 2
    assert (video["durations_s"], video["sound"], video["max_count"]) == ([5, 10], True, 1)


# The real builders. Whether ComfyUI accepts their graphs is checked against a real one in test_comfy_live.


def links(graph: dict[str, Any]) -> list[tuple[str, int]]:
    return [
        (value[0], value[1])
        for node in graph.values()
        for value in node["inputs"].values()
        if isinstance(value, list) and len(value) == 2
    ]


def test_krea_makes_the_size_and_count_asked_for() -> None:
    graph = real.krea2(job(size=(896, 1152), count=3)).nodes
    assert node_of(graph, "EmptyLatentImage") == {"width": 896, "height": 1152, "batch_size": 3}
    assert node_of(graph, "KSampler")["seed"] == 7
    assert node_of(graph, "CLIPTextEncode")["text"] == "a prompt"
    assert all(node_id in graph for node_id, _ in links(graph))


@pytest.mark.parametrize("references", [0, 1, 2])
def test_klein_chains_every_photo_onto_the_prompt(references: int) -> None:
    photos = [(EDIT_TARGET, PHOTO)] + [(REFERENCE, PHOTO)] * references
    built = real.klein(job(*photos, prompt="photo 1 wearing the coat in photo 2", size=None, megapixels=2.0))
    graph = built.nodes
    loads = [n for n in graph.values() if n["class_type"] == "LoadImage"]
    assert [n["inputs"]["image"] for n in loads] == [f"unnoodle/{n}.png" for n in range(len(photos))]
    # Each photo goes onto both the prompt and the empty negative
    assert sum(n["class_type"] == "ReferenceLatent" for n in graph.values()) == 2 * len(photos)
    scales = [n["inputs"] for n in graph.values() if n["class_type"] == "ImageScaleToTotalPixels"]
    assert [s["megapixels"] for s in scales] == [2.0] + [1.0] * references
    # The output takes its size from the photo being edited
    size_from = node_of(graph, "GetImageSize")["image"][0]
    assert graph[size_from]["inputs"]["image"][0] == next(k for k, n in graph.items() if n["class_type"] == "LoadImage")
    text = node_of(graph, "CLIPTextEncode")["text"]
    assert text == ("image 1 wearing the coat in image 2" if references else "image 1 wearing the coat in photo 2")
    assert built.output_node is not None and graph[built.output_node]["class_type"] == "SaveImage"
    assert all(node_id in graph for node_id, _ in links(graph))


def test_an_edit_puts_the_photo_to_edit_first_whatever_the_order_attached() -> None:
    j = job((REFERENCE, PHOTO), (EDIT_TARGET, PHOTO), prompt="the hat from photo 1 on the man in photo 2", size=None)
    graph = real.klein(j).nodes
    loads = [n["inputs"]["image"] for n in graph.values() if n["class_type"] == "LoadImage"]
    assert loads == ["unnoodle/1.png", "unnoodle/0.png"]
    assert node_of(graph, "CLIPTextEncode")["text"] == "the hat from image 2 on the man in image 1"


def test_minimax_gives_each_photo_and_clip_its_place_and_tag() -> None:
    attached = [(REFERENCE, CLIP), (REFERENCE, PHOTO), (REFERENCE, PHOTO)]
    prompt = "the man in photo 2 dances like clip 1 next to photo 1"
    graph = real.minimax_h3(job(*attached, prompt=prompt, size=(480, 864), frames=243)).nodes
    node = node_of(graph, "MiniMaxH3ReferenceToVideo")
    assert (node["width"], node["height"], node["length"]) == (480, 864, 243)
    assert node["prompt"] == "the man in <Picture 2> dances like <Video 1> next to <Picture 1>"
    # Photos and clips are numbered separately, in the order they were attached
    loads = {k: n["inputs"] for k, n in graph.items() if n["class_type"] in ("LoadImage", "LoadVideo")}
    image_of = {
        key: graph[link[0]]["inputs"]["image"][0] for key, link in node.items() if key.startswith("ref_images.")
    }
    assert [loads[load]["image"] for _, load in sorted(image_of.items())] == ["unnoodle/1.png", "unnoodle/2.png"]
    clip_of = graph[node["ref_videos.ref_video_0"][0]]["inputs"]["video"][0]
    assert loads[clip_of] == {"file": "unnoodle/0.mp4"}
    # Sound comes with the video
    assert "audio" in node_of(graph, "CreateVideo")
    assert all(node_id in graph for node_id, _ in links(graph))


def test_minimax_from_a_prompt_alone_has_no_references() -> None:
    node = node_of(real.minimax_h3(job(size=(480, 864), frames=124)).nodes, "MiniMaxH3ReferenceToVideo")
    assert not any(key.startswith("ref_") and key != "ref_image_size" for key in node)
