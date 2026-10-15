"""Small video files for tests, made with ffmpeg's test pattern."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg isn't on the PATH")


def clip(seconds: float, size: tuple[int, int] = (320, 240), fps: int = 30) -> bytes:
    """An H.264 MP4 of ffmpeg's test pattern."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "clip.mp4"
        pattern = f"testsrc=duration={seconds}:size={size[0]}x{size[1]}:rate={fps}"
        command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        subprocess.run([*command, str(path)], check=True)
        return path.read_bytes()
