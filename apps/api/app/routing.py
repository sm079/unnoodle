"""Which workflow runs a request.

The user never picks a workflow. The output type and the roles of the attached inputs decide the capability: a
picture with photos attached is image.edit, a video with photos or clips is video.reference. Among the workflows for
that capability, the model the request names runs it, or the capability's default when it names none.

The composer works the route out the same way before sending (apps/web/src/lib/routing.ts), with the same messages.
"""

from collections import Counter
from collections.abc import Iterable

from app.models import Capability, InputRole, MediaType
from app.workflows import Workflow, default_workflow


class RoutingError(ValueError):
    """A request that no workflow can run. The message is written for the person who sent it."""


# An attachment, as routing sees it: its role and whether it is a photo or a clip
Attached = tuple[InputRole, MediaType]

DOING = {
    Capability.IMAGE_GENERATE: "Creating an image",
    Capability.IMAGE_EDIT: "Editing an image",
    Capability.VIDEO_GENERATE: "Making a video",
    Capability.VIDEO_REFERENCE: "Making a video",
}


def route(workflows: Iterable[Workflow], media_type: MediaType, inputs: list[Attached], model: str | None) -> Workflow:
    capability = capability_for(media_type, inputs)
    workflow = choose_workflow(workflows, capability, model)
    for (role, kind), count in Counter(inputs).items():
        most = workflow.most(role, kind)
        if count > most:
            what = "photo" if kind is MediaType.IMAGE else "clip"
            raise RoutingError(
                f"{DOING[capability]} can't use {plural(what)}"
                if most == 0
                else f"{DOING[capability]} takes at most {counted(most, what)}"
            )
    return workflow


def capability_for(media_type: MediaType, inputs: list[Attached]) -> Capability:
    if media_type is MediaType.IMAGE:
        return Capability.IMAGE_EDIT if inputs else Capability.IMAGE_GENERATE
    return Capability.VIDEO_REFERENCE if inputs else Capability.VIDEO_GENERATE


def choose_workflow(workflows: Iterable[Workflow], capability: Capability, model: str | None) -> Workflow:
    offering = [w for w in workflows if capability in w.capabilities]
    if not offering:
        raise RoutingError(f"{DOING[capability]} isn't available yet")
    if model is None:
        default = default_workflow(offering, capability)
        # load_workflows refuses a catalogue without one
        assert default is not None
        return default
    for workflow in offering:
        if workflow.model == model:
            return workflow
    raise RoutingError(f"{DOING[capability]} isn't available with that model")


def plural(noun: str) -> str:
    return f"{noun}s"


def counted(count: int, noun: str) -> str:
    return f"{count} {noun if count == 1 else plural(noun)}"
