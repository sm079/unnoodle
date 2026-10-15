"""Stand-ins for the real workflows that run on the dev ComfyUI without any models (see the README).

They take the same inputs and offer the same settings as the real ones, and use the dev node in
dev/comfyui/custom_nodes to take a few seconds, report progress, fail on demand ("#oom" in the prompt) and write the
prompt on the result, so the whole app can be tried on a laptop.
"""

from app.catalogues.real import IMAGE_MEGAPIXELS
from app.graph import Graph, Link
from app.models import Capability, InputRole, MediaType
from app.workflows import Accepts, Job, Workflow


def stamp(g: Graph, images: Link, job: Job, prompt: str) -> Link:
    """The dev node: steps through for a few seconds, then writes the prompt on the images."""
    return g.add("UnnoodleDevSteps", images=images, prompt=prompt, seed=job.seed, steps=12, step_seconds=0.25)[0]


def image(job: Job) -> Graph:
    assert job.size is not None
    width, height = job.size
    g = Graph()
    canvas = g.add("EmptyImage", width=width, height=height, batch_size=job.count, color=0x202020)
    g.output(g.add("SaveImage", images=stamp(g, canvas[0], job, job.prompt), filename_prefix=job.filename_prefix))
    return g


def edit(job: Job) -> Graph:
    """The first photo at the quality's size, with the others pasted small in its corner."""
    g = Graph()
    photos = job.files(MediaType.IMAGE)
    loaded = g.add("LoadImage", image=photos[0])
    scaled = g.add(
        "ImageScaleToTotalPixels",
        image=loaded[0],
        upscale_method="lanczos",
        megapixels=job.megapixels,
        resolution_steps=16,
    )
    picture = scaled[0]
    for n, photo in enumerate(photos[1:]):
        reference = g.add("LoadImage", image=photo)
        small = g.add(
            "ImageScaleToTotalPixels",
            image=reference[0],
            upscale_method="area",
            megapixels=max(job.megapixels / 25, 0.01),
            resolution_steps=1,
        )
        offset = 16 + 32 * n
        picture = g.add(
            "ImageCompositeMasked", destination=picture, source=small[0], x=offset, y=offset, resize_source=False
        )[0]
    # The prompt as the real edit model reads it, to show the rewriting
    prompt = job.prompt_with(photo="image {n}")
    g.output(g.add("SaveImage", images=stamp(g, picture, job, prompt), filename_prefix=job.filename_prefix))
    return g


WORKFLOWS = [
    Workflow(
        id="dev-image",
        capabilities=frozenset({Capability.IMAGE_GENERATE}),
        model="dev",
        model_name="Dev stand-in",
        description="A tinted canvas with the prompt written on it",
        build=image,
        megapixels=IMAGE_MEGAPIXELS,
        max_count=4,
    ),
    Workflow(
        id="dev-edit",
        capabilities=frozenset({Capability.IMAGE_EDIT}),
        model="dev",
        model_name="Dev stand-in",
        description="The photo with the others pasted in its corner and the prompt written on it",
        build=edit,
        megapixels=IMAGE_MEGAPIXELS,
        aspect_ratios=None,
        accepts=(Accepts(InputRole.EDIT_TARGET, MediaType.IMAGE, 1), Accepts(InputRole.REFERENCE, MediaType.IMAGE, 2)),
    ),
]
