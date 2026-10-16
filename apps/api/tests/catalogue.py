"""A small catalogue for tests: one pipeline per kind of route, with graphs that only carry what the job says."""

from typing import Any

from app.graph import Graph
from app.models import Capability, InputRole, MediaType, Quality
from app.pipelines import Accepts, Job, Pipeline, check_catalogue

MEGAPIXELS = {Quality.LOW: 0.5, Quality.MEDIUM: 1.0, Quality.HIGH: 2.0}


def build(job: Job) -> Graph:
    """A graph that loads every input and saves a canvas the size of the job, so tests can read the job back."""
    g = Graph()
    for i in job.inputs:
        if i.media_type is MediaType.IMAGE:
            g.add("LoadImage", image=i.file)
        else:
            g.add("LoadVideo", file=i.file)
    width, height = job.size or (0, 0)
    canvas = g.add("EmptyImage", width=width, height=height, batch_size=1, color=0)
    g.add("Job", prompt=job.prompt_with(photo="image {n}", clip="<Video {n}>"), seed=job.seed, frames=job.frames)
    g.output(g.add("SaveImage", images=canvas[0], filename_prefix=job.filename_prefix))
    return g


def pipeline(id: str, *capabilities: Capability, **fields: Any) -> Pipeline:
    defaults: dict[str, Any] = {
        "model": "test",
        "model_name": "Test",
        "description": "A test pipeline",
        "build": build,
        "megapixels": MEGAPIXELS,
    }
    return Pipeline(id=id, capabilities=frozenset(capabilities), **(defaults | fields))


IMAGE = pipeline("t2i", Capability.IMAGE_GENERATE, aspect_ratios=("1:1", "3:4"))
EDIT = pipeline(
    "edit",
    Capability.IMAGE_EDIT,
    accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 3),),
)
VIDEO = pipeline(
    "video",
    Capability.VIDEO_GENERATE,
    Capability.VIDEO_REFERENCE,
    multiple=32,
    accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 2), Accepts(InputRole.REFERENCE, MediaType.VIDEO, 1)),
    frames={5: 124, 10: 243},
    sound=True,
)


def catalogue() -> dict[str, Pipeline]:
    pipelines = [IMAGE, EDIT, VIDEO]
    check_catalogue(pipelines)
    return {w.id: w for w in pipelines}


def node_of(graph: dict[str, Any], class_type: str) -> dict[str, Any]:
    """The inputs of the only node of a type."""
    matches: list[dict[str, Any]] = [n["inputs"] for n in graph.values() if n["class_type"] == class_type]
    [inputs] = matches
    return inputs
