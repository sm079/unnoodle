"""RunPod's REST API, as far as renting one GPU pod goes: create, look up, list and delete."""

import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

REST = "https://rest.runpod.io/v1"
# RunPod's official template with the renderer installed (the same one runpod-helper uses)
TEMPLATE = "cw3nka7d08"
# Pods this app rents are named this, so they can be told apart from anyone else's on the account
POD_NAME = "unnoodle-gpu"
# Models for all three pipelines (about 85 GB) plus the template and headroom
DISK_GB = 150


class NoCapacity(Exception):
    """No GPU of the type asked for is free right now."""


class RunPodError(Exception):
    pass


@dataclass(frozen=True)
class Pod:
    id: str
    name: str
    status: str
    cost_per_hour: float | None
    ip: str | None
    ssh_port: int | None


class Pods(Protocol):
    def create(self, gpu_type: str, public_key: str) -> Pod: ...
    def get(self, pod_id: str) -> Pod | None: ...
    def list(self) -> list[Pod]: ...
    def delete(self, pod_id: str) -> None: ...


def pod_of(data: dict[str, Any]) -> Pod:
    port = (data.get("portMappings") or {}).get("22")
    return Pod(
        id=data["id"],
        name=data.get("name") or "",
        status=data.get("desiredStatus") or "",
        cost_per_hour=data.get("costPerHr"),
        ip=data.get("publicIp") or None,
        ssh_port=int(port) if port else None,
    )


class RunPod:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            base_url=REST,
            # Cloudflare in front of the API turns away clients without a User-Agent of their own
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "unnoodle-gpu"},
            timeout=60,
        )

    def create(self, gpu_type: str, public_key: str) -> Pod:
        body = {
            "name": POD_NAME,
            "templateId": TEMPLATE,
            "gpuTypeIds": [gpu_type],
            "gpuCount": 1,
            # Not shared community hosts: inputs and outputs are people's own
            "cloudType": "SECURE",
            "containerDiskInGb": DISK_GB,
            "volumeInGb": 0,
            # SSH only: no public URLs for the renderer or anything else on the pod
            "ports": ["22/tcp"],
            "supportPublicIp": True,
            # The template puts this in root's authorized_keys: only the GPU process's own key gets in
            "env": {"PUBLIC_KEY": public_key},
        }
        response = self.client.post("/pods", json=body)
        if response.is_error:
            # RunPod words it two ways: "no instances currently available", "no longer any instances available"
            if re.search(r"no (longer any|instances currently) (instances )?available", response.text):
                raise NoCapacity(response.text)
            raise RunPodError(f"Creating a pod failed: {response.status_code} {response.text}")
        return pod_of(response.json())

    def get(self, pod_id: str) -> Pod | None:
        response = self.client.get(f"/pods/{pod_id}")
        if response.status_code == 404:
            return None
        if response.is_error:
            raise RunPodError(f"Looking up pod {pod_id} failed: {response.status_code} {response.text}")
        return pod_of(response.json())

    def list(self) -> list[Pod]:
        response = self.client.get("/pods")
        if response.is_error:
            raise RunPodError(f"Listing pods failed: {response.status_code} {response.text}")
        return [pod_of(p) for p in response.json()]

    def delete(self, pod_id: str) -> None:
        response = self.client.delete(f"/pods/{pod_id}")
        if response.is_error and response.status_code != 404:
            raise RunPodError(f"Deleting pod {pod_id} failed: {response.status_code} {response.text}")
