from dataclasses import replace

import pytest

from app.models import Capability, InputRole, MediaType
from app.routing import Attached, RoutingError, capability_for, choose_pipeline, route
from tests.catalogue import EDIT, IMAGE, VIDEO

PHOTO, CLIP = MediaType.IMAGE, MediaType.VIDEO
REF_PHOTO: Attached = (InputRole.REFERENCE, PHOTO)
REF_CLIP: Attached = (InputRole.REFERENCE, CLIP)


@pytest.mark.parametrize(
    ("media_type", "inputs", "capability"),
    [
        (PHOTO, [], Capability.IMAGE_GENERATE),
        (PHOTO, [REF_PHOTO], Capability.IMAGE_EDIT),
        (PHOTO, [REF_PHOTO, REF_PHOTO, REF_PHOTO], Capability.IMAGE_EDIT),
        (PHOTO, [REF_CLIP], Capability.IMAGE_EDIT),
        (CLIP, [], Capability.VIDEO_GENERATE),
        (CLIP, [REF_PHOTO], Capability.VIDEO_REFERENCE),
        (CLIP, [REF_CLIP, REF_PHOTO], Capability.VIDEO_REFERENCE),
    ],
)
def test_the_output_type_and_input_roles_decide_the_capability(
    media_type: MediaType, inputs: list[Attached], capability: Capability
) -> None:
    assert capability_for(media_type, inputs) is capability


OTHER = replace(IMAGE, id="other", model="other")
CATALOGUE = [replace(IMAGE, default=True), OTHER, EDIT, VIDEO]


def test_a_request_without_a_model_gets_the_default() -> None:
    assert choose_pipeline(CATALOGUE, Capability.IMAGE_GENERATE, None).id == "t2i"
    assert choose_pipeline(CATALOGUE, Capability.VIDEO_REFERENCE, None).id == "video"


def test_a_named_model_picks_its_pipeline() -> None:
    assert choose_pipeline(CATALOGUE, Capability.IMAGE_GENERATE, "other").id == "other"


def test_a_model_that_cannot_do_the_capability_is_refused() -> None:
    with pytest.raises(RoutingError, match="^Editing an image isn't available with that model$"):
        choose_pipeline(CATALOGUE, Capability.IMAGE_EDIT, "other")


def test_a_capability_without_pipelines_is_refused() -> None:
    with pytest.raises(RoutingError, match="^Making a video isn't available yet$"):
        choose_pipeline([IMAGE], Capability.VIDEO_GENERATE, None)


def test_route_checks_the_inputs_fit_the_pipeline() -> None:
    assert route(CATALOGUE, PHOTO, [REF_PHOTO] * 3, None).id == "edit"
    with pytest.raises(RoutingError, match="^Editing an image takes at most 3 photos$"):
        route(CATALOGUE, PHOTO, [REF_PHOTO] * 4, None)
    with pytest.raises(RoutingError, match="^Editing an image can't use clips$"):
        route(CATALOGUE, PHOTO, [REF_PHOTO, REF_CLIP], None)
    with pytest.raises(RoutingError, match="^Making a video takes at most 1 clip$"):
        route(CATALOGUE, CLIP, [REF_CLIP, REF_CLIP], None)
