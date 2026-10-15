"""The workflows that need models: Krea 2 Turbo makes pictures and FLUX.2 Klein 9B edits photos.

Each builder follows the graph its model was tested with in ComfyUI, sampler settings included. Only the parts a
request changes are worked out per request: the prompt, the seed, the size, and one image chain per attached photo.
Every node is part of ComfyUI itself, so a plain install with the models in place runs them.
"""

from app.graph import Graph, Link
from app.models import Capability, InputRole, MediaType, Quality
from app.workflows import Accepts, Job, Workflow

IMAGE_MEGAPIXELS = {Quality.LOW: 0.5, Quality.MEDIUM: 1.0, Quality.HIGH: 2.0}

# References only show the model what to copy, and every one adds to the work of each step, so they stay at about
# a megapixel whatever the quality
REFERENCE_MEGAPIXELS = 1.0


def krea2(job: Job) -> Graph:
    assert job.size is not None
    width, height = job.size
    g = Graph()
    model = g.add("UNETLoader", unet_name="krea2_turbo_fp8_scaled.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen3vl_4b_fp8_scaled.safetensors", type="krea2", device="default")
    vae = g.add("VAELoader", vae_name="qwen_image_vae.safetensors")
    positive = g.add("CLIPTextEncode", text=job.prompt, clip=clip[0])
    # Turbo runs at cfg 1, where the negative prompt does nothing
    negative = g.add("ConditioningZeroOut", conditioning=positive[0])
    latent = g.add("EmptyLatentImage", width=width, height=height, batch_size=job.count)
    samples = g.add(
        "KSampler",
        model=model[0],
        seed=job.seed,
        steps=8,
        cfg=1,
        sampler_name="euler",
        scheduler="simple",
        positive=positive[0],
        negative=negative[0],
        latent_image=latent[0],
        denoise=1,
    )
    images = g.add("VAEDecode", samples=samples[0], vae=vae[0])
    g.output(g.add("SaveImage", images=images[0], filename_prefix=job.filename_prefix))
    return g


def klein(job: Job) -> Graph:
    """An edit of the first photo, with the others as references. Each photo is encoded and attached to the
    prompt in turn, so the model knows them as image 1, image 2 and image 3; the result has the first one's shape."""
    g = Graph()
    model = g.add("UNETLoader", unet_name="flux-2-klein-9b-fp8.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen_3_8b_fp8mixed.safetensors", type="flux2", device="default")
    vae = g.add("VAELoader", vae_name="flux2-vae.safetensors")
    positive: Link = g.add("CLIPTextEncode", text=job.prompt_with(photo="image {n}"), clip=clip[0])[0]
    negative: Link = g.add("ConditioningZeroOut", conditioning=positive)[0]

    photos = job.files(MediaType.IMAGE)
    target: Link | None = None
    for n, photo in enumerate(photos):
        loaded = g.add("LoadImage", image=photo)
        scaled = g.add(
            "ImageScaleToTotalPixels",
            image=loaded[0],
            upscale_method="lanczos",
            megapixels=job.megapixels if n == 0 else min(job.megapixels, REFERENCE_MEGAPIXELS),
            resolution_steps=16,
        )
        latent = g.add("VAEEncode", pixels=scaled[0], vae=vae[0])
        positive = g.add("ReferenceLatent", conditioning=positive, latent=latent[0])[0]
        negative = g.add("ReferenceLatent", conditioning=negative, latent=latent[0])[0]
        target = target or scaled[0]
    assert target is not None, "an edit needs a photo"

    size = g.add("GetImageSize", image=target)
    latent = g.add("EmptyFlux2LatentImage", width=size[0], height=size[1], batch_size=job.count)
    sigmas = g.add("Flux2Scheduler", steps=4, width=size[0], height=size[1])
    guider = g.add("CFGGuider", model=model[0], positive=positive, negative=negative, cfg=1)
    noise = g.add("RandomNoise", noise_seed=job.seed)
    sampler = g.add("KSamplerSelect", sampler_name="euler")
    samples = g.add(
        "SamplerCustomAdvanced",
        noise=noise[0],
        guider=guider[0],
        sampler=sampler[0],
        sigmas=sigmas[0],
        latent_image=latent[0],
    )
    images = g.add("VAEDecode", samples=samples[0], vae=vae[0])
    g.output(g.add("SaveImage", images=images[0], filename_prefix=job.filename_prefix))
    return g


WORKFLOWS = [
    Workflow(
        id="krea2-turbo",
        capabilities=frozenset({Capability.IMAGE_GENERATE}),
        model="krea-2",
        model_name="Krea 2",
        description="Pictures from a description",
        build=krea2,
        megapixels=IMAGE_MEGAPIXELS,
        max_count=4,
    ),
    Workflow(
        id="flux2-klein-edit",
        capabilities=frozenset({Capability.IMAGE_EDIT}),
        model="flux-2-klein",
        model_name="FLUX.2 Klein",
        description="Changes a photo, optionally using up to two more",
        build=klein,
        megapixels=IMAGE_MEGAPIXELS,
        aspect_ratios=None,
        accepts=(Accepts(InputRole.EDIT_TARGET, MediaType.IMAGE, 1), Accepts(InputRole.REFERENCE, MediaType.IMAGE, 2)),
    ),
]
