from dataclasses import replace

import pytest

from app.models import Capability, InputRole, MediaType
from app.routing import Attached, RoutingError, capability_for, choose_workflow, route
from tests.catalogue import EDIT, IMAGE, VIDEO

PHOTO, CLIP = MediaType.IMAGE, MediaType.VIDEO
TARGET: Attached = (InputRole.EDIT_TARGET, PHOTO)
REF_PHOTO: Attached = (InputRole.REFERENCE, PHOTO)
REF_CLIP: Attached = (InputRole.REFERENCE, CLIP)


@pytest.mark.parametrize(
    ("media_type", "inputs", "capability"),
    [
        (PHOTO, [], Capability.IMAGE_GENERATE),
        (PHOTO, [TARGET], Capability.IMAGE_EDIT),
        (PHOTO, [TARGET, REF_PHOTO, REF_PHOTO], Capability.IMAGE_EDIT),
        (PHOTO, [REF_PHOTO, TARGET], Capability.IMAGE_EDIT),
        (CLIP, [], Capability.VIDEO_GENERATE),
        (CLIP, [REF_PHOTO], Capability.VIDEO_REFERENCE),
        (CLIP, [REF_CLIP, REF_PHOTO], Capability.VIDEO_REFERENCE),
    ],
)
def test_the_output_type_and_input_roles_decide_the_capability(
    media_type: MediaType, inputs: list[Attached], capability: Capability
) -> None:
    assert capability_for(media_type, inputs) is capability


@pytest.mark.parametrize(
    ("media_type", "inputs", "message"),
    [
        (PHOTO, [REF_PHOTO], "Pick the photo to edit"),
        (PHOTO, [TARGET, TARGET], "Only one photo can be the one to edit"),
        (PHOTO, [(InputRole.EDIT_TARGET, CLIP)], "Only a photo can be edited"),
        (CLIP, [TARGET], "A video can't edit a photo, but it can use one as a reference"),
    ],
)
def test_combinations_nothing_handles_are_refused(media_type: MediaType, inputs: list[Attached], message: str) -> None:
    with pytest.raises(RoutingError, match=f"^{message}$"):
        capability_for(media_type, inputs)


OTHER = replace(IMAGE, id="other", model="other")
CATALOGUE = [replace(IMAGE, default=True), OTHER, EDIT, VIDEO]


def test_a_request_without_a_model_gets_the_default() -> None:
    assert choose_workflow(CATALOGUE, Capability.IMAGE_GENERATE, None).id == "t2i"
    assert choose_workflow(CATALOGUE, Capability.VIDEO_REFERENCE, None).id == "video"


def test_a_named_model_picks_its_workflow() -> None:
    assert choose_workflow(CATALOGUE, Capability.IMAGE_GENERATE, "other").id == "other"


def test_a_model_that_cannot_do_the_capability_is_refused() -> None:
    with pytest.raises(RoutingError, match="^Editing a photo isn't available with that model$"):
        choose_workflow(CATALOGUE, Capability.IMAGE_EDIT, "other")


def test_a_capability_without_workflows_is_refused() -> None:
    with pytest.raises(RoutingError, match="^Making a video isn't available yet$"):
        choose_workflow([IMAGE], Capability.VIDEO_GENERATE, None)


def test_route_checks_the_inputs_fit_the_workflow() -> None:
    assert route(CATALOGUE, PHOTO, [TARGET, REF_PHOTO, REF_PHOTO], None).id == "edit"
    with pytest.raises(RoutingError, match="^Editing a photo takes at most 2 reference photos$"):
        route(CATALOGUE, PHOTO, [TARGET, REF_PHOTO, REF_PHOTO, REF_PHOTO], None)
    with pytest.raises(RoutingError, match="^Editing a photo can't use reference clips$"):
        route(CATALOGUE, PHOTO, [TARGET, REF_CLIP], None)
    with pytest.raises(RoutingError, match="^Making a video takes at most 1 reference clip$"):
        route(CATALOGUE, CLIP, [REF_CLIP, REF_CLIP], None)
