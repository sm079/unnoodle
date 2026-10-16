"""RunPod test driver. python driver.py <step> [...]

Talks to the local API (which sends work to the pod through the tunnel), keeps names -> ids in state.json and
appends one result line per generation to results.jsonl.
"""

import json
import pathlib
import subprocess
import sys
import time

import httpx

# The repo root: dev/metrics/<run>/scripts/ is four levels down
REPO = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "apps" / "api"))
from app.catalogues.real import PIPELINES  # noqa: E402
from app.models import Quality  # noqa: E402
from app.pipelines import ratio_of  # noqa: E402

API = "http://127.0.0.1:8000"
RENDERER = "http://127.0.0.1:8288"
HERE = pathlib.Path(__file__).parent
STATE = HERE / "state.json"
RESULTS = HERE / "results.jsonl"
INPUTS = HERE / "inputs"
MEDIA = REPO / "apps" / "api" / "media"
WF = {w.id: w for w in PIPELINES}

api = httpx.Client(base_url=API, timeout=300)


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {"assets": {}, "gens": {}}


S = load()


def save():
    STATE.write_text(json.dumps(S, indent=1))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def upload(name, path):
    with open(path, "rb") as f:
        r = api.post("/assets", files={"file": (pathlib.Path(path).name, f)})
    if r.status_code != 201:
        log(f"upload {name}: {r.status_code} {r.text}")
        return None
    a = r.json()
    S["assets"][name] = a
    save()
    log(f"upload {name}: {a['media_type']} {a['width']}x{a['height']} dur={a['duration_s']}")
    return a


def asset(name):
    """An uploaded asset, or the first output of a generation, by name."""
    if name in S["assets"]:
        return S["assets"][name]
    return S["gens"][name]["outputs"][0]


def gen(name, media_type, prompt, inputs=(), quality="medium", aspect=None, duration=None, count=1, seed=None,
        project=None):
    body = {
        "media_type": media_type,
        "prompt": prompt,
        "inputs": [{"asset_id": asset(i)["id"], "role": "reference"} for i in inputs],
        "params": {"quality": quality, "aspect_ratio": aspect, "duration_s": duration, "count": count, "seed": seed},
        "project_id": project,
    }
    r = api.post("/generations", json=body)
    if r.status_code != 201:
        log(f"{name}: refused {r.status_code}: {r.json().get('detail')}")
        return []
    gs = r.json()
    names = [name] if len(gs) == 1 else [f"{name}.{n}" for n in range(len(gs))]
    for n, g in zip(names, gs):
        S["gens"][n] = g | {"_inputs": list(inputs)}
    save()
    log(f"{name}: queued {len(gs)} ({gs[0]['pipeline_id']}, seeds {[g['params']['seed'] for g in gs]})")
    return names


def expected_size(g, inputs):
    wf = WF[g["pipeline_id"]]
    p = g["params"]
    ratio = ratio_of(p["aspect_ratio"]) if p["aspect_ratio"] else (asset(inputs[0])["width"], asset(inputs[0])["height"])
    return wf.size(Quality(p["quality"]), ratio)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True).stdout
    info = json.loads(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    res = {"codec": v.get("codec_name"), "fps": v.get("r_frame_rate"), "frames": v.get("nb_frames"),
           "dur": round(float(info["format"]["duration"]), 2), "audio": a["codec_name"] if a else None}
    if a:
        vol = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        mean = [l.split(":")[1].strip() for l in vol.splitlines() if "mean_volume" in l]
        res["mean_volume"] = mean[0] if mean else None
    return res


def media_path(url):
    return MEDIA / url.split("/media/", 1)[1]


def wait(names, interrupt=None, poll=0.5):
    """Follows generations to the end. interrupt=(name, after_s): POST /interrupt to the renderer that long after it
    starts running."""
    pending = list(names)
    prog = {n: [] for n in names}
    running_since = {}
    while pending:
        for n in list(pending):
            g = api.get(f"/generations/{S['gens'][n]['id']}").json()
            if g["status"] == "running":
                running_since.setdefault(n, time.monotonic())
                if g["progress"] is not None and (not prog[n] or prog[n][-1][1] != round(g["progress"], 2)):
                    prog[n].append((round(time.monotonic() - running_since[n], 1), round(g["progress"], 2)))
                if interrupt and interrupt[0] == n and time.monotonic() - running_since[n] >= interrupt[1]:
                    httpx.post(f"{RENDERER}/interrupt", json={}, timeout=10)
                    log(f"{n}: sent /interrupt")
                    interrupt = None
            if g["status"] in ("done", "failed"):
                pending.remove(n)
                S["gens"][n] = g | {"_inputs": S["gens"][n]["_inputs"]}
                save()
                report(n, g, prog[n])
        time.sleep(poll)


def secs(a, b):
    from datetime import datetime
    return None if not (a and b) else round((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds(), 1)


def report(n, g, prog):
    r = {"name": n, "status": g["status"], "error": g["error"], "pipeline": g["pipeline_id"],
         "quality": g["params"]["quality"], "shape": g["params"]["aspect_ratio"] or "same as first",
         "duration_s": g["params"]["duration_s"], "seed": g["params"]["seed"], "inputs": S["gens"][n]["_inputs"],
         "waited_s": secs(g["created_at"], g["started_at"]), "ran_s": secs(g["started_at"], g["finished_at"]),
         "progress_restarts": sum(1 for a, b in zip(prog, prog[1:]) if b[1] < a[1]),
         # (seconds since it started running, progress the API reported)
         "progress_samples": prog}
    if g["status"] == "done":
        o = g["outputs"][0]
        exp = expected_size(g, S["gens"][n]["_inputs"])
        r |= {"size": f"{o['width']}x{o['height']}", "expected": f"{exp[0]}x{exp[1]}",
              "size_ok": (o["width"], o["height"]) == exp, "poster": o["thumbnail_url"] != o["url"]}
        if o["media_type"] == "video":
            r |= probe(media_path(o["url"]))
    with RESULTS.open("a") as f:
        f.write(json.dumps(r) + "\n")
    log(json.dumps(r))


def project(name):
    if name not in S.get("projects", {}):
        S.setdefault("projects", {})[name] = api.post("/projects", json={"name": name}).json()["id"]
        save()
    return S["projects"][name]


# ---- steps ------------------------------------------------------------------------------------------------------


def step_refusals():
    for n in range(1, 5):
        if f"sq{n}" not in S["assets"]:
            upload(f"sq{n}", INPUTS / f"sq{n}.png")
    upload("short", INPUTS / "short.mp4")  # expect 422
    upload("text", INPUTS / "notes.txt")  # expect 415
    if "clipA" not in S["assets"]:
        upload("clipA", INPUTS / "clipA.mp4")
    sq = ["sq1", "sq2", "sq3", "sq4"]
    gen("R-klein-4-photos", "image", "x @photo1", sq)
    gen("R-clip-in-image-mode", "image", "x", ["clipA"])
    gen("R-video-10-photos", "video", "x", (sq * 3)[:10], duration=5)
    gen("R-video-4-clips", "video", "x", ["clipA"] * 4, duration=5)
    gen("R-count-5", "image", "x", aspect="1:1", count=5)
    gen("R-length-7s", "video", "x", aspect="16:9", duration=7)
    gen("R-video-no-length", "video", "x", aspect="16:9")
    gen("R-same-as-nothing", "image", "x")
    gen("R-image-with-length", "image", "x", aspect="1:1", duration=5)


def step_krea():
    p = project("RunPod test")
    first = gen("K0-interrupt", "image", "a lighthouse on a cliff at dusk", quality="medium", aspect="1:1")
    k1 = gen("K1", "image", "a red vintage bicycle leaning on a pale blue wall, soft morning light, photo",
             quality="low", aspect="3:4", count=2, seed=100)
    k2 = gen("K2", "image", "portrait photo of a young woman in a yellow raincoat, plain grey studio background, "
             "looking at the camera", quality="high", aspect="2:3", project=p)
    k3 = gen("K3", "image", "a white ceramic teapot painted with a blue fish, product photo on a white table",
             quality="medium", aspect="1:1")
    k4 = gen("K4", "image", "a busy night market street in Kathmandu in the rain, lanterns, people with umbrellas",
             quality="medium", aspect="9:16")
    # The first run loads the models, so the interrupt lands well inside it
    wait(first + k1 + k2 + k3 + k4, interrupt=("K0-interrupt", 3))


def step_prep():
    """Uploads that go through the app's own handling: K2 as JPEG, K3 as WebP, and a phone-like clip made from K4
    (portrait 1080x1920, 30 fps, 6 s, with sound) that the upload should bring to 24 fps, short edge 768, silent."""
    k2, k3, k4 = (media_path(asset(n)["url"]) for n in ("K2", "K3", "K4"))
    run = lambda *a: subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, a)], check=True)
    run("-i", k2, "-q:v", "3", INPUTS / "woman.jpg")
    run("-i", k3, "-quality", "85", INPUTS / "teapot.webp")
    run("-loop", "1", "-i", k4, "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-t", "6",
        "-vf", "scale=1080:1920,zoompan=z='min(zoom+0.0015,1.3)':d=180:s=1080x1920:fps=30,format=yuv420p",
        "-r", "30", "-c:v", "libx264", "-c:a", "aac", "-shortest", INPUTS / "market.mp4")
    upload("woman.jpg", INPUTS / "woman.jpg")
    upload("teapot.webp", INPUTS / "teapot.webp")
    upload("market.mp4", INPUTS / "market.mp4")
    log("stored clip:", probe(media_path(asset("market.mp4")["url"])))


def step_klein():
    e1 = gen("E1", "image", "@photo1 wears a black leather jacket instead of the raincoat, same pose and background",
             ["K2"], quality="medium")
    e2 = gen("E2", "image", "@photo1 holds the teapot from @photo2 in both hands, in a sunny kitchen",
             ["woman.jpg", "teapot.webp"], quality="low", aspect="4:3")
    e3 = gen("E3", "image", "@photo1 rides the bicycle from @photo2 down a quiet street, the teapot from @photo3 in "
             "the front basket", ["K2", "K1.0", "K3"], quality="high", count=2)
    wait(e1 + e2 + e3)


def step_v1():
    v1 = gen("V1", "video", "a street musician plays an acoustic guitar under a lamp on a rainy night and sings "
             "softly, rain patters on the pavement", quality="low", aspect="16:9", duration=5)
    wait(v1)


def step_v23():
    v2 = gen("V2", "video", "@photo1 pours tea from the teapot in @photo2 into a cup, then smiles and says "
             "\"cheers\" to the camera", ["E1", "K3"], quality="low", duration=5)
    v3 = gen("V3", "video", "the camera moves through the market street from @clip1; the musician from @clip2 rides "
             "the bicycle from @photo1 through the crowd, ringing its bell", ["market.mp4", "V1", "K1.0"],
             quality="medium", duration=10)
    wait(v2 + v3)


def step_wait():
    wait([n for n in sys.argv[2:]])


def step_history():
    """What the renderer actually ran: each prompt's text as the model got it, its references, status and run time."""
    hist = httpx.get(f"{RENDERER}/history", params={"max_items": 100}, timeout=30).json()
    for pid, h in hist.items():
        nodes = h["prompt"][2]
        texts = [n["inputs"].get("text") or n["inputs"].get("prompt") for n in nodes.values()
                 if n["class_type"] in ("CLIPTextEncode", "MiniMaxH3ReferenceToVideo")]
        refs = sorted(k for n in nodes.values() for k in n["inputs"] if k.startswith("ref_"))
        loads = [n["class_type"] for n in nodes.values() if n["class_type"] in ("LoadImage", "LoadVideo")]
        msgs = h.get("status", {}).get("messages", [])
        t = {m[0]: m[1].get("timestamp") for m in msgs}
        start, end = t.get("execution_start"), t.get("execution_success") or t.get("execution_error") or \
            t.get("execution_interrupted")
        dur = round((end - start) / 1000, 1) if start and end else None
        print(pid[:8], h.get("status", {}).get("status_str"), f"{dur}s", loads, refs, "|", texts[0][:140] if texts else "")


if __name__ == "__main__":
    globals()[f"step_{sys.argv[1]}"]()
