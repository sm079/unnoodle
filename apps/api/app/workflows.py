"""Workflows: what each one does, what it takes and offers, and the code that builds its ComfyUI graph.

A workflow builds its graph for every request (see app.graph), so one workflow covers every combination of inputs it
takes: an edit with one photo or with three, a video from a prompt alone or from reference photos and clips. The
sampler settings stay inside the builder; requests only choose a quality, a shape, a length and how many.

Workflows come in catalogues, chosen by name in the settings: "dev" runs on the dev ComfyUI without any models, "real"
needs the models (on a rented GPU, say). Each catalogue is a module in app.catalogues with a WORKFLOWS list. They are
checked as they load, so a mistake in one stops the API from starting rather than failing a request later.
"""

import importlib
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Literal, get_args

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.graph import Graph
from app.models import Capability, InputRole, MediaType, Quality

# The shapes ComfyUI's Resolution Selector offers, as width:height
AspectRatio = Literal["1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"]
ASPECT_RATIOS: tuple[AspectRatio, ...] = get_args(AspectRatio)

# The roles a capability can't do without
REQUIRED_ROLES: dict[Capability, set[InputRole]] = {
    Capability.IMAGE_GENERATE: set(),
    Capability.IMAGE_EDIT: {InputRole.REFERENCE},
    Capability.VIDEO_GENERATE: set(),
    Capability.VIDEO_REFERENCE: {InputRole.REFERENCE},
}

# How people mention an attachment in a prompt: "the dress from @photo2", "moving like @clip1"
MENTION = re.compile(r"@([a-z0-9_]+)", re.IGNORECASE)


class WorkflowError(Exception):
    """A workflow that can't be used. The message names it and every problem found."""


@dataclass(frozen=True)
class Accepts:
    """How many assets of one kind a workflow takes, e.g. up to 2 reference photos."""

    role: InputRole
    media_type: MediaType
    most: int


@dataclass(frozen=True)
class JobInput:
    role: InputRole
    media_type: MediaType
    # Its name in ComfyUI's input folder, as LoadImage and LoadVideo take it
    file: str


@dataclass(frozen=True)
class Job:
    """One request, as a workflow's builder sees it."""

    prompt: str
    seed: int
    # The output's area in megapixels, from the quality
    megapixels: float
    # (width, height) in pixels: the shape asked for, or the first attachment's, at the quality's area
    size: tuple[int, int]
    # Videos only
    frames: int | None
    # In the order they were attached, which is how the prompt numbers them
    inputs: tuple[JobInput, ...]
    # Groups each generation's files in ComfyUI's output folder
    filename_prefix: str

    def files(self, media_type: MediaType, role: InputRole | None = None) -> list[str]:
        return [i.file for i in self.inputs if i.media_type is media_type and role in (None, i.role)]

    def handles(self) -> dict[str, tuple[MediaType, int]]:
        """What each attachment is called in the prompt, with its kind and its number among that kind: photo1,
        photo2 and clip1 for two photos and a clip. Photos and clips are numbered separately, in the order they were
        attached, which is also the order builders hand them to the model."""
        handles: dict[str, tuple[MediaType, int]] = {}
        counts: Counter[MediaType] = Counter()
        for i in self.inputs:
            counts[i.media_type] += 1
            word = "photo" if i.media_type is MediaType.IMAGE else "clip"
            handles[f"{word}{counts[i.media_type]}"] = (i.media_type, counts[i.media_type])
        return handles

    def prompt_with(self, photo: str, clip: str = "clip {n}") -> str:
        """The prompt with each mention ("@photo2", "@clip1") in the words the model was trained on, e.g.
        photo="image {n}". A mention of something that isn't attached stays as it was typed."""
        handles = self.handles()

        def reword(mention: re.Match[str]) -> str:
            found = handles.get(mention.group(1).lower())
            if found is None:
                return mention.group(0)
            kind, number = found
            return (photo if kind is MediaType.IMAGE else clip).format(n=number)

        return MENTION.sub(reword, self.prompt)


Builder = Callable[[Job], Graph]


@dataclass(frozen=True)
class Workflow:
    id: str
    capabilities: frozenset[Capability]
    # Identifies the model in requests, e.g. "krea-2"
    model: str
    # Shown only when a capability has several models to pick from
    model_name: str
    description: str
    build: Builder
    # The output's area at each quality
    megapixels: Mapping[Quality, float]
    # The shapes offered. A request with attachments can also take the first one's shape.
    aspect_ratios: tuple[AspectRatio, ...] = ASPECT_RATIOS
    # Width and height are rounded to a multiple of this
    multiple: int = 16
    accepts: tuple[Accepts, ...] = ()
    # Videos only: the lengths offered in seconds, and the frame count each one runs
    frames: Mapping[int, int] = field(default_factory=dict)
    # Whether its videos have sound
    sound: bool = False
    # Runs when a request names no model. Needed when several workflows share a capability.
    default: bool = False

    @property
    def media_type(self) -> MediaType:
        return next(iter(self.capabilities)).media_type

    def most(self, role: InputRole, media_type: MediaType) -> int:
        return next((a.most for a in self.accepts if (a.role, a.media_type) == (role, media_type)), 0)

    def size(self, quality: Quality, ratio: tuple[int, int]) -> tuple[int, int]:
        """Width and height for a quality and a shape, worked out as ComfyUI's Resolution Selector does."""
        return size_for(self.megapixels[quality], ratio, self.multiple)


def ratio_of(aspect_ratio: str) -> tuple[int, int]:
    """ "3:4" -> (3, 4)"""
    w, h = aspect_ratio.split(":")
    return int(w), int(h)


def size_for(megapixels: float, ratio: tuple[int, int], multiple: int) -> tuple[int, int]:
    w, h = ratio
    scale = math.sqrt(megapixels * 1024 * 1024 / (w * h))
    return round(w * scale / multiple) * multiple, round(h * scale / multiple) * multiple


def load_workflows(catalogue: str) -> dict[str, Workflow]:
    """The workflows of a catalogue in app.catalogues, by id. Raises WorkflowError if any of them can't be used."""
    try:
        module = importlib.import_module(f"app.catalogues.{catalogue}")
    except ModuleNotFoundError as error:
        raise WorkflowError(f"there is no catalogue called {catalogue!r}") from error
    workflows: list[Workflow] = module.WORKFLOWS
    check_catalogue(workflows)
    return {w.id: w for w in workflows}


def check_workflow(workflow: Workflow) -> list[str]:
    problems: list[str] = []
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", workflow.model):
        problems.append(f"model {workflow.model!r} must be lowercase letters, digits, dots and dashes")
    media_types = {c.media_type for c in workflow.capabilities}
    if len(media_types) != 1:
        problems.append("its capabilities must all make images or all make videos")
        return problems
    for capability in sorted(workflow.capabilities):
        for role in sorted(REQUIRED_ROLES[capability]):
            if not any(a.role is role for a in workflow.accepts):
                problems.append(f"{capability} needs it to accept a {role}")
    if set(workflow.megapixels) != set(Quality):
        problems.append("it needs megapixels for low, medium and high")
    is_video = workflow.media_type is MediaType.VIDEO
    if is_video and not workflow.frames:
        problems.append("a video workflow needs the lengths it offers")
    if not is_video and (workflow.frames or workflow.sound):
        problems.append("lengths and sound are for videos")
    return problems


def check_catalogue(workflows: list[Workflow]) -> None:
    """Checks each workflow, then that ids are unique and every capability with several workflows has one default."""
    problems = [f"{w.id}: {problem}" for w in workflows for problem in check_workflow(w)]
    ids = [w.id for w in workflows]
    problems += [f"{id} is used by several workflows" for id in sorted({i for i in ids if ids.count(i) > 1})]
    for capability in Capability:
        offering = [w for w in workflows if capability in w.capabilities]
        defaults = [w.id for w in offering if w.default]
        if len(offering) > 1 and len(defaults) != 1:
            problems.append(
                f"{capability} has {len(offering)} workflows and needs exactly one default, found {defaults}"
            )
        models = [w.model for w in offering]
        for model in sorted({m for m in models if models.count(m) > 1}):
            problems.append(f"{capability} has several workflows for model {model!r}")
    if problems:
        raise WorkflowError("; ".join(problems))


def default_workflow(workflows: Iterable[Workflow], capability: Capability) -> Workflow | None:
    """The workflow that runs when a request names no model: the one marked default, or the only one there is."""
    offering = [w for w in workflows if capability in w.capabilities]
    if len(offering) == 1:
        return offering[0]
    return next((w for w in offering if w.default), None)


# What the composer needs to offer a workflow's settings


class AcceptsOut(BaseModel):
    role: InputRole
    media_type: MediaType
    most: int


class WorkflowOut(BaseModel):
    id: str
    capabilities: list[Capability]
    model: str
    model_name: str
    description: str
    # The capabilities it runs when a request names no model
    default_for: list[Capability]
    # A request with attachments can also take the first one's shape
    aspect_ratios: list[AspectRatio]
    # Videos only
    durations_s: list[int]
    sound: bool
    accepts: list[AcceptsOut]

    @classmethod
    def of(cls, workflow: Workflow, workflows: Iterable[Workflow]) -> WorkflowOut:
        workflows = list(workflows)
        return cls(
            id=workflow.id,
            capabilities=sorted(workflow.capabilities),
            model=workflow.model,
            model_name=workflow.model_name,
            description=workflow.description,
            default_for=[c for c in sorted(workflow.capabilities) if default_workflow(workflows, c) is workflow],
            aspect_ratios=list(workflow.aspect_ratios),
            durations_s=sorted(workflow.frames),
            sound=workflow.sound,
            accepts=[AcceptsOut(role=a.role, media_type=a.media_type, most=a.most) for a in workflow.accepts],
        )


def get_workflows(request: Request) -> dict[str, Workflow]:
    workflows: dict[str, Workflow] = request.app.state.workflows
    return workflows


WorkflowsDep = Annotated[dict[str, Workflow], Depends(get_workflows)]

router = APIRouter()


@router.get("/workflows")
def list_workflows(workflows: WorkflowsDep) -> list[WorkflowOut]:
    return [WorkflowOut.of(w, workflows.values()) for w in workflows.values()]
