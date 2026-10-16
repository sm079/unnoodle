"""Checks the real graphs against the pod's /object_info: node types, input names, and choice values."""

import pathlib
import sys

import httpx

# The repo root: dev/metrics/<run>/scripts/ is four levels down
REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "apps" / "api"))
from app.catalogues.real import WORKFLOWS  # noqa: E402
from app.models import InputRole, MediaType  # noqa: E402
from app.workflows import Job, JobInput  # noqa: E402

info = httpx.get("http://127.0.0.1:8288/object_info", timeout=60).json()
photos = tuple(JobInput(InputRole.REFERENCE, MediaType.IMAGE, f"unnoodle/p{n}.png") for n in range(3))
clips = tuple(JobInput(InputRole.REFERENCE, MediaType.VIDEO, f"unnoodle/c{n}.mp4") for n in range(2))
cases = {"krea2-turbo": (), "flux2-klein-edit": photos, "minimax-h3": photos + clips}

for w in WORKFLOWS:
    job = Job(prompt="@photo1 and @clip1", seed=1, megapixels=1, size=(1024, 1024), frames=124 if w.frames else None,
              inputs=cases[w.id], filename_prefix="unnoodle/x")
    graph = w.build(job).nodes
    problems = []
    for nid, node in graph.items():
        spec = info.get(node["class_type"])
        if spec is None:
            problems.append(f"{node['class_type']}: not installed")
            continue
        known = {**spec["input"].get("required", {}), **spec["input"].get("optional", {})}
        for key, value in node["inputs"].items():
            base = key.split(".")[0]
            if key not in known and base not in known:
                problems.append(f"{node['class_type']}.{key}: unknown input (has {sorted(known)})")
                continue
            kind = (known.get(key) or known[base])[0]
            if isinstance(kind, list) and not isinstance(value, list) and value not in kind:
                problems.append(f"{node['class_type']}.{key}={value!r}: not in {kind[:6]}")
            if kind == "COMBO":
                options = (known.get(key) or known[base])[1].get("options", [])
                if not isinstance(value, list) and options and value not in options and not str(value).startswith("unnoodle/"):
                    problems.append(f"{node['class_type']}.{key}={value!r}: not in {options[:6]}")
    print(w.id, "OK" if not problems else "")
    for p in problems:
        print("   ", p)
