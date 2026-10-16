"""Stand-ins for the real workflows that run on the dev ComfyUI without any models (see the README).

They take the same inputs and offer the same settings as the real ones, and use the dev node in
dev/comfyui/custom_nodes to take a few seconds, report progress, fail on demand ("#oom" in the prompt) and write the
prompt on the result, so the whole app can be tried on a laptop.
"""

from dataclasses import replace

from app.catalogues.real import (
    IMAGE_MEGAPIXELS,
    MINIMAX_FRAMES,
    VIDEO_MEGAPIXELS,
    klein_seconds,
    krea2_seconds,
    minimax_seconds,
)
from app.graph import Graph, Link
from app.models import Capability, InputRole, MediaType
from app.workflows import Accepts, Job, Work, Workflow


def stamp(g: Graph, images: Link, job: Job, prompt: str) -> Link:
    """The dev node: steps through for a few seconds, then writes the prompt on the images."""
    return g.add("UnnoodleDevSteps", images=images, prompt=prompt, seed=job.seed, steps=12, step_seconds=0.25)[0]


def paste_small(g: Graph, picture: Link, small: Link, n: int) -> Link:
    """Pastes a small image into the corner of every frame, stepping down for each one."""
    offset = 16 + 32 * n
    return g.add("ImageCompositeMasked", destination=picture, source=small, x=offset, y=offset, resize_source=False)[0]


def shrink(g: Graph, image: Link, megapixels: float) -> Link:
    small = g.add(
        "ImageScaleToTotalPixels",
        image=image,
        upscale_method="area",
        megapixels=max(megapixels / 25, 0.01),
        resolution_steps=1,
    )
    return small[0]


def image(job: Job) -> Graph:
    width, height = job.size
    g = Graph()
    canvas = g.add("EmptyImage", width=width, height=height, batch_size=1, color=0x202020)
    g.output(g.add("SaveImage", images=stamp(g, canvas[0], job, job.prompt), filename_prefix=job.filename_prefix))
    return g


def edit(job: Job) -> Graph:
    """The first photo filling the size asked for, with the others pasted small in its corner."""
    width, height = job.size
    g = Graph()
    photos = job.files(MediaType.IMAGE)
    loaded = g.add("LoadImage", image=photos[0])
    filled = g.add("ImageScale", image=loaded[0], upscale_method="lanczos", width=width, height=height, crop="center")
    picture = filled[0]
    for n, photo in enumerate(photos[1:]):
        picture = paste_small(g, picture, shrink(g, g.add("LoadImage", image=photo)[0], job.megapixels), n)
    # The prompt as the real edit model reads it, to show the rewriting
    prompt = job.prompt_with(photo="image {n}")
    g.output(g.add("SaveImage", images=stamp(g, picture, job, prompt), filename_prefix=job.filename_prefix))
    return g


# A slideshow rather than a film: 4 frames a second keeps a 15 second video light enough for a laptop's CPU
DEV_VIDEO_FPS = 4


def video(job: Job) -> Graph:
    """A silent slideshow with every reference photo, and the first frame of every reference clip, in its corner."""
    assert job.frames is not None
    width, height = job.size
    g = Graph()
    frames: Link = g.add("EmptyImage", width=width, height=height, batch_size=job.frames, color=0x202020)[0]
    smalls = [shrink(g, g.add("LoadImage", image=photo)[0], job.megapixels) for photo in job.files(MediaType.IMAGE)]
    for clip in job.files(MediaType.VIDEO):
        clip_frames = g.add("GetVideoComponents", video=g.add("LoadVideo", file=clip)[0])
        first = g.add("ImageFromBatch", image=clip_frames[0], batch_index=0, length=1)
        smalls.append(shrink(g, first[0], job.megapixels))
    for n, small in enumerate(smalls):
        frames = paste_small(g, frames, small, n)
    prompt = job.prompt_with(photo="<Picture {n}>", clip="<Video {n}>")
    made = g.add("CreateVideo", images=stamp(g, frames, job, prompt), fps=DEV_VIDEO_FPS)
    g.output(
        g.add("SaveVideo", video=made[0], filename_prefix=job.filename_prefix, format="mp4", **{"format.codec": "h264"})
    )
    return g


def video_seconds(work: Work) -> float:
    # As long as the real video of that length, whose frame rate is higher
    assert work.frames is not None
    return minimax_seconds(replace(work, frames=MINIMAX_FRAMES[work.frames // DEV_VIDEO_FPS]))


WORKFLOWS = [
    Workflow(
        id="dev-image",
        capabilities=frozenset({Capability.IMAGE_GENERATE}),
        model="dev",
        model_name="Dev stand-in",
        description="A tinted canvas with the prompt written on it",
        build=image,
        megapixels=IMAGE_MEGAPIXELS,
        # The real models' estimates, so Smart Queue orders the stand-ins as it would the real thing
        estimate=krea2_seconds,
    ),
    Workflow(
        id="dev-edit",
        capabilities=frozenset({Capability.IMAGE_EDIT}),
        model="dev",
        model_name="Dev stand-in",
        description="The first photo with the others pasted in its corner and the prompt written on it",
        build=edit,
        megapixels=IMAGE_MEGAPIXELS,
        accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 3),),
        estimate=klein_seconds,
    ),
    Workflow(
        id="dev-video",
        capabilities=frozenset({Capability.VIDEO_GENERATE, Capability.VIDEO_REFERENCE}),
        model="dev",
        model_name="Dev stand-in",
        description="A silent slideshow with the references in its corner and the prompt written on it",
        build=video,
        megapixels=VIDEO_MEGAPIXELS,
        multiple=32,
        accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 9), Accepts(InputRole.REFERENCE, MediaType.VIDEO, 3)),
        frames={seconds: seconds * DEV_VIDEO_FPS for seconds in (5, 10, 15)},
        estimate=video_seconds,
    ),
]
