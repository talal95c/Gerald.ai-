from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class NodeBox:
    id: str
    text: str
    x: float
    y: float
    w: float
    h: float
    lines: tuple[str, ...]


@dataclass(frozen=True)
class EdgePath:
    source: str
    target: str
    points: tuple[tuple[float, float], ...]
    label: str | None
    label_pos: tuple[float, float]


@dataclass(frozen=True)
class DiagramLayout:
    width: float
    height: float
    nodes: list[NodeBox]
    edges: list[EdgePath]
    title: str | None
    reveal_order: list[str]


@dataclass(frozen=True)
class DiagramCommand:
    layout: DiagramLayout
    x: float | None = None
    y: float | None = None


def _wrap(text: str, width: float, measure: Callable[[str], float]) -> tuple[str, ...]:
    words = []
    for word in text.split():
        while len(word) > 1 and measure(word) > width:
            cut = len(word) - 1
            while cut > 1 and measure(word[:cut]) > width:
                cut -= 1
            words.append(word[:cut])
            word = word[cut:]
        words.append(word)
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and measure(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return tuple(lines)


def _acyclic_layers(node_ids: list[str], edges: list[dict]) -> tuple[dict[str, int], list[dict]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
    state: dict[str, int] = {}
    kept: set[tuple[str, str]] = set()

    def visit(node_id: str) -> None:
        state[node_id] = 1
        for child in adjacency[node_id]:
            if state.get(child) == 1:
                continue
            kept.add((node_id, child))
            if state.get(child, 0) == 0:
                visit(child)
        state[node_id] = 2

    for node_id in node_ids:
        if state.get(node_id, 0) == 0:
            visit(node_id)
    filtered = [edge for edge in edges if (edge["from"], edge["to"]) in kept]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in filtered:
        incoming[edge["to"]] += 1
        outgoing[edge["from"]].append(edge["to"])
    roots = [node_id for node_id in node_ids if incoming[node_id] == 0] or [node_ids[0]]
    layers = {node_id: 0 for node_id in roots}
    for _ in range(len(node_ids)):
        for node_id in node_ids:
            if node_id in layers:
                for child in outgoing[node_id]:
                    layers[child] = max(layers.get(child, 0), layers[node_id] + 1)
    for node_id in node_ids:
        layers.setdefault(node_id, 0)
    return layers, filtered


def layout_diagram(
    *,
    layout: str,
    nodes: list[dict],
    title: str | None = None,
    edges: list[dict] | None = None,
    measure_text: Callable[[str], float] | None = None,
) -> DiagramLayout:
    if not isinstance(layout, str) or layout not in {"flow", "tree", "cycle"}:
        raise ValueError("layout must be flow, tree, or cycle")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 12:
        raise ValueError("nodes must contain between 2 and 12 items")
    if edges is None:
        edges = []
    if not isinstance(edges, list):
        raise ValueError("edges must be an array")
    if len(edges) > 20:
        raise ValueError("edges must contain at most 20 items")
    if title is not None and not isinstance(title, str):
        raise ValueError("title must be a string")
    ids: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"].strip():
            raise ValueError("each node requires a non-empty id")
        if set(node) - {"id", "text"}:
            raise ValueError("node fields must be id and text")
        if node["id"] in ids:
            raise ValueError(f"duplicate node id: {node['id']}")
        text = node.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"node {node['id']} text must be non-empty")
        if len(text) > 40:
            raise ValueError(f"node {node['id']} text must be at most 40 characters")
        ids.append(node["id"])
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") not in ids or edge.get("to") not in ids:
            raise ValueError("edge references an unknown node id")
        if set(edge) - {"from", "to", "label"}:
            raise ValueError("edge fields must be from, to, and optional label")
        label = edge.get("label")
        if label is not None and (not isinstance(label, str) or len(label) > 24):
            raise ValueError("edge label must be a string of at most 24 characters")
    measure = measure_text or (lambda text: len(text) * 7.2)
    sizes = []
    for node in nodes:
        width = min(200.0, max(72.0, measure(node["text"]) + 24))
        lines = _wrap(node["text"], width - 24, measure)
        height = 16 + 16 * len(lines)
        sizes.append((width, height, lines))
    title_height = 34.0 if title else 16.0
    boxes: list[NodeBox] = []
    kept_edges = edges
    reveal_order = ids[:]
    if layout == "cycle":
        n = len(nodes)
        rx, ry = max(120.0, n * 80.0), max(100.0, n * 65.0)
        margin_x, margin_y = 100.0, 32.0
        center_x, center_y = rx + margin_x, ry + margin_y
        centers = [
            (center_x + rx * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
             center_y + ry * math.sin(-math.pi / 2 + 2 * math.pi * i / n))
            for i in range(n)
        ]
        for node, (w, h, lines), (cx, cy) in zip(nodes, sizes, centers):
            boxes.append(NodeBox(node["id"], node["text"], cx - w / 2, cy - h / 2 + title_height, w, h, lines))
        width, height = 2 * (rx + margin_x), 2 * (ry + margin_y) + title_height
    else:
        layers, kept_edges = _acyclic_layers(ids, edges)
        reveal_order = [
            node_id
            for layer in sorted(set(layers.values()))
            for node_id in ids
            if layers[node_id] == layer
        ]
        groups: dict[int, list[int]] = {}
        for index, node_id in enumerate(ids):
            groups.setdefault(layers[node_id], []).append(index)
        ordered_layers = sorted(groups)
        if layout == "flow":
            layer_width = {layer: max(sizes[i][0] for i in groups[layer]) for layer in ordered_layers}
            xpos, cursor = {}, 24.0
            for layer in ordered_layers:
                xpos[layer] = cursor
                cursor += layer_width[layer] + 60
            for layer in ordered_layers:
                y = title_height + 20
                for index in groups[layer]:
                    w, h, lines = sizes[index]
                    boxes.append(NodeBox(ids[index], nodes[index]["text"], xpos[layer] + (layer_width[layer] - w) / 2, y, w, h, lines))
                    y += h + 38
            width = cursor - 36
            height = max((sum(sizes[i][1] + 38 for i in groups[layer]) for layer in ordered_layers), default=0) + title_height + 44
        else:
            layer_height = {layer: max(sizes[i][1] for i in groups[layer]) for layer in ordered_layers}
            ypos, cursor = {}, title_height + 18
            for layer in ordered_layers:
                ypos[layer] = cursor
                cursor += layer_height[layer] + 54
            for layer in ordered_layers:
                x = 24.0
                for index in groups[layer]:
                    w, h, lines = sizes[index]
                    boxes.append(NodeBox(ids[index], nodes[index]["text"], x, ypos[layer] + (layer_height[layer] - h) / 2, w, h, lines))
                    x += w + 38
            width = max((sum(sizes[i][0] + 38 for i in groups[layer]) for layer in ordered_layers), default=0) + 8
            height = cursor - 20
    by_id = {box.id: box for box in boxes}
    directions = []
    for edge in kept_edges:
        source, target = by_id[edge["from"]], by_id[edge["to"]]
        if layout == "tree":
            start = (source.x + source.w / 2, source.y + source.h)
            end = (target.x + target.w / 2, target.y)
        elif layout == "cycle":
            source_center = (source.x + source.w / 2, source.y + source.h / 2)
            target_center = (target.x + target.w / 2, target.y + target.h / 2)
            dx, dy = target_center[0] - source_center[0], target_center[1] - source_center[1]

            def boundary(box: NodeBox, center: tuple[float, float], vx: float, vy: float):
                factors = [
                    (box.w / 2) / abs(vx) if vx else float("inf"),
                    (box.h / 2) / abs(vy) if vy else float("inf"),
                ]
                amount = min(factors)
                return center[0] + vx * amount, center[1] + vy * amount

            start = boundary(source, source_center, dx, dy)
            end = boundary(target, target_center, -dx, -dy)
        else:
            start = (source.x + source.w, source.y + source.h / 2)
            end = (target.x, target.y + target.h / 2)
        directions.append(EdgePath(edge["from"], edge["to"], (start, end), edge.get("label"), ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)))
    return DiagramLayout(width, height, boxes, directions, title, reveal_order)
