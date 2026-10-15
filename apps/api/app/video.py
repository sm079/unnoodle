"""Video files, through ffmpeg: what they hold, a still for grids, and cutting a clip down to what a model uses.

ffmpeg and ffprobe have to be on the PATH. Only videos need them; images never do.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Reference clips are cut to what MiniMax H3 uses of them: up to 15 seconds at 24 frames a second, on a canvas whose
# short edge is 768 pixels. Anything beyond that would only cost upload time and memory on the GPU machine.
CLIP_FPS = 24
CLIP_SHORT_EDGE = 768
SHORTEST_CLIP_S = 2.0
LONGEST_CLIP_S = 15.0
# What phones record and browsers make, as ffprobe names the containers. ffprobe also reads still images (a GIF is
# a one-frame "video"), which aren't clips.
CLIP_CONTAINERS = {"mov,mp4,m4a,3gp,3g2,mj2", "matroska,webm"}


class VideoError(Exception):
    """A file ffmpeg can't read as a video."""


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration_s: float
    container: str


def probe(path: Path) -> VideoInfo:
    output = run(
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration,format_name",
        "-of", "json",
        str(path),
    )  # fmt: skip
    try:
        found = json.loads(output)
        stream = found["streams"][0]
        container = found["format"]
        return VideoInfo(
            int(stream["width"]), int(stream["height"]), float(container["duration"]), container["format_name"]
        )
    except (KeyError, IndexError, ValueError) as error:
        raise VideoError(f"{path.name} has no video stream") from error


def cut_clip(source: Path, target: Path) -> None:
    """Writes the first LONGEST_CLIP_S of a clip to target as H.264 at CLIP_FPS, its short edge at most
    CLIP_SHORT_EDGE (never enlarged) and without sound. Phone clips come out upright, as they were filmed."""
    # Keeps the shape; width and height stay even, which H.264 needs
    edge = f"trunc(min({CLIP_SHORT_EDGE},{{}})/2)*2"
    scale = f"scale='if(lt(iw,ih),{edge.format('iw')},-2)':'if(lt(iw,ih),-2,{edge.format('ih')})'"
    run(
        "ffmpeg",
        "-v", "error", "-y",
        "-i", str(source),
        "-t", str(LONGEST_CLIP_S),
        "-vf", f"fps={CLIP_FPS},{scale}",
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(target),
    )  # fmt: skip


def poster(source: Path, target: Path) -> None:
    """The first frame as a JPEG, for grids and attachment chips."""
    run("ffmpeg", "-v", "error", "-y", "-i", str(source), "-frames:v", "1", "-q:v", "3", str(target))


def run(*command: str) -> str:
    try:
        done = subprocess.run(command, capture_output=True, check=True, text=True, timeout=120)
    except subprocess.CalledProcessError as error:
        raise VideoError(error.stderr.strip() or f"{command[0]} failed") from error
    return done.stdout
