"""Collects real run metrics from this session into OUT: the raw logs, plus runs.json with one record per generation.

python collect.py <out_dir> <since ISO time>

Sources: the app's database (what was asked, when it was queued, claimed and finished, sizes), ComfyUI's /history on
the pod (when each prompt ran there), the pod's ComfyUI log (model loads, sampler steps and speed), the driver's
progress samples, and the worker log.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

# The repo root: dev/metrics/<run>/scripts/ is four levels down
REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "apps" / "api"))
from app.db import make_engine  # noqa: E402
from app.models import Generation  # noqa: E402
from app.settings import Settings  # noqa: E402

OUT = pathlib.Path(sys.argv[1])
SINCE = datetime.fromisoformat(sys.argv[2])
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
HERE = pathlib.Path(__file__).parent
MEDIA = REPO / "apps" / "api" / "media"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

# ---- raw sources ----
history = httpx.get("http://127.0.0.1:8288/history", params={"max_items": 500}, timeout=60).json()
(RAW / "comfy-history.json").write_text(json.dumps(history, indent=1))
log = subprocess.run(["python", "rp.py", "ssh", "cat /dev/shm/comfy/comfyui.log"], cwd=os.environ.get("RUNPOD_HELPER", "../runpod-helper"),
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
log = ANSI.sub("", log)
(RAW / "pod-comfyui.log").write_text(log, encoding="utf-8")
serve = pathlib.Path(os.environ["TEMP"], "unnoodle-serve.log").read_text(encoding="utf-8", errors="replace")
(RAW / "worker.log").write_text("\n".join(l for l in serve.splitlines() if l.startswith("worker")), encoding="utf-8")
for name in ("results.jsonl", "state.json", "sweep.jsonl"):
    if (HERE / name).exists():
        (RAW / name).write_text((HERE / name).read_text())

# ---- the pod log, one segment per executed prompt (ComfyUI runs one at a time and closes each with this line) ----
BAR = re.compile(r"(\d+)/(\d+) \[(\d+):(\d+)<[^,\]]*(?:, *([\d.]+)(s/it|it/s))?")
LOADED = re.compile(r"Model (\w+) prepared for dynamic VRAM loading\. (\d+)MB Staged|loaded (completely|partially)[^\n]*")
segments, current = [], []
for line in log.splitlines():
    current.append(line)
    if m := re.search(r"Prompt executed in ([\d.]+) seconds", line):
        segments.append({"executed_s": float(m.group(1)), "lines": current})
        current = []


def bars(lines):
    """Each sampler progress bar: steps, seconds to the first step (model set-up included), total seconds, s/step."""
    out = []
    for line in lines:
        for part in line.split("\r"):
            for m in BAR.finditer(part):
                n, total, mm, ss, rate, unit = m.groups()
                n, total, elapsed = int(n), int(total), int(mm) * 60 + int(ss)
                if n == 0 and (not out or out[-1].get("done")):
                    out.append({"steps": total})
                if not out:
                    continue
                bar = out[-1]
                if n == 1 and "first_step_s" not in bar:
                    bar["first_step_s"] = elapsed
                if n == total and not bar.get("done"):
                    bar |= {"done": True, "total_s": elapsed}
                    if rate:
                        bar["s_per_step"] = float(rate) if unit == "s/it" else round(1 / float(rate), 3)
    return out


# Prompts in the order they ran on the pod, to line up with the segments
def started(h):
    msgs = {m[0]: m[1].get("timestamp") for m in h.get("status", {}).get("messages", [])}
    return msgs


ran = sorted(history.items(), key=lambda kv: started(kv[1]).get("execution_start") or 0)
pod = {}
for (pid, h), seg in zip(ran, segments[-len(ran):] if len(segments) >= len(ran) else segments):
    msgs = started(h)
    end = msgs.get("execution_success") or msgs.get("execution_error") or msgs.get("execution_interrupted")
    cached = [m[1].get("nodes", []) for m in h["status"]["messages"] if m[0] == "execution_cached"]
    pod[pid] = {
        "status": h["status"]["status_str"],
        "pod_start": msgs.get("execution_start"),
        "pod_exec_s": round((end - msgs["execution_start"]) / 1000, 2) if end and msgs.get("execution_start") else None,
        "log_executed_s": seg["executed_s"],
        "cached_nodes": len(cached[0]) if cached else 0,
        "sampler": bars(seg["lines"]),
        "model_loads": [m.group(0)[:120] for l in seg["lines"] for m in [LOADED.search(l)] if m],
    }

# ---- the app's side ----
results = {}
if (HERE / "results.jsonl").exists():
    for line in (HERE / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        results[r["name"]] = r
state = json.loads((HERE / "state.json").read_text())
names = {g["id"]: n for n, g in state["gens"].items()}

engine = make_engine(Settings().database_url)
runs = []
with Session(engine) as session:
    for g in session.scalars(select(Generation).where(Generation.created_at >= SINCE).order_by(Generation.created_at)):
        kinds = [i.asset.media_type.value for i in g.inputs]
        out = g.outputs[0] if g.outputs else None
        app_run_s = (g.finished_at - g.started_at).total_seconds() if g.finished_at and g.started_at else None
        p = pod.get(g.comfy_prompt_id or "", {})
        name = names.get(str(g.id))
        runs.append({
            "name": name,
            "workflow": g.workflow_id,
            "status": g.status.value,
            "error": g.error,
            "quality": g.quality.value,
            "shape": g.aspect_ratio or "same as first",
            "duration_s": g.duration_s,
            "photos": kinds.count("image"),
            "clips": kinds.count("video"),
            "input_bytes": sum((MEDIA / i.asset.storage_key).stat().st_size for i in g.inputs),
            "input_sizes": [f"{i.asset.width}x{i.asset.height}" + (f"/{i.asset.duration_s}s" if i.asset.duration_s else "")
                            for i in g.inputs],
            "output": f"{out.width}x{out.height}" if out else None,
            "output_bytes": (MEDIA / out.storage_key).stat().st_size if out else None,
            "attempts": g.attempts,
            "created_at": g.created_at.isoformat(),
            "queue_wait_s": round((g.started_at - g.created_at).total_seconds(), 2) if g.started_at else None,
            "app_run_s": round(app_run_s, 2) if app_run_s else None,
            **{k: v for k, v in p.items()},
            "transfer_overhead_s": round(app_run_s - p["pod_exec_s"], 2) if app_run_s and p.get("pod_exec_s") is not None
            else None,
            "progress_samples": results.get(name, {}).get("progress_samples"),
        })
unmatched = {pid: v for pid, v in pod.items() if pid not in {r.get("comfy_prompt_id") for r in runs}}
matched_ids = set()
with Session(engine) as session:
    matched_ids = {g.comfy_prompt_id for g in session.scalars(select(Generation).where(Generation.created_at >= SINCE))}
orphans = {pid: v for pid, v in pod.items() if pid not in matched_ids}

summary = {
    "setup": {
        "gpu": "RTX 5090 32 GB (RunPod secure cloud, $1.19/h), 108 GB container RAM",
        "comfyui": "v0.39.1",
        "transport": "SSH tunnel from the laptop to the pod; inputs uploaded and outputs downloaded through it",
        "notes": "transfer_overhead_s is app_run_s minus the time ComfyUI spent; most of it is the tunnel (~0.5-0.7 MB/s)",
    },
    "runs": runs,
    "pod_runs_without_a_generation": orphans,
}
(OUT / "runs.json").write_text(json.dumps(summary, indent=1, default=str))
print(f"{len(runs)} generations, {len(pod)} pod runs ({len(orphans)} unmatched), {len(segments)} log segments")
for r in runs:
    s = r.get("sampler") or []
    print(f"{(r['name'] or '?'):18} {r['workflow']:17} {r['status']:6} {r['quality']:6} {str(r['duration_s']):5} "
          f"p{r['photos']}c{r['clips']} wait={r['queue_wait_s']} app={r['app_run_s']} pod={r.get('pod_exec_s')} "
          f"xfer={r.get('transfer_overhead_s')} steps={[(b.get('steps'), b.get('first_step_s'), b.get('s_per_step')) for b in s]}")
