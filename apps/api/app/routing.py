"""Which pipeline runs a request.

The user never picks a pipeline. The output type and the roles of the attached inputs decide the capability: a
picture with photos attached is image.edit, a video with photos or clips is video.reference. Among the pipelines for
that capability, the model the request names runs it, or the capability's default when it names none.

The composer works the route out the same way before sending (apps/web/src/lib/routing.ts), with the same messages.
"""

from collections import Counter
from collections.abc import Iterable

from app.models import Capability, InputRole, MediaType
from app.pipelines import Pipeline, default_pipeline


class RoutingError(ValueError):
    """A request that no pipeline can run. The message is written for the person who sent it."""


# An attachment, as routing sees it: its role and whether it is a photo or a clip
Attached = tuple[InputRole, MediaType]

DOING = {
    Capability.IMAGE_GENERATE: "Creating an image",
    Capability.IMAGE_EDIT: "Editing an image",
    Capability.VIDEO_GENERATE: "Making a video",
    Capability.VIDEO_REFERENCE: "Making a video",
}


def route(pipelines: Iterable[Pipeline], media_type: MediaType, inputs: list[Attached], model: str | None) -> Pipeline:
    capability = capability_for(media_type, inputs)
    pipeline = choose_pipeline(pipelines, capability, model)
    for (role, kind), count in Counter(inputs).items():
        most = pipeline.most(role, kind)
        if count > most:
            what = "photo" if kind is MediaType.IMAGE else "clip"
            raise RoutingError(
                f"{DOING[capability]} can't use {plural(what)}"
                if most == 0
                else f"{DOING[capability]} takes at most {counted(most, what)}"
            )
    return pipeline


def capability_for(media_type: MediaType, inputs: list[Attached]) -> Capability:
    if media_type is MediaType.IMAGE:
        return Capability.IMAGE_EDIT if inputs else Capability.IMAGE_GENERATE
    return Capability.VIDEO_REFERENCE if inputs else Capability.VIDEO_GENERATE


def choose_pipeline(pipelines: Iterable[Pipeline], capability: Capability, model: str | None) -> Pipeline:
    offering = [w for w in pipelines if capability in w.capabilities]
    if not offering:
        raise RoutingError(f"{DOING[capability]} isn't available yet")
    if model is None:
        default = default_pipeline(offering, capability)
        # load_pipelines refuses a catalogue without one
        assert default is not None
        return default
    for pipeline in offering:
        if pipeline.model == model:
            return pipeline
    raise RoutingError(f"{DOING[capability]} isn't available with that model")


def plural(noun: str) -> str:
    return f"{noun}s"


def counted(count: int, noun: str) -> str:
    return f"{count} {noun if count == 1 else plural(noun)}"
