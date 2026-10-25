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
    lines: list[str] = []
    current = ""
    for word in text.split():
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
    def estimate(text: str) -> float:
        return sum(
            9.8 * (1.25 if character.isupper() or character in "MW@#%&" else 1)
            for character in text
        )

    measure = measure_text or estimate
    sizes = []
    for node in nodes:
        words = node["text"].split()
        longest_word = max((measure(word) for word in words), default=0)
        width = min(240.0, max(84.0, measure(node["text"]) + 28, longest_word + 28))
        lines = _wrap(node["text"], width - 28, measure)
        height = 20 + 20 * len(lines)
        sizes.append((width, height, lines))
    title_height = 40.0 if title else 16.0
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

            child_map = {node_id: [] for node_id in ids}
            parent_map: dict[str, str] = {}
            for edge in kept_edges:
                parent, child = edge["from"], edge["to"]
                if child not in parent_map and parent != child:
                    parent_map[child] = parent
                    child_map[parent].append(child)
            roots = [node_id for node_id in ids if node_id not in parent_map]
            if not roots:
                roots = [ids[0]]
            centers: dict[str, float] = {}
            rightmost = 24.0
            gap = 38.0

            def place_subtree(node_id: str, left: float) -> tuple[dict[str, float], float]:
                child_centers: list[float] = []
                placed: dict[str, float] = {}
                cursor_x = left
                for child_id in child_map[node_id]:
                    child_placed, child_right = place_subtree(child_id, cursor_x)
                    placed.update(child_placed)
                    child_centers.append(child_placed[child_id])
                    cursor_x = child_right + gap
                subtree_right = cursor_x - gap if child_centers else left
                width = sizes[ids.index(node_id)][0]
                if child_centers:
                    center = sum(child_centers) / len(child_centers)
                    node_left = center - width / 2
                    shift = max(0.0, left - node_left)
                    if shift:
                        placed = {key: value + shift for key, value in placed.items()}
                        child_centers = [value + shift for value in child_centers]
                        center += shift
                        subtree_right += shift
                else:
                    center = left + width / 2
                placed[node_id] = center
                return placed, max(subtree_right, center + width / 2)

            for root in roots:
                placed, root_right = place_subtree(root, rightmost)
                centers.update(placed)
                rightmost = root_right + gap
            for index, node_id in enumerate(ids):
                w, h, lines = sizes[index]
                center_x = centers.get(node_id, rightmost + w / 2)
                boxes.append(
                    NodeBox(
                        node_id,
                        nodes[index]["text"],
                        center_x - w / 2,
                        ypos[layers[node_id]] + (layer_height[layers[node_id]] - h) / 2,
                        w,
                        h,
                        lines,
                    )
                )
            width = max(84.0, rightmost - gap + 24.0)
            height = cursor - 20
    by_id = {box.id: box for box in boxes}
    directions = []
    for edge in kept_edges:
        source, target = by_id[edge["from"]], by_id[edge["to"]]
        if layout == "tree":
            start = (source.x + source.w / 2, source.y + source.h)
            end = (target.x + target.w / 2, target.y)
            elbow_y = (start[1] + end[1]) / 2
            points = (start, (start[0], elbow_y), (end[0], elbow_y), end)
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
            points = (start, end)
        else:
            start = (source.x + source.w, source.y + source.h / 2)
            end = (target.x, target.y + target.h / 2)
            points = (start, end)
        directions.append(
            EdgePath(
                edge["from"],
                edge["to"],
                points,
                edge.get("label"),
                ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2),
            )
        )
    return DiagramLayout(width, height, boxes, directions, title, reveal_order)
