"""The calls the worker makes to ComfyUI: upload inputs, run a graph while following its progress, fetch outputs."""

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

logger = logging.getLogger(__name__)

# Inputs go into their own folder in ComfyUI's input directory, named after the asset, so uploading again is harmless
INPUT_SUBFOLDER = "unnoodle"


class ComfyUnavailable(Exception):
    """ComfyUI couldn't be reached or dropped the connection. The job should wait for it, not fail."""


class ComfyRejected(Exception):
    """ComfyUI refused the graph before running it: the workflow itself is broken."""


class ComfyFailed(Exception):
    """The run failed inside ComfyUI."""

    def __init__(self, message: str, node_type: str | None = None, exception_type: str | None = None) -> None:
        super().__init__(message)
        self.node_type = node_type
        self.exception_type = exception_type


@dataclass(frozen=True)
class OutputFile:
    filename: str
    subfolder: str
    type: str


class Comfy(Protocol):
    def upload(self, data: bytes, name: str) -> str:
        """Puts a file in ComfyUI's input folder and returns the value a LoadImage or LoadVideo node takes."""
        ...

    def run(
        self,
        graph: dict[str, Any],
        prompt_id: str,
        output_node: str,
        on_progress: Callable[[float], None],
        on_quiet: Callable[[], None],
    ) -> list[OutputFile]:
        """Runs a graph to the end and returns the files its output node saved.

        on_progress gets 0 to 1 as the node doing the work advances; on_quiet is called whenever nothing has been heard
        for a while, so the caller can show it is still alive.
        """
        ...

    def download(self, file: OutputFile) -> bytes: ...


class ComfyClient:
    def __init__(self, base_url: str, quiet_after_s: float = 10) -> None:
        self.http = httpx.Client(base_url=base_url, timeout=httpx.Timeout(30, connect=5))
        self.ws_url = base_url.replace("http", "ws", 1).rstrip("/") + "/ws"
        self.quiet_after_s = quiet_after_s

    def upload(self, data: bytes, name: str) -> str:
        form = {"type": "input", "subfolder": INPUT_SUBFOLDER, "overwrite": "true"}
        response = self.request("POST", "/upload/image", files={"image": (name, data)}, data=form)
        stored = response.json()
        return f"{stored['subfolder']}/{stored['name']}" if stored["subfolder"] else str(stored["name"])

    def run(
        self,
        graph: dict[str, Any],
        prompt_id: str,
        output_node: str,
        on_progress: Callable[[float], None],
        on_quiet: Callable[[], None],
    ) -> list[OutputFile]:
        # Errors and progress go only to the client that submitted the prompt, so connect first and submit under
        # the same client id
        client_id = uuid.uuid4().hex
        try:
            with connect(f"{self.ws_url}?clientId={client_id}", max_size=None, open_timeout=5) as ws:
                body = {"prompt": graph, "prompt_id": prompt_id, "client_id": client_id}
                response = self.http.post("/prompt", json=body)
                if response.status_code == 400:
                    raise ComfyRejected(rejection(response.json()))
                response.raise_for_status()
                self.follow(ws, prompt_id, on_progress, on_quiet)
        except (OSError, WebSocketException, httpx.TransportError) as error:
            raise ComfyUnavailable(str(error) or type(error).__name__) from error

        history = self.request("GET", f"/history/{prompt_id}").json()
        outputs = history[prompt_id]["outputs"].get(output_node, {})
        # SaveImage lists "images", video savers other keys; every entry with a filename is a file
        return [
            OutputFile(item["filename"], item.get("subfolder", ""), item.get("type", "output"))
            for items in outputs.values()
            if isinstance(items, list)
            for item in items
            if isinstance(item, dict) and "filename" in item
        ]

    def follow(
        self, ws: Any, prompt_id: str, on_progress: Callable[[float], None], on_quiet: Callable[[], None]
    ) -> None:
        while True:
            try:
                message = ws.recv(timeout=self.quiet_after_s)
            except TimeoutError:
                on_quiet()
                continue
            if isinstance(message, bytes):
                continue  # live previews
            event = json.loads(message)
            data = event.get("data") or {}
            if data.get("prompt_id") != prompt_id:
                continue
            match event.get("type"):
                case "progress" if data.get("max"):
                    on_progress(data["value"] / data["max"])
                case "execution_success":
                    return
                case "execution_error":
                    raise ComfyFailed(
                        str(data.get("exception_message", "")).strip(),
                        node_type=data.get("node_type"),
                        exception_type=data.get("exception_type"),
                    )
                case "execution_interrupted":
                    raise ComfyFailed("The run was interrupted")

    def download(self, file: OutputFile) -> bytes:
        params = {"filename": file.filename, "subfolder": file.subfolder, "type": file.type}
        return self.request("GET", "/view", params=params).content

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.http.request(method, url, **kwargs)
        except httpx.TransportError as error:
            raise ComfyUnavailable(str(error) or type(error).__name__) from error
        response.raise_for_status()
        return response


def rejection(body: dict[str, Any]) -> str:
    """Summarises why ComfyUI refused a graph, e.g. "node 7 (UnnoodleDevSteps): Required input is missing: seed"."""
    parts = []
    for node_id, node in (body.get("node_errors") or {}).items():
        reasons = "; ".join(f"{e.get('message')}: {e.get('details')}" for e in node.get("errors", []))
        parts.append(f"node {node_id} ({node.get('class_type')}): {reasons}")
    error = body.get("error") or {}
    return ", ".join(parts) or str(error.get("message") or body)
