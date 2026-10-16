"""How a reference clip's size and length change MiniMax H3's speed.

Builds the app's own MiniMax graph with one reference clip at several sizes, runs it on the pod, times the sampler's
steps from the renderer's progress events, and interrupts after STEPS steps (the rate is steady after the first).
python sweep.py  -> appends to sweep.jsonl
"""

import json
import pathlib
import subprocess
import sys
import time
import uuid

import httpx

# The repo root: dev/metrics/<run>/scripts/ is four levels down
REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "apps" / "api"))
from app.catalogues.real import MINIMAX_FRAMES, minimax_h3  # noqa: E402
from app.models import InputRole, MediaType  # noqa: E402
from app.pipelines import Job, JobInput  # noqa: E402
from app.worker.renderer import RendererClient, RendererFailed  # noqa: E402

C = "http://127.0.0.1:8288"
HERE = pathlib.Path(__file__).parent
SRC = HERE / "inputs" / "market15.mp4"
OUT = HERE / "sweep.jsonl"
STEPS = 3
PROMPT = "the camera moves through the market street from @clip1, people walk past with umbrellas, rain falls"

# (name, output size, output seconds, clip size, clip seconds)
RUNS = [
    ("clip0.25mp-5s", (384, 672), 5, (384, 672), 6),
    ("clip0.5mp-5s", (384, 672), 5, (544, 960), 6),
    ("clip1.0mp-5s", (384, 672), 5, (768, 1344), 6),
    ("clip0.4mp-10s", (384, 672), 10, (480, 864), 11),
]


def latent_t(frames):
    return 2 if frames <= 5 else ((frames - 5) // 17) * 5 + 2


def tokens(size, frames):
    return latent_t(frames) * (size[0] // 16) * (size[1] // 16)


def make_clip(size, seconds):
    path = HERE / "inputs" / f"sweep-{size[0]}x{size[1]}-{seconds}s.mp4"
    if not path.exists():
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(SRC), "-t", str(seconds),
                        "-vf", f"fps=24,scale={size[0]}:{size[1]}", "-an", "-c:v", "libx264", "-crf", "20",
                        str(path)], check=True)
    return path


renderer = RendererClient(C)
for name, out_size, out_s, clip_size, clip_s in RUNS:
    clip = make_clip(clip_size, clip_s)
    t0 = time.monotonic()
    stored = renderer.upload(clip.read_bytes(), clip.name)
    upload_s = time.monotonic() - t0
    frames = MINIMAX_FRAMES[out_s]
    job = Job(prompt=PROMPT, seed=7, megapixels=0, size=out_size, frames=frames,
              inputs=(JobInput(InputRole.REFERENCE, MediaType.VIDEO, stored),), filename_prefix="unnoodle/sweep")
    graph = minimax_h3(job)
    events = []
    start = time.monotonic()

    def progress(fraction):
        events.append((round(time.monotonic() - start, 2), round(fraction, 3)))
        if round(fraction * 8) >= STEPS and abs(fraction * 8 - round(fraction * 8)) < 1e-6:
            httpx.post(f"{C}/interrupt", json={}, timeout=10)

    try:
        renderer.run(graph.nodes, str(uuid.uuid4()), graph.output_node, progress, lambda: None)
    except RendererFailed as error:
        if "stopped" not in str(error):
            print(name, "failed:", error)
    steps = [t for t, f in events if abs(f * 8 - round(f * 8)) < 1e-6 and f > 0]
    per_step = [round(b - a, 2) for a, b in zip(steps, steps[1:])]
    ref_frames = min(clip_s * 24, frames)
    row = {
        "name": name, "output": f"{out_size[0]}x{out_size[1]}", "output_frames": frames,
        "clip": f"{clip_size[0]}x{clip_size[1]}", "clip_mp": round(clip_size[0] * clip_size[1] / 2**20, 2),
        "clip_frames_used": ref_frames,
        "output_tokens": tokens(out_size, frames), "clip_tokens": tokens(clip_size, ref_frames),
        "upload_s": round(upload_s, 1), "first_step_s": steps[0] if steps else None, "s_per_step": per_step,
        "events": events,
    }
    with OUT.open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps({k: v for k, v in row.items() if k != "events"}), flush=True)
