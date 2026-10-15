"""Building ComfyUI graphs in code, in the API format that POST /prompt takes.

A workflow builds its graph for each request, so a graph has exactly the nodes that request needs: one image chain
per attached photo, and none for photos that weren't attached. Exported graphs can't do that, because they have a
fixed number of slots.

    g = Graph()
    image = g.add("LoadImage", image="unnoodle/photo.png")
    g.output(g.add("SaveImage", images=image[0], filename_prefix="unnoodle/x"))

Some inputs have dots in their names: ComfyUI's growing inputs ("ref_images.ref_image_0") and the options of a
dynamic choice ("format.codec"). They are passed with ** since they aren't Python names.
"""

from dataclasses import dataclass, field
from typing import Any

# What an input that takes another node's output holds: [node id, output index]
Link = list[str | int]


@dataclass(frozen=True)
class Node:
    id: str
    class_type: str

    def __getitem__(self, index: int) -> Link:
        return [self.id, index]


@dataclass
class Graph:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The node whose saved files are the result
    output_node: str | None = None

    def add(self, class_type: str, **inputs: Any) -> Node:
        node = Node(str(len(self.nodes) + 1), class_type)
        self.nodes[node.id] = {"class_type": class_type, "inputs": inputs}
        return node

    def output(self, node: Node) -> Node:
        self.output_node = node.id
        return node
