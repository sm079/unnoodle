"""The workflows that need models: Krea 2 Turbo makes pictures, FLUX.2 Klein 9B edits photos, and MiniMax H3 makes
videos with sound, from a prompt alone or from reference photos and clips.

Each builder follows the graph its model was tested with in ComfyUI, sampler settings included. Only the parts a
request changes are worked out per request: the prompt, the seed, the size, and one image chain per attached photo.
Every node is part of ComfyUI itself, so a plain install with the models in place runs them.
"""

from app.graph import Graph, Link
from app.models import Capability, InputRole, MediaType, Quality
from app.workflows import Accepts, Job, Workflow

IMAGE_MEGAPIXELS = {Quality.LOW: 0.5, Quality.MEDIUM: 1.0, Quality.HIGH: 2.0}
VIDEO_MEGAPIXELS = {Quality.LOW: 0.25, Quality.MEDIUM: 0.4, Quality.HIGH: 0.9}

# MiniMax H3 runs at 24 frames a second on a grid of 17k + 5 frames, and was trained on 124 to 362 of them
MINIMAX_FRAMES = {5: 124, 10: 243, 15: 362}

# References only show the model what to copy, and every one adds to the work of each step, so they stay at about
# a megapixel whatever the quality
REFERENCE_MEGAPIXELS = 1.0


def krea2(job: Job) -> Graph:
    width, height = job.size
    g = Graph()
    model = g.add("UNETLoader", unet_name="krea2_turbo_fp8_scaled.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen3vl_4b_fp8_scaled.safetensors", type="krea2", device="default")
    vae = g.add("VAELoader", vae_name="qwen_image_vae.safetensors")
    positive = g.add("CLIPTextEncode", text=job.prompt, clip=clip[0])
    # Turbo runs at cfg 1, where the negative prompt does nothing
    negative = g.add("ConditioningZeroOut", conditioning=positive[0])
    latent = g.add("EmptyLatentImage", width=width, height=height, batch_size=1)
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
    """A picture from one to three photos: a change to one, or a mix of several, as the prompt says. Each photo is
    encoded and attached to the prompt in turn, so the model knows them as image 1, image 2 and image 3."""
    width, height = job.size
    g = Graph()
    model = g.add("UNETLoader", unet_name="flux-2-klein-9b-fp8.safetensors", weight_dtype="default")
    clip = g.add("CLIPLoader", clip_name="qwen_3_8b_fp8mixed.safetensors", type="flux2", device="default")
    vae = g.add("VAELoader", vae_name="flux2-vae.safetensors")
    positive: Link = g.add("CLIPTextEncode", text=job.prompt_with(photo="image {n}"), clip=clip[0])[0]
    negative: Link = g.add("ConditioningZeroOut", conditioning=positive)[0]

    for photo in job.files(MediaType.IMAGE):
        loaded = g.add("LoadImage", image=photo)
        scaled = g.add(
            "ImageScaleToTotalPixels",
            image=loaded[0],
            upscale_method="lanczos",
            megapixels=REFERENCE_MEGAPIXELS,
            resolution_steps=16,
        )
        latent = g.add("VAEEncode", pixels=scaled[0], vae=vae[0])
        positive = g.add("ReferenceLatent", conditioning=positive, latent=latent[0])[0]
        negative = g.add("ReferenceLatent", conditioning=negative, latent=latent[0])[0]

    latent = g.add("EmptyFlux2LatentImage", width=width, height=height, batch_size=1)
    sigmas = g.add("Flux2Scheduler", steps=4, width=width, height=height)
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


def minimax_h3(job: Job) -> Graph:
    """A video with sound. Attached photos and clips are references the prompt can name ("the coat in @photo2"); with
    none it is text to video. Uploaded clips are already at 24 frames a second, which the model expects."""
    assert job.frames is not None
    width, height = job.size
    g = Graph()
    model = g.add("UNETLoader", unet_name="minimax_h3_ref2va_pruned_int8_convrot.safetensors", weight_dtype="default")
    turbo = g.add(
        "LoraLoaderModelOnly",
        model=model[0],
        lora_name="minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors",
        strength_model=1,
    )
    shifted = g.add("MiniMaxH3SigmaShift", model=turbo[0], shift_video=12, shift_audio=4)
    clip = g.add(
        "CLIPLoader", clip_name="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type="minimax", device="default"
    )
    vae = g.add("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors")
    audio_vae = g.add("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors")

    references: dict[str, Link] = {}
    for n, photo in enumerate(job.files(MediaType.IMAGE)):
        loaded = g.add("LoadImage", image=photo)
        # The node scales references down to the video's area; this only saves it work on large photos
        scaled = g.add(
            "ImageScaleToTotalPixels",
            image=loaded[0],
            upscale_method="lanczos",
            megapixels=REFERENCE_MEGAPIXELS,
            resolution_steps=1,
        )
        references[f"ref_images.ref_image_{n}"] = scaled[0]
    for n, clip_file in enumerate(job.files(MediaType.VIDEO)):
        loaded = g.add("LoadVideo", file=clip_file)
        frames = g.add("GetVideoComponents", video=loaded[0])
        references[f"ref_videos.ref_video_{n}"] = frames[0]

    conditioned = g.add(
        "MiniMaxH3ReferenceToVideo",
        clip=clip[0],
        vae=vae[0],
        audio_vae=audio_vae[0],
        prompt=job.prompt_with(photo="<Picture {n}>", clip="<Video {n}>"),
        width=width,
        height=height,
        length=job.frames,
        ref_image_size="match",
        **references,
    )
    noise = g.add("RandomNoise", noise_seed=job.seed)
    guider = g.add("BasicGuider", model=shifted[0], conditioning=conditioned[0])
    sampler = g.add("KSamplerSelect", sampler_name="euler")
    sigmas = g.add("BasicScheduler", model=shifted[0], scheduler="beta", steps=8, denoise=1)
    samples = g.add(
        "SamplerCustomAdvanced",
        noise=noise[0],
        guider=guider[0],
        sampler=sampler[0],
        sigmas=sigmas[0],
        latent_image=conditioned[1],
    )
    frames = g.add("VAEDecode", samples=samples[0], vae=vae[0])
    sound = g.add("VAEDecodeAudio", samples=samples[0], vae=audio_vae[0])
    video = g.add("CreateVideo", images=frames[0], audio=sound[0], fps=24)
    # H.264 in MP4 plays on every phone
    g.output(
        g.add(
            "SaveVideo",
            video=video[0],
            filename_prefix=job.filename_prefix,
            format="mp4",
            **{"format.codec": "h264"},
        )
    )
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
    ),
    Workflow(
        id="flux2-klein-edit",
        capabilities=frozenset({Capability.IMAGE_EDIT}),
        model="flux-2-klein",
        model_name="FLUX.2 Klein",
        description="Changes or combines up to three photos",
        build=klein,
        megapixels=IMAGE_MEGAPIXELS,
        accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 3),),
    ),
    Workflow(
        id="minimax-h3",
        capabilities=frozenset({Capability.VIDEO_GENERATE, Capability.VIDEO_REFERENCE}),
        model="minimax-h3",
        model_name="MiniMax H3",
        description="Video with sound, from a description and any photos or clips to follow",
        build=minimax_h3,
        megapixels=VIDEO_MEGAPIXELS,
        multiple=32,
        accepts=(Accepts(InputRole.REFERENCE, MediaType.IMAGE, 9), Accepts(InputRole.REFERENCE, MediaType.VIDEO, 3)),
        frames=MINIMAX_FRAMES,
        sound=True,
    ),
]
