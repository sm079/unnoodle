"""A development-only renderer node for running unnoodle's fake pipelines.

Core image nodes finish in milliseconds and report no progress, so on their own they can't exercise a generation's
running and failed states. This node waits out a set-up time without reporting anything, as a model loading does, then
works through timed steps, reporting each one as progress, and fails like an
out-of-memory GPU when the prompt contains FAIL_MARKER. It also tints every image by the seed and writes the prompt
on it, so each output visibly matches the request that made it.

The renderer loads it only when started with `--base-directory dev/renderer`; it is never installed anywhere else.
"""

import colorsys
import textwrap
import time
from typing import override

import comfy.model_management
import comfy.utils
import numpy as np
import torch
from comfy_api.latest import ComfyExtension, io
from PIL import Image, ImageDraw, ImageFont

FAIL_MARKER = "#oom"
TINT_STRENGTH = 0.35


class DevSteps(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UnnoodleDevSteps",
            display_name="Dev steps (unnoodle)",
            category="unnoodle/dev",
            description=f"Stands in for a model: reports progress per step, and fails if the prompt has {FAIL_MARKER}.",
            inputs=[
                io.Image.Input("images"),
                io.String.Input("prompt", multiline=True, default=""),
                io.Int.Input("seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF),
                io.Int.Input("steps", default=8, min=1, max=1000),
                io.Float.Input("step_seconds", default=0.25, min=0.0, max=600.0, step=0.05),
                io.Float.Input("setup_seconds", default=0.0, min=0.0, max=3600.0, step=0.5),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(
        cls, images: torch.Tensor, prompt: str, seed: int, steps: int, step_seconds: float, setup_seconds: float
    ) -> io.NodeOutput:
        wait(setup_seconds)
        bar = comfy.utils.ProgressBar(steps)
        for step in range(1, steps + 1):
            wait(step_seconds)
            if FAIL_MARKER in prompt and step > steps // 2:
                raise torch.cuda.OutOfMemoryError(f"CUDA out of memory (simulated: the prompt contains {FAIL_MARKER})")
            bar.update(1)
        return io.NodeOutput(stamp(images, prompt, seed))


def wait(seconds: float) -> None:
    # In short sleeps, so POST /interrupt can cancel a run part-way, as it does a sampler
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        comfy.model_management.throw_exception_if_processing_interrupted()
        time.sleep(min(left, 0.25))
    comfy.model_management.throw_exception_if_processing_interrupted()


def stamp(images: torch.Tensor, prompt: str, seed: int) -> torch.Tensor:
    """Tints a batch of images (B, H, W, C in 0..1) by the seed and captions each with the prompt."""
    tint = torch.tensor(seed_colour(seed), dtype=images.dtype, device=images.device)
    tinted = images * (1 - TINT_STRENGTH) + tint * TINT_STRENGTH
    total = tinted.shape[0]
    frames = []
    for index, frame in enumerate(tinted):
        picture = Image.fromarray((frame.cpu().numpy() * 255).round().astype(np.uint8))
        caption(picture, prompt, f"seed {seed} · {index + 1}/{total}")
        frames.append(torch.from_numpy(np.asarray(picture).astype(np.float32) / 255))
    return torch.stack(frames).to(images.device)


def seed_colour(seed: int) -> tuple[float, float, float]:
    # Golden-ratio steps through the hue circle keep nearby seeds far apart in colour
    return colorsys.hsv_to_rgb((seed * 0.618033988749895) % 1, 0.65, 0.9)


def caption(picture: Image.Image, prompt: str, label: str) -> None:
    width, height = picture.size
    size = max(12, height // 24)
    font = ImageFont.load_default(size=size)
    lines = textwrap.wrap(prompt, max(10, int(width / (size * 0.55))))[:4] or ["(no prompt)"]
    lines.append(label)
    line_height = round(size * 1.3)
    top = height - line_height * len(lines) - size
    draw = ImageDraw.Draw(picture, "RGBA")
    draw.rectangle((0, top, width, height), fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        draw.text((size // 2, top + size // 2 + i * line_height), line, font=font, fill=(255, 255, 255, 255))


class DevExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [DevSteps]


async def comfy_entrypoint() -> DevExtension:
    return DevExtension()
