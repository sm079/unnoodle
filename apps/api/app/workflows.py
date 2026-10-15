"""Workflows: ComfyUI graphs that each implement one capability, plus the manifest that describes them.

Each workflow is a folder:

    <workflows dir>/<id>/
        workflow.json   the graph, exported from ComfyUI with Export (API)
        manifest.toml   capability, model, sizes and limits: what the graph itself can't say

The app and a graph agree on node titles only, never node ids, so a graph can be rebuilt freely as long as the titles
stay. A node titled "in.<name>" receives a value: a primitive node gets it as its value, a LoadImage or LoadVideo node
gets an uploaded file. The node titled "out.media" saves the result. Inputs that take a single asset are titled after
their role (in.start_frame); roles that take several are numbered from 1 (in.reference_1, in.reference_2), so the
graph decides how many it accepts.

Everything is checked when the workflows load, so a broken export stops the API from starting rather than failing a
request later.
"""

import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import Capability, InputRole, MediaType

INPUT_PREFIX = "in."
OUTPUT_TITLE = "out.media"

AspectRatio = Literal["1:1", "4:3", "3:4", "16:9", "9:16"]

# Values the worker fills in, beyond attached assets
PARAMETERS = {"prompt", "seed", "width", "height", "batch_size", "frames", "fps", "audio"}
REQUIRED_PARAMETERS = {"prompt", "seed", "width", "height"}
VIDEO_PARAMETERS = {"frames", "fps"}

# Roles that take several assets get numbered nodes; the rest get one
NUMBERED_ROLES = {InputRole.REFERENCE, InputRole.KEYFRAME}

# Which input of a bound node receives the value
VALUE_FIELDS = {
    "PrimitiveInt": "value",
    "PrimitiveFloat": "value",
    "PrimitiveBoolean": "value",
    "PrimitiveString": "value",
    "PrimitiveStringMultiline": "value",
    "LoadImage": "image",
    "LoadVideo": "file",
}
ASSET_NODES = {"LoadImage": MediaType.IMAGE, "LoadVideo": MediaType.VIDEO}

# The roles a capability can't do without
REQUIRED_ROLES: dict[Capability, set[InputRole]] = {
    Capability.IMAGE_GENERATE: set(),
    Capability.IMAGE_EDIT: {InputRole.EDIT_TARGET},
    Capability.IMAGE_RESTYLE: {InputRole.RESTYLE},
    Capability.IMAGE_MULTI_REF: {InputRole.REFERENCE},
    Capability.VIDEO_GENERATE: set(),
    Capability.VIDEO_FROM_FRAME: {InputRole.START_FRAME},
    Capability.VIDEO_FIRST_LAST: {InputRole.START_FRAME, InputRole.END_FRAME},
    Capability.VIDEO_KEYFRAMES: {InputRole.KEYFRAME},
    Capability.VIDEO_REFERENCE: {InputRole.REFERENCE},
    Capability.VIDEO_CHARACTER_SWAP: {InputRole.SOURCE_VIDEO, InputRole.REFERENCE},
}


class WorkflowError(Exception):
    """A workflow folder that can't be used. The message names the folder and every problem found."""


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: Capability
    # Identifies the model in requests, e.g. "ltx-2.5"
    model: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]*$")]
    # Shown in the model menu, e.g. "LTX 2.5"
    model_name: str
    description: str
    # Picked when a request names no model. Required when several workflows share a capability.
    default: bool = False
    # Output sizes in pixels as (width, height), by resolution label ("1K", "720p") and then aspect ratio
    sizes: dict[str, dict[AspectRatio, tuple[int, int]]] = Field(min_length=1)
    max_count: int = Field(default=1, ge=1)
    # Videos only
    fps: int | None = Field(default=None, gt=0)
    durations_s: list[float] = []
    audio: bool = False


@dataclass(frozen=True)
class Binding:
    node_id: str
    field: str


@dataclass(frozen=True)
class Workflow:
    id: str
    manifest: Manifest
    graph: dict[str, Any]
    # By input name, e.g. "prompt" or "reference_2"
    bindings: dict[str, Binding]
    output_node: str
    # The most assets the graph accepts in each role it has nodes for
    roles: dict[InputRole, int]

    @property
    def capability(self) -> Capability:
        return self.manifest.capability


def load_workflows(directory: Path) -> dict[str, Workflow]:
    """Loads every workflow folder in a directory, by id. Raises WorkflowError if any of them can't be used."""
    if not directory.is_dir():
        raise WorkflowError(f"{directory}: no such directory")
    workflows = {folder.name: load_workflow(folder) for folder in sorted(directory.iterdir()) if folder.is_dir()}
    check_catalogue(list(workflows.values()))
    return workflows


def load_workflow(folder: Path) -> Workflow:
    problems: list[str] = []
    try:
        manifest = Manifest.model_validate(tomllib.loads((folder / "manifest.toml").read_text(encoding="utf-8")))
        graph = json.loads((folder / "workflow.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkflowError(f"{folder.name}: missing {Path(str(error.filename)).name}") from error
    except tomllib.TOMLDecodeError as error:
        raise WorkflowError(f"{folder.name}: manifest.toml: {error}") from error
    except json.JSONDecodeError as error:
        raise WorkflowError(f"{folder.name}: workflow.json: {error}") from error
    except ValidationError as error:
        fields = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        raise WorkflowError(f"{folder.name}: manifest.toml: {fields}") from error

    titles: dict[str, list[str]] = {}
    for node_id, node in graph.items():
        title = node.get("_meta", {}).get("title")
        if isinstance(title, str):
            titles.setdefault(title, []).append(node_id)
    for title, node_ids in titles.items():
        if len(node_ids) > 1 and (title.startswith(INPUT_PREFIX) or title == OUTPUT_TITLE):
            problems.append(f"{len(node_ids)} nodes are titled {title!r}")

    output_nodes = titles.get(OUTPUT_TITLE, [])
    if not output_nodes:
        problems.append(f"no node is titled {OUTPUT_TITLE!r}")

    bindings: dict[str, Binding] = {}
    asset_roles: dict[str, InputRole] = {}
    for title, node_ids in titles.items():
        if not title.startswith(INPUT_PREFIX):
            continue
        name = title.removeprefix(INPUT_PREFIX)
        class_type = graph[node_ids[0]].get("class_type")
        role = role_for_input(name)
        if role is None and name not in PARAMETERS:
            problems.append(f"{title!r} is not an input the app can fill")
            continue
        if class_type not in VALUE_FIELDS:
            problems.append(f"{title!r} is a {class_type} node; bound nodes must be one of {sorted(VALUE_FIELDS)}")
            continue
        if (role is not None) != (class_type in ASSET_NODES):
            kind = "a LoadImage or LoadVideo node" if role is not None else "a primitive node"
            problems.append(f"{title!r} must be {kind}")
            continue
        bindings[name] = Binding(node_ids[0], VALUE_FIELDS[class_type])
        if role is not None:
            asset_roles[name] = role

    media_type = manifest.capability.media_type
    needed = REQUIRED_PARAMETERS | (VIDEO_PARAMETERS if media_type is MediaType.VIDEO else set())
    if manifest.max_count > 1 and media_type is MediaType.IMAGE:
        needed.add("batch_size")
    problems += [f"no node is titled {INPUT_PREFIX + name!r}" for name in sorted(needed - bindings.keys())]

    roles = count_roles(asset_roles, problems)
    missing_roles = REQUIRED_ROLES[manifest.capability] - roles.keys()
    problems += [f"{manifest.capability} needs a {role} input" for role in sorted(missing_roles)]

    is_video = media_type is MediaType.VIDEO
    if is_video and (manifest.fps is None or not manifest.durations_s):
        problems.append("video workflows need fps and durations_s")
    if not is_video and (manifest.fps is not None or manifest.durations_s or manifest.audio):
        problems.append("fps, durations_s and audio are for video workflows")
    if manifest.audio and "audio" not in bindings:
        problems.append(f"audio is offered but no node is titled {INPUT_PREFIX + 'audio'!r}")

    if problems:
        raise WorkflowError(f"{folder.name}: " + "; ".join(problems))
    return Workflow(folder.name, manifest, graph, bindings, output_nodes[0], roles)


def role_for_input(name: str) -> InputRole | None:
    """The role an asset input name stands for: "start_frame" and "reference_2" have one, "seed" doesn't."""
    match = re.fullmatch(r"([a-z_]+?)(?:_(\d+))?", name)
    if match is None:
        return None
    base, number = match.groups()
    try:
        role = InputRole(base)
    except ValueError:
        return None
    return role if (number is not None) == (role in NUMBERED_ROLES) else None


def count_roles(asset_roles: dict[str, InputRole], problems: list[str]) -> dict[InputRole, int]:
    roles: dict[InputRole, int] = {}
    for role in set(asset_roles.values()):
        if role not in NUMBERED_ROLES:
            roles[role] = 1
            continue
        numbers = sorted(int(name.rsplit("_", 1)[1]) for name, r in asset_roles.items() if r is role)
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(f"{role} inputs must be numbered 1 to {len(numbers)}, found {numbers}")
        roles[role] = len(numbers)
    return roles


def check_catalogue(workflows: list[Workflow]) -> None:
    """Every capability with several workflows needs exactly one default, and model ids can't repeat within one."""
    problems: list[str] = []
    for capability in Capability:
        offering = [w for w in workflows if w.capability is capability]
        defaults = [w.id for w in offering if w.manifest.default]
        if len(offering) > 1 and len(defaults) != 1:
            problems.append(
                f"{capability} has {len(offering)} workflows and needs exactly one default, found {defaults}"
            )
        models = [w.manifest.model for w in offering]
        for model in sorted({m for m in models if models.count(m) > 1}):
            problems.append(f"{capability} has several workflows for model {model!r}")
    if problems:
        raise WorkflowError("; ".join(problems))


# What the composer needs to offer a workflow's settings


class WorkflowOut(BaseModel):
    id: str
    capability: Capability
    model: str
    model_name: str
    description: str
    # Runs when a request for this capability names no model
    default: bool
    # The aspect ratios offered at each resolution
    resolutions: dict[str, list[AspectRatio]]
    max_count: int
    durations_s: list[float]
    audio: bool
    # The most assets accepted per role
    roles: dict[InputRole, int]

    @classmethod
    def of(cls, workflow: Workflow, default: bool) -> WorkflowOut:
        m = workflow.manifest
        return cls(
            id=workflow.id,
            capability=m.capability,
            model=m.model,
            model_name=m.model_name,
            description=m.description,
            default=default,
            resolutions={label: list(ratios) for label, ratios in m.sizes.items()},
            max_count=m.max_count,
            durations_s=m.durations_s,
            audio=m.audio,
            roles=workflow.roles,
        )


def get_workflows(request: Request) -> dict[str, Workflow]:
    workflows: dict[str, Workflow] = request.app.state.workflows
    return workflows


WorkflowsDep = Annotated[dict[str, Workflow], Depends(get_workflows)]

router = APIRouter()


@router.get("/workflows")
def list_workflows(workflows: WorkflowsDep) -> list[WorkflowOut]:
    defaults = [default_workflow(workflows.values(), capability) for capability in Capability]
    default_ids = {w.id for w in defaults if w is not None}
    return [WorkflowOut.of(w, w.id in default_ids) for w in workflows.values()]


def default_workflow(workflows: Iterable[Workflow], capability: Capability) -> Workflow | None:
    """The workflow that runs when a request names no model: the one marked default, or the only one there is."""
    offering = [w for w in workflows if w.capability is capability]
    if len(offering) == 1:
        return offering[0]
    return next((w for w in offering if w.manifest.default), None)
