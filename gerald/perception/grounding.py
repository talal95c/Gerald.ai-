from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from math import hypot
import unicodedata
from typing import Literal

import numpy as np

from gerald.capture.screen import Capture
from gerald.perception.elements import Element


@dataclass(frozen=True)
class ScreenRect:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2


GroundingLayer = Literal["element", "text", "snap", "raw"]


@dataclass(frozen=True)
class GroundingResolution:
    rect: ScreenRect
    layer: GroundingLayer
    note: str | None = None


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(
        character if character.isalnum() else " "
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.split())


def _text_score(query: str, candidate: str) -> tuple[int, float] | None:
    query = _normalize_text(query)
    candidate = _normalize_text(candidate)
    if not query or not candidate:
        return None
    if query == candidate:
        return 4, 1.0
    if candidate.startswith(query) or query in candidate:
        return 3, len(query) / len(candidate)
    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    overlap = len(query_tokens & candidate_tokens) / len(query_tokens)
    if overlap >= 0.6:
        return 2, overlap
    ratio = SequenceMatcher(None, query, candidate).ratio()
    if ratio >= 0.8:
        return 1, ratio
    return None


def _matched_word_rect(element: Element, query: str) -> tuple[int, int, int, int]:
    if element.source != "ocr" or not element.word_boxes:
        return element.rect
    query_tokens = _normalize_text(query).split()
    flattened: list[tuple[str, int]] = []
    for index, (word, _rect) in enumerate(element.word_boxes):
        flattened.extend((token, index) for token in _normalize_text(word).split())
    selected: set[int] = set()
    for start in range(max(0, len(flattened) - len(query_tokens) + 1)):
        tokens = [token for token, _index in flattened[start : start + len(query_tokens)]]
        if tokens == query_tokens:
            selected.update(index for _token, index in flattened[start : start + len(query_tokens)])
            break
    if not selected:
        for index, (word, _rect) in enumerate(element.word_boxes):
            tokens = _normalize_text(word).split()
            if any(
                token in query_tokens
                or any(SequenceMatcher(None, token, query_token).ratio() >= 0.8 for query_token in query_tokens)
                for token in tokens
            ):
                selected.add(index)
    if not selected:
        return element.rect
    rectangles = [element.word_boxes[index][1] for index in selected]
    left = min(rect[0] for rect in rectangles)
    top = min(rect[1] for rect in rectangles)
    right = max(rect[0] + rect[2] for rect in rectangles)
    bottom = max(rect[1] + rect[3] for rect in rectangles)
    return left, top, right - left, bottom - top


def _screen_rect(capture: Capture, rect: tuple[int, int, int, int]) -> ScreenRect:
    x, y, width, height = rect
    screen_x, screen_y = capture.img_to_screen(x, y)
    return ScreenRect(
        round(screen_x),
        round(screen_y),
        round(width / capture.scale),
        round(height / capture.scale),
    )


def _raw_rect(capture: Capture, x: float, y: float) -> ScreenRect:
    screen_x, screen_y = capture.img_to_screen(x, y)
    return ScreenRect(round(screen_x - 30), round(screen_y - 30), 60, 60)


def _element_layer(element: Element) -> GroundingLayer:
    return "text" if element.source == "ocr" or element.role.casefold() == "text" else "element"


def _distance_to_rect(x: float, y: float, rect: tuple[int, int, int, int]) -> float:
    left, top, width, height = rect
    dx = max(left - x, 0, x - (left + width))
    dy = max(top - y, 0, y - (top + height))
    return hypot(dx, dy)


def _dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    height, width = mask.shape
    result = np.zeros_like(mask)
    for dy in range(-radius, radius + 1):
        source_top = max(0, -dy)
        source_bottom = min(height, height - dy)
        target_top = max(0, dy)
        target_bottom = min(height, height + dy)
        for dx in range(-radius, radius + 1):
            source_left = max(0, -dx)
            source_right = min(width, width - dx)
            target_left = max(0, dx)
            target_right = min(width, width + dx)
            result[target_top:target_bottom, target_left:target_right] |= mask[
                source_top:source_bottom,
                source_left:source_right,
            ]
    return result


def _components(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = mask.shape
    visited = np.zeros_like(mask)
    components: list[tuple[int, int, int, int]] = []
    for seed_y, seed_x in zip(*np.nonzero(mask), strict=True):
        if visited[seed_y, seed_x]:
            continue
        visited[seed_y, seed_x] = True
        stack = [(int(seed_y), int(seed_x))]
        min_x = max_x = int(seed_x)
        min_y = max_y = int(seed_y)
        while stack:
            y, x = stack.pop()
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        stack.append((next_y, next_x))
        components.append((min_x, min_y, max_x + 1, max_y + 1))
    return components


def _visual_snap(
    args_x: float,
    args_y: float,
    capture: Capture,
    image_array: np.ndarray,
) -> ScreenRect | None:
    if image_array.ndim == 2:
        rgb = np.repeat(image_array[:, :, None], 3, axis=2)
    elif image_array.ndim == 3 and image_array.shape[2] >= 3:
        rgb = image_array[:, :, :3]
    else:
        return None
    image_height, image_width = rgb.shape[:2]
    scale_x = image_width / max(1, capture.monitor.width)
    scale_y = image_height / max(1, capture.monitor.height)
    screen_x, screen_y = capture.img_to_screen(args_x, args_y)
    center_x = round((screen_x - capture.monitor.left) * scale_x)
    center_y = round((screen_y - capture.monitor.top) * scale_y)
    radius = max(1, round(64 / capture.scale))
    left = max(0, center_x - radius)
    top = max(0, center_y - radius)
    right = min(image_width, center_x + radius)
    bottom = min(image_height, center_y + radius)
    if right - left < 2 or bottom - top < 2:
        return None

    crop = rgb[top:bottom, left:right].astype(np.float32)
    gray = crop[:, :, 0] * 0.299 + crop[:, :, 1] * 0.587 + crop[:, :, 2] * 0.114
    gradient_y, gradient_x = np.gradient(gray)
    magnitude = np.hypot(gradient_x, gradient_y)
    threshold = max(30.0, float(np.percentile(magnitude, 85)))
    mask = _dilate(magnitude >= threshold, 2)

    crop_height, crop_width = mask.shape
    max_side = min(2 * radius, crop_width, crop_height)
    candidates = []
    for component in _components(mask):
        x0, y0, x1, y1 = component
        component_width = x1 - x0
        component_height = y1 - y0
        if min(component_width, component_height) < 8 or max(component_width, component_height) > max_side:
            continue
        touching = sum(
            (
                x0 == 0,
                y0 == 0,
                x1 >= crop_width,
                y1 >= crop_height,
            )
        )
        if touching > 2:
            continue
        global_box = (left + x0, top + y0, left + x1, top + y1)
        point_x, point_y = center_x, center_y
        contains = (
            global_box[0] <= point_x < global_box[2]
            and global_box[1] <= point_y < global_box[3]
        )
        center_distance = hypot(
            point_x - (global_box[0] + global_box[2]) / 2,
            point_y - (global_box[1] + global_box[3]) / 2,
        )
        candidates.append((contains, center_distance, component_width * component_height, global_box))

    containing = [candidate for candidate in candidates if candidate[0]]
    if containing:
        chosen = min(containing, key=lambda candidate: (candidate[2], candidate[1]))
    else:
        nearby = [candidate for candidate in candidates if candidate[1] <= radius]
        if not nearby:
            return None
        chosen = min(nearby, key=lambda candidate: (candidate[1], candidate[2]))

    x0, y0, x1, y1 = chosen[3]
    padded = (
        max(0, x0 - 4),
        max(0, y0 - 4),
        min(image_width, x1 + 4),
        min(image_height, y1 + 4),
    )
    return ScreenRect(*capture.full_rect_to_screen(
        (padded[0], padded[1], padded[2] - padded[0], padded[3] - padded[1])
    ))


def resolve_target(
    args: dict[str, object],
    capture: Capture,
    elements: list[Element],
    image_array: np.ndarray | None = None,
    *,
    with_details: bool = False,
) -> ScreenRect | GroundingResolution:
    def resolved(rect: ScreenRect, layer: GroundingLayer, note: str | None = None):
        detail = GroundingResolution(rect, layer, note)
        return detail if with_details else detail.rect

    coordinate_note = None
    force_coordinates = False
    if "element_id" in args:
        element_id = args["element_id"]
        if not isinstance(element_id, int) or isinstance(element_id, bool):
            raise ValueError("element_id must be an integer")
        element = next((entry for entry in elements if entry.id == element_id), None)
        if element is None:
            raise ValueError(f"unknown element_id: {element_id}")
        if (
            element.role.casefold() == "text"
            and "x" in args
            and "y" in args
        ):
            x, y = args["x"], args["y"]
            if (
                not isinstance(x, (int, float))
                or isinstance(x, bool)
                or not isinstance(y, (int, float))
                or isinstance(y, bool)
            ):
                raise ValueError("x and y must be numbers")
            if _distance_to_rect(float(x), float(y), element.rect) > 24:
                force_coordinates = True
                coordinate_note = "element_id ignored: x,y is more than 24 image px outside its text element"
            else:
                return resolved(_screen_rect(capture, element.rect), "text")
        else:
            return resolved(_screen_rect(capture, element.rect), _element_layer(element))

    query = None if force_coordinates else args.get("text")
    if query is not None:
        if not isinstance(query, str):
            raise ValueError("text must be a string")
        matches = []
        for element in elements:
            score = _text_score(query, element.name)
            if score is not None:
                matches.append((element, score))
        if matches:
            has_point = "x" in args and "y" in args
            if has_point:
                x, y = args["x"], args["y"]
                if (
                    not isinstance(x, (int, float))
                    or isinstance(x, bool)
                    or not isinstance(y, (int, float))
                    or isinstance(y, bool)
                ):
                    raise ValueError("x and y must be numbers")
                image_x, image_y = float(x), float(y)

                def point_sort(match):
                    element, score = match
                    ex, ey, ew, eh = element.rect
                    distance = hypot(image_x - (ex + ew / 2), image_y - (ey + eh / 2))
                    area = ew * eh
                    return distance, -score[0], -score[1], area, element.id

                element, _score = min(matches, key=point_sort)
            else:
                element, _score = min(
                    matches,
                    key=lambda match: (
                        -match[1][0],
                        -match[1][1],
                        match[0].rect[2] * match[0].rect[3],
                        match[0].id,
                    ),
                )
            rect = element.rect
            if _normalize_text(element.name) != _normalize_text(query):
                rect = _matched_word_rect(element, query)
            return resolved(_screen_rect(capture, rect), _element_layer(element))
        if "x" not in args or "y" not in args:
            raise ValueError(f"text not found on screen: {query}")

    if "x" not in args or "y" not in args:
        if isinstance(query, str):
            raise ValueError(f"text not found on screen: {query}")
        raise ValueError("target requires element_id, text, or x and y")
    x, y = args["x"], args["y"]
    if not isinstance(x, (int, float)) or isinstance(x, bool) or not isinstance(y, (int, float)) or isinstance(y, bool):
        raise ValueError("x and y must be numbers")
    image_x, image_y = float(x), float(y)
    containing = [
        element
        for element in elements
        if element.rect[0] <= image_x <= element.rect[0] + element.rect[2]
        and element.rect[1] <= image_y <= element.rect[1] + element.rect[3]
    ]
    if containing:
        element = min(containing, key=lambda value: value.rect[2] * value.rect[3])
        return resolved(_screen_rect(capture, element.rect), _element_layer(element), coordinate_note)
    if image_array is not None:
        snapped = _visual_snap(image_x, image_y, capture, image_array)
        if snapped is not None:
            return resolved(snapped, "snap", coordinate_note)
        return resolved(_raw_rect(capture, image_x, image_y), "raw", coordinate_note)

    nearest = None
    nearest_distance = float("inf")
    for element in elements:
        ex, ey, ew, eh = element.rect
        distance = hypot(image_x - (ex + ew / 2), image_y - (ey + eh / 2))
        if distance < nearest_distance:
            nearest, nearest_distance = element, distance
    if nearest is not None and nearest_distance <= 40:
        return resolved(_screen_rect(capture, nearest.rect), _element_layer(nearest), coordinate_note)
    return resolved(_raw_rect(capture, image_x, image_y), "raw", coordinate_note)
