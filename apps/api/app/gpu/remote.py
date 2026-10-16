"""Reaching a pod over SSH: running the scripts in remote/ on it, the watchdog's heartbeat, and the tunnel that brings
its renderer to this machine.

The key is made here, the first time, and kept in settings.gpu_keys_dir: each pod gets its public half when it's
created, so no one's personal key is involved and nothing but this process can log in.
"""

import logging
import subprocess
from pathlib import Path
from typing import Protocol

from app.gpu.runpod import Pod

logger = logging.getLogger(__name__)

REMOTE = Path(__file__).parent / "remote"
# Where the renderer listens on the pod (localhost only, see remote/setup.sh)
RENDERER_PORT = 8188


class Shell(Protocol):
    def reachable(self, pod: Pod) -> bool: ...
    def run(self, pod: Pod, script: str, *args: str, secrets: dict[str, str] | None = None) -> tuple[int, str]: ...
    def heartbeat(self, pod: Pod) -> bool: ...
    def open_tunnel(self, pod: Pod) -> None: ...
    def tunnel_open(self) -> bool: ...
    def close_tunnel(self) -> None: ...


def ensure_key(keys_dir: Path) -> str:
    """The public key, made on first use."""
    key = keys_dir / "id_ed25519"
    if not key.exists():
        keys_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "unnoodle-gpu", "-f", str(key)], check=True
        )
    return key.with_suffix(".pub").read_text().strip()


def quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


class SSH:
    def __init__(self, keys_dir: Path, tunnel_port: int) -> None:
        self.keys_dir = keys_dir
        self.tunnel_port = tunnel_port
        self.tunnel: subprocess.Popen[bytes] | None = None

    def command(self, pod: Pod, *extra: str) -> list[str]:
        return [
            "ssh",
            "-i",
            str(self.keys_dir / "id_ed25519"),
            "-p",
            str(pod.ssh_port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            # One file per pod: RunPod reuses addresses, and a new pod there has a new host key
            "-o",
            f"UserKnownHostsFile={self.keys_dir / f'known_hosts_{pod.id}'}",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ConnectTimeout=15",
            *extra,
            f"root@{pod.ip}",
        ]

    def reachable(self, pod: Pod) -> bool:
        try:
            return subprocess.run([*self.command(pod), "true"], capture_output=True, timeout=60).returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def run(self, pod: Pod, script: str, *args: str, secrets: dict[str, str] | None = None) -> tuple[int, str]:
        """Pipes a script from remote/ to bash on the pod. Secrets become variables at the top of the piped script,
        so they're never on a command line on either machine."""
        body = (REMOTE / script).read_bytes()
        if secrets:
            body = "".join(f"{k}={quote(v)}\n" for k, v in secrets.items()).encode() + body
        command = [*self.command(pod), "bash -s -- " + " ".join(quote(a) for a in args)]
        done = subprocess.run(command, input=body, capture_output=True)
        output = (done.stdout + done.stderr).decode(errors="replace")
        return done.returncode, output

    def heartbeat(self, pod: Pod) -> bool:
        try:
            done = subprocess.run([*self.command(pod), "touch /dev/shm/heartbeat"], capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False
        return done.returncode == 0

    def open_tunnel(self, pod: Pod) -> None:
        self.close_tunnel()
        # Listens on every interface of this container, so the worker reaches the renderer at gpu:<port>; the
        # container's port isn't published, so nothing outside the compose network does
        forward = f"0.0.0.0:{self.tunnel_port}:127.0.0.1:{RENDERER_PORT}"
        self.tunnel = subprocess.Popen(
            [*self.command(pod, "-N", "-o", "ExitOnForwardFailure=yes", "-L", forward)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Tunnel to pod %s on port %d", pod.id, self.tunnel_port)

    def tunnel_open(self) -> bool:
        return self.tunnel is not None and self.tunnel.poll() is None

    def close_tunnel(self) -> None:
        if self.tunnel is not None and self.tunnel.poll() is None:
            self.tunnel.terminate()
            try:
                self.tunnel.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.tunnel.kill()
        self.tunnel = None
