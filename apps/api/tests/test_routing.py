import pytest

from app.models import Capability, InputRole, MediaType
from app.routing import RoutingError, capability_for, choose_workflow, route
from app.workflows import Manifest, Workflow

IMAGE, VIDEO = MediaType.IMAGE, MediaType.VIDEO
START, END, KEY, REF = InputRole.START_FRAME, InputRole.END_FRAME, InputRole.KEYFRAME, InputRole.REFERENCE
EDIT, RESTYLE, SOURCE = InputRole.EDIT_TARGET, InputRole.RESTYLE, InputRole.SOURCE_VIDEO


@pytest.mark.parametrize(
    ("media_type", "roles", "capability"),
    [
        (IMAGE, [], Capability.IMAGE_GENERATE),
        (IMAGE, [EDIT], Capability.IMAGE_EDIT),
        (IMAGE, [EDIT, REF, REF], Capability.IMAGE_EDIT),
        (IMAGE, [REF, EDIT], Capability.IMAGE_EDIT),
        (IMAGE, [RESTYLE], Capability.IMAGE_RESTYLE),
        (IMAGE, [REF], Capability.IMAGE_MULTI_REF),
        (IMAGE, [REF, REF, REF], Capability.IMAGE_MULTI_REF),
        (VIDEO, [], Capability.VIDEO_GENERATE),
        (VIDEO, [START], Capability.VIDEO_FROM_FRAME),
        (VIDEO, [START, END], Capability.VIDEO_FIRST_LAST),
        (VIDEO, [END, START], Capability.VIDEO_FIRST_LAST),
        (VIDEO, [KEY, KEY, KEY], Capability.VIDEO_KEYFRAMES),
        (VIDEO, [REF, REF], Capability.VIDEO_REFERENCE),
        (VIDEO, [SOURCE, REF], Capability.VIDEO_CHARACTER_SWAP),
    ],
)
def test_the_output_type_and_input_roles_decide_the_capability(
    media_type: MediaType, roles: list[InputRole], capability: Capability
) -> None:
    assert capability_for(media_type, roles) is capability


@pytest.mark.parametrize(
    ("media_type", "roles", "message"),
    [
        (IMAGE, [START], "A start frame can't be used to make an image"),
        (VIDEO, [EDIT], "An edit target can't be used to make a video"),
        (IMAGE, [EDIT, EDIT], "Nothing makes an image from 2 edit targets"),
        (IMAGE, [RESTYLE, REF], "Nothing makes an image from 1 restyle and 1 reference"),
        (VIDEO, [END], "Nothing makes a video from 1 end frame"),
        (VIDEO, [START, START], "Nothing makes a video from 2 start frames"),
        (VIDEO, [START, KEY], "Nothing makes a video from 1 start frame and 1 keyframe"),
        (VIDEO, [SOURCE], "Nothing makes a video from 1 source video"),
    ],
)
def test_combinations_nothing_handles_are_refused(media_type: MediaType, roles: list[InputRole], message: str) -> None:
    with pytest.raises(RoutingError, match=f"^{message}$"):
        capability_for(media_type, roles)


def workflow(id: str, capability: Capability, model: str, default: bool = False, **roles: int) -> Workflow:
    manifest = Manifest(
        capability=capability,
        model=model,
        model_name=model.title(),
        description="",
        default=default,
        sizes={"1K": {"1:1": (1024, 1024)}},
    )
    return Workflow(id, manifest, {}, {}, "1", {InputRole(role): count for role, count in roles.items()})


CATALOGUE = [
    workflow("anima", Capability.IMAGE_GENERATE, "anima"),
    workflow("flux-t2i", Capability.IMAGE_GENERATE, "flux", default=True),
    workflow("flux-edit", Capability.IMAGE_EDIT, "flux", edit_target=1, reference=2),
]


def test_a_request_without_a_model_gets_the_default() -> None:
    assert choose_workflow(CATALOGUE, Capability.IMAGE_GENERATE, None).id == "flux-t2i"
    assert choose_workflow(CATALOGUE, Capability.IMAGE_EDIT, None).id == "flux-edit"


def test_a_named_model_picks_its_workflow() -> None:
    assert choose_workflow(CATALOGUE, Capability.IMAGE_GENERATE, "anima").id == "anima"


def test_a_model_that_cannot_do_the_capability_is_refused() -> None:
    with pytest.raises(RoutingError, match="^anima doesn't do image.edit; these do: flux$"):
        choose_workflow(CATALOGUE, Capability.IMAGE_EDIT, "anima")


def test_a_capability_without_workflows_is_refused() -> None:
    with pytest.raises(RoutingError, match="^No workflow does video.generate yet$"):
        choose_workflow(CATALOGUE, Capability.VIDEO_GENERATE, None)


def test_route_checks_the_inputs_fit_the_workflow() -> None:
    assert route(CATALOGUE, IMAGE, [EDIT, REF, REF], None).id == "flux-edit"
    with pytest.raises(RoutingError, match="^Flux takes at most 2 references$"):
        route(CATALOGUE, IMAGE, [EDIT, REF, REF, REF], None)
