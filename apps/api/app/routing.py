"""Which workflow runs a request.

The user never picks a workflow. The output type and the roles of the attached inputs decide the capability: a video
with a start frame is video.from_frame, with a start and an end frame it is video.first_last. Among the workflows for
that capability, the model the request names runs it, or the capability's default when it names none.
"""

from collections import Counter
from collections.abc import Iterable

from app.models import Capability, InputRole, MediaType
from app.workflows import Workflow, default_workflow


class RoutingError(ValueError):
    """A request that no workflow can run. The message is written for the person who sent it."""


A_MEDIA = {MediaType.IMAGE: "an image", MediaType.VIDEO: "a video"}


ROLES_FOR = {
    MediaType.IMAGE: {InputRole.EDIT_TARGET, InputRole.RESTYLE, InputRole.REFERENCE},
    MediaType.VIDEO: {
        InputRole.START_FRAME,
        InputRole.END_FRAME,
        InputRole.KEYFRAME,
        InputRole.REFERENCE,
        InputRole.SOURCE_VIDEO,
    },
}


def route(workflows: Iterable[Workflow], media_type: MediaType, roles: list[InputRole], model: str | None) -> Workflow:
    capability = capability_for(media_type, roles)
    workflow = choose_workflow(workflows, capability, model)
    for role, count in Counter(roles).items():
        most = workflow.roles.get(role, 0)
        if count > most:
            raise RoutingError(f"{workflow.manifest.model_name} takes at most {inputs_phrase(role, most)}")
    return workflow


def capability_for(media_type: MediaType, roles: Iterable[InputRole]) -> Capability:
    counts = Counter(roles)
    present = set(counts)
    for role in sorted(present - ROLES_FOR[media_type]):
        raise RoutingError(f"{article(words(role)).capitalize()} can't be used to make {A_MEDIA[media_type]}")

    if media_type is MediaType.IMAGE:
        if not present:
            return Capability.IMAGE_GENERATE
        if counts[InputRole.EDIT_TARGET] == 1 and present <= {InputRole.EDIT_TARGET, InputRole.REFERENCE}:
            return Capability.IMAGE_EDIT
        if counts == {InputRole.RESTYLE: 1}:
            return Capability.IMAGE_RESTYLE
        if present == {InputRole.REFERENCE}:
            return Capability.IMAGE_MULTI_REF
    else:
        if not present:
            return Capability.VIDEO_GENERATE
        if counts == {InputRole.START_FRAME: 1}:
            return Capability.VIDEO_FROM_FRAME
        if counts == {InputRole.START_FRAME: 1, InputRole.END_FRAME: 1}:
            return Capability.VIDEO_FIRST_LAST
        if present == {InputRole.KEYFRAME}:
            return Capability.VIDEO_KEYFRAMES
        if present == {InputRole.REFERENCE}:
            return Capability.VIDEO_REFERENCE
        if counts == {InputRole.SOURCE_VIDEO: 1, InputRole.REFERENCE: 1}:
            return Capability.VIDEO_CHARACTER_SWAP

    inputs = " and ".join(inputs_phrase(role, count) for role, count in counts.items())
    raise RoutingError(f"Nothing makes {A_MEDIA[media_type]} from {inputs}")


def choose_workflow(workflows: Iterable[Workflow], capability: Capability, model: str | None) -> Workflow:
    offering = [w for w in workflows if w.capability is capability]
    if not offering:
        raise RoutingError(f"No workflow does {capability} yet")
    if model is None:
        default = default_workflow(offering, capability)
        # load_workflows refuses a catalogue without one
        assert default is not None
        return default
    for workflow in offering:
        if workflow.manifest.model == model:
            return workflow
    available = ", ".join(sorted(w.manifest.model for w in offering))
    raise RoutingError(f"{model} doesn't do {capability}; these do: {available}")


def words(role: InputRole) -> str:
    return role.replace("_", " ")


def inputs_phrase(role: InputRole, count: int) -> str:
    return f"{count} {words(role)}" + ("s" if count != 1 else "")


def article(noun: str) -> str:
    return f"{'an' if noun[0] in 'aeiou' else 'a'} {noun}"
