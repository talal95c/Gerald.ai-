from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from math import hypot, isfinite
import re
from statistics import median
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


GroundingLayer = Literal["element", "text", "snap", "raw", "grounder"]


@dataclass(frozen=True)
class GroundingResolution:
    rect: ScreenRect
    layer: GroundingLayer
    note: str | None = None


def _normalize_text(text: str) -> str:
    text = re.sub(r"\b(?:l|d|j|qu|n|s|c|m|t)[’'](?=\w)", "", text.casefold())
    decomposed = unicodedata.normalize("NFKD", text)
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


def _matched_word_run(
    element: Element,
    query: str,
) -> tuple[tuple[int, int, int, int], bool] | None:
    if element.source != "ocr" or not element.word_boxes:
        return None
    query_tokens = _normalize_text(query).split()
    if not query_tokens:
        return None
    flattened: list[tuple[str, int]] = []
    for index, (word, _rect) in enumerate(element.word_boxes):
        flattened.extend((token, index) for token in _normalize_text(word).split())

    def rectangle_for(start: int) -> tuple[int, int, int, int]:
        selected = {
            index for _token, index in flattened[start : start + len(query_tokens)]
        }
        rectangles = [element.word_boxes[index][1] for index in selected]
        left = min(rect[0] for rect in rectangles)
        top = min(rect[1] for rect in rectangles)
        right = max(rect[0] + rect[2] for rect in rectangles)
        bottom = max(rect[1] + rect[3] for rect in rectangles)
        return left, top, right - left, bottom - top

    runs = [
        flattened[start : start + len(query_tokens)]
        for start in range(max(0, len(flattened) - len(query_tokens) + 1))
    ]
    for start, run in enumerate(runs):
        if [token for token, _index in run] == query_tokens:
            return rectangle_for(start), True
    for start, run in enumerate(runs):
        tokens = [token for token, _index in run]
        if all(
            abs(len(query_word) - len(token)) <= 1
            and SequenceMatcher(None, query_word, token).ratio() >= 0.8
            for query_word, token in zip(query_tokens, tokens)
        ):
            return rectangle_for(start), False
    return None


def _matched_line_runs(
    elements: list[Element],
    query: str,
) -> list[tuple[tuple[int, int, int, int], bool, float]]:
    query_tokens = _normalize_text(query).split()
    if not query_tokens:
        return []
    tokens: list[tuple[str, tuple[int, int, int, int], int]] = []
    for element in elements:
        if element.source not in {"ocr", "uia"}:
            continue
        source_words = (
            element.word_boxes
            if element.source == "ocr" and element.word_boxes
            else ((element.name, element.rect),)
        )
        for word, rect in source_words:
            tokens.extend(
                (token, rect, element.id)
                for token in _normalize_text(word).split()
            )
    tokens.sort(key=lambda item: (item[1][1], item[1][0], item[1][2]))
    visual_lines: list[list[tuple[str, tuple[int, int, int, int], int]]] = []
    for token in tokens:
        _word, rect, _owner = token
        _left, top, _width, height = rect
        compatible = []
        for line in visual_lines:
            overlap = max(
                max(
                    0,
                    min(top + height, item_rect[1] + item_rect[3])
                    - max(top, item_rect[1]),
                )
                / max(1, min(height, item_rect[3]))
                for _item_word, item_rect, _item_owner in line
            )
            if overlap >= 0.5:
                compatible.append((overlap, line))
        if compatible:
            max(compatible, key=lambda item: item[0])[1].append(token)
        else:
            visual_lines.append([token])

    lines: list[list[tuple[str, tuple[int, int, int, int], int]]] = []
    for visual_line in visual_lines:
        ordered = sorted(visual_line, key=lambda item: item[1][0])
        group: list[tuple[str, tuple[int, int, int, int], int]] = []
        for token in ordered:
            if group:
                previous_word, previous_rect, _previous_owner = group[-1]
                left, _top, width, _height = token[1]
                char_widths = [
                    item_rect[2] / max(1, len(item_word))
                    for item_word, item_rect, _owner in group
                    if item_rect[2] > 0
                ]
                char_width = (
                    median(char_widths)
                    if char_widths
                    else max(1.0, width / max(1, len(token[0])))
                )
                gap = left - (previous_rect[0] + previous_rect[2])
                if not (
                    gap < 2 * char_width
                    or re.search(r"[/(),:-]", query) and gap < 4 * char_width
                ):
                    lines.append(group)
                    group = []
            group.append(token)
        if group:
            lines.append(group)

    results = []
    for line in lines:
        for start in range(max(0, len(line) - len(query_tokens) + 1)):
            selected = line[start : start + len(query_tokens)]
            if len({owner for _word, _rect, owner in selected}) < 2:
                continue
            candidate = [word for word, _rect, _owner in selected]
            exact = candidate == query_tokens
            if exact:
                score = 1.0
            else:
                ratios = [
                    SequenceMatcher(None, query_word, candidate_word).ratio()
                    for query_word, candidate_word in zip(query_tokens, candidate)
                ]
                if not ratios or min(ratios) < 0.85:
                    continue
                score = sum(ratios) / len(ratios)
            matched_rects = [rect for _word, rect, _owner in selected]
            results.append(
                (
                    (
                        min(rect[0] for rect in matched_rects),
                        min(rect[1] for rect in matched_rects),
                        max(rect[0] + rect[2] for rect in matched_rects)
                        - min(rect[0] for rect in matched_rects),
                        max(rect[1] + rect[3] for rect in matched_rects)
                        - min(rect[1] for rect in matched_rects),
                    ),
                    exact,
                    score,
                )
            )
    return results


def _matched_word_rect(element: Element, query: str) -> tuple[int, int, int, int] | None:
    match = _matched_word_run(element, query)
    return match[0] if match is not None else None


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
    radius = max(1, round(64 * max(scale_x, scale_y)))
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
    force_visual_coordinates = False
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

    description = args.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("description must be a string")
    target_text = args.get("text")
    query = None if force_coordinates else args.get("text")
    weak_text_matches = []

    def point_sort_key(match, image_x: float, image_y: float):
        element, score, _rank, _rect = match
        ex, ey, ew, eh = element.rect
        distance = hypot(image_x - (ex + ew / 2), image_y - (ey + eh / 2))
        return distance, -score[0], -score[1], ew * eh, element.id

    if query is not None:
        if not isinstance(query, str):
            raise ValueError("text must be a string")
        matches = []
        normalized_query = _normalize_text(query)
        for element in elements:
            score = _text_score(query, element.name)
            word_match = _matched_word_run(element, query)
            word_rect = word_match[0] if word_match is not None else None
            if score is None and word_match is None:
                continue
            score = score or (3, 1.0)
            normalized_name = _normalize_text(element.name)
            if normalized_name == normalized_query:
                rank = 4
            elif word_rect is not None:
                rank = 3 if word_match[1] else 2
            elif score[0] >= 3:
                estimated_width = max(1, len(normalized_query) * 8)
                is_long = len(normalized_name.split()) > 3 or element.rect[2] > 3 * estimated_width
                rank = 1 if is_long else 2
            else:
                rank = 2
            matches.append((element, score, rank, word_rect or element.rect))
        best_single_rank = max((match[2] for match in matches), default=0)
        line_matches = _matched_line_runs(elements, query)
        line_point = None
        if line_matches and "x" in args and "y" in args:
            x, y = args["x"], args["y"]
            if (
                not isinstance(x, (int, float))
                or isinstance(x, bool)
                or not isinstance(y, (int, float))
                or isinstance(y, bool)
            ):
                raise ValueError("x and y must be numbers")
            line_point = (float(x), float(y))
        exact_line_matches = [match for match in line_matches if match[1]]
        if exact_line_matches and best_single_rank < 3:
            if line_point is None:
                chosen = min(
                    exact_line_matches,
                    key=lambda match: match[0][2] * match[0][3],
                )
            else:
                chosen = min(
                    exact_line_matches,
                    key=lambda match: (
                        hypot(
                            line_point[0] - (match[0][0] + match[0][2] / 2),
                            line_point[1] - (match[0][1] + match[0][3] / 2),
                        ),
                        match[0][2] * match[0][3],
                    ),
                )
            return resolved(_screen_rect(capture, chosen[0]), "text")
        fuzzy_line_matches = [match for match in line_matches if not match[1]]
        if fuzzy_line_matches and best_single_rank < 3:
            if line_point is None:
                chosen = max(
                    fuzzy_line_matches,
                    key=lambda match: (match[2], -match[0][2] * match[0][3]),
                )
            else:
                chosen = min(
                    fuzzy_line_matches,
                    key=lambda match: (
                        hypot(
                            line_point[0] - (match[0][0] + match[0][2] / 2),
                            line_point[1] - (match[0][1] + match[0][3] / 2),
                        ),
                        -match[2],
                        match[0][2] * match[0][3],
                    ),
                )
            return resolved(_screen_rect(capture, chosen[0]), "text")
        if matches:
            best_rank = max(match[2] for match in matches)
            matches = [match for match in matches if match[2] == best_rank]
            if best_rank == 1:
                weak_text_matches = matches
            else:
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
                    element, _score, _rank, rect = min(
                        matches,
                        key=lambda match: point_sort_key(match, image_x, image_y),
                    )
                else:
                    element, _score, _rank, rect = min(
                        matches,
                        key=lambda match: (
                            -match[1][0],
                            -match[1][1],
                            match[0].rect[2] * match[0].rect[3],
                            match[0].id,
                        ),
                    )
                return resolved(_screen_rect(capture, rect), _element_layer(element))

    grounder_query = description or (target_text if isinstance(target_text, str) else "")
    if ("element_id" not in args or force_coordinates) and grounder_query:
        from gerald.perception.grounder import configured_grounder, locate_with_timeout

        grounder = configured_grounder()
        if grounder is not None:
            grounder_image = capture.full_image or capture.image
            point = locate_with_timeout(grounder, grounder_image, grounder_query, timeout=4.0)
            if point is not None:
                grounder_x, grounder_y = point
                image_x = grounder_x * capture.image.width / max(1, grounder_image.width)
                image_y = grounder_y * capture.image.height / max(1, grounder_image.height)
                containing = [
                    element
                    for element in elements
                    if element.rect[0] <= image_x <= element.rect[0] + element.rect[2]
                    and element.rect[1] <= image_y <= element.rect[1] + element.rect[3]
                    and all(element.id != weak[0].id for weak in weak_text_matches)
                ]
                if containing:
                    element = min(containing, key=lambda item: item.rect[2] * item.rect[3])
                    return resolved(_screen_rect(capture, element.rect), "grounder", coordinate_note)
                snap_image = image_array if image_array is not None else np.asarray(capture.image)
                snapped = _visual_snap(image_x, image_y, capture, snap_image)
                if snapped is not None:
                    return resolved(snapped, "grounder", coordinate_note)
                return resolved(
                    _raw_rect(capture, image_x, image_y),
                    "grounder",
                    coordinate_note,
                )

    if weak_text_matches:
        x, y = args.get("x"), args.get("y")
        valid_point = (
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and isinstance(y, (int, float))
            and not isinstance(y, bool)
        )
        if valid_point:
            try:
                image_x, image_y = float(x), float(y)
                valid_point = isfinite(image_x) and isfinite(image_y)
            except OverflowError:
                valid_point = False
        if valid_point:
            element, _score, _rank, rect = min(
                weak_text_matches,
                key=lambda match: point_sort_key(match, image_x, image_y),
            )
            return resolved(_screen_rect(capture, rect), _element_layer(element))
        element, _score, _rank, rect = min(
            weak_text_matches,
            key=lambda match: (
                -match[1][0],
                -match[1][1],
                match[0].rect[2] * match[0].rect[3],
                match[0].id,
            ),
        )
        return resolved(_screen_rect(capture, rect), _element_layer(element))

    if query is not None:
        if "x" not in args or "y" not in args:
            raise ValueError(f"text not found on screen: {query}")
        coordinate_note = "text not found, used x,y"
        force_visual_coordinates = True

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
    if containing and not force_visual_coordinates:
        element = min(containing, key=lambda value: value.rect[2] * value.rect[3])
        return resolved(_screen_rect(capture, element.rect), _element_layer(element), coordinate_note)
    if image_array is not None:
        snapped = _visual_snap(image_x, image_y, capture, image_array)
        if snapped is not None:
            return resolved(snapped, "snap", coordinate_note)
        return resolved(_raw_rect(capture, image_x, image_y), "raw", coordinate_note)
    if force_visual_coordinates:
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
