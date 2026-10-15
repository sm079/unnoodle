"""Which workflow runs a request.

The user never picks a workflow. The output type and the roles of the attached inputs decide the capability: an
image with a photo to edit is image.edit, a video with reference photos or clips is video.reference. Among the
workflows for that capability, the model the request names runs it, or the capability's default when it names none.

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
    Capability.IMAGE_GENERATE: "Making a picture",
    Capability.IMAGE_EDIT: "Editing a photo",
    Capability.VIDEO_GENERATE: "Making a video",
    Capability.VIDEO_REFERENCE: "Making a video",
}


def route(workflows: Iterable[Workflow], media_type: MediaType, inputs: list[Attached], model: str | None) -> Workflow:
    capability = capability_for(media_type, inputs)
    workflow = choose_workflow(workflows, capability, model)
    for (role, kind), count in Counter(inputs).items():
        most = workflow.most(role, kind)
        if count > most:
            what = noun(role, kind)
            raise RoutingError(
                f"{DOING[capability]} can't use {plural(what)}"
                if most == 0
                else f"{DOING[capability]} takes at most {counted(most, what)}"
            )
    return workflow


def capability_for(media_type: MediaType, inputs: list[Attached]) -> Capability:
    roles = Counter(role for role, _ in inputs)
    if (InputRole.EDIT_TARGET, MediaType.VIDEO) in inputs:
        raise RoutingError("Only a photo can be edited")
    if media_type is MediaType.IMAGE:
        if not inputs:
            return Capability.IMAGE_GENERATE
        if roles[InputRole.EDIT_TARGET] > 1:
            raise RoutingError("Only one photo can be the one to edit")
        if roles[InputRole.EDIT_TARGET] == 0:
            raise RoutingError("Pick the photo to edit")
        return Capability.IMAGE_EDIT
    if roles[InputRole.EDIT_TARGET]:
        raise RoutingError("A video can't edit a photo, but it can use one as a reference")
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


def noun(role: InputRole, media_type: MediaType) -> str:
    if role is InputRole.EDIT_TARGET:
        return "photo to edit"
    return "reference photo" if media_type is MediaType.IMAGE else "reference clip"


def plural(noun: str) -> str:
    # "photo to edit" -> "photos to edit"
    first, _, rest = noun.partition(" to ")
    return f"{first}s to {rest}" if rest else f"{noun}s"


def counted(count: int, noun: str) -> str:
    return f"{count} {noun if count == 1 else plural(noun)}"
