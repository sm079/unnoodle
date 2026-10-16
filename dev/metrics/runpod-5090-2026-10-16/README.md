# Real runs on an RTX 5090, 16 Oct 2026

The first end-to-end run of the real catalogue (Krea 2, FLUX.2 Klein 9B, MiniMax H3) on a RunPod RTX 5090 (32 GB,
secure cloud, renderer v0.39.1), driven through the API with the worker reaching the renderer over an SSH tunnel. Kept as
real numbers to pace simulated generations by (durations, progress, queue waits) and to size reference clips.

- `runs.json`: one record per generation: what was asked (pipeline, quality, shape, length, photos and clips), the
  output size, queue wait, time in the app, time on the GPU, sampler steps (seconds to the first step, which includes
  loading and set-up, and seconds per step after it), and transfer overhead (app time minus GPU time; mostly the
  tunnel, which was slow on this connection). Runs on the pod with no generation (the reference clip sweep, and the
  original of a run resubmitted after the tunnel dropped) are listed separately.
- `raw/sweep.jsonl`: MiniMax H3 with one reference clip at 0.25, 0.5 and 1 MP (and 0.4 MP over 10 s), stopped after
  three steps. Step time follows the total latent tokens of the output and the clips, and grows faster than linearly.
- `raw/`: the renderer's history from the pod and the test driver's own results. The pod and worker logs that `runs.json`
  was parsed from are `*.log`, which git ignores.
- `scripts/`: the test driver (`driver.py`), the clip sweep, the node spec check against `/object_info`, and the collector
  that wrote `runs.json`. They expect the tunnel on `127.0.0.1:8288` and the API on `127.0.0.1:8000`.

Not covered: high quality video, 15 second video, running out of memory.
