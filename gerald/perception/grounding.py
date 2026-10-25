from __future__ import annotations

from difflib import SequenceMatcher
from dataclasses import dataclass
from math import hypot
import unicodedata

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


def resolve_target(
    args: dict[str, object],
    capture: Capture,
    elements: list[Element],
) -> ScreenRect:
    if "element_id" in args:
        element_id = args["element_id"]
        if not isinstance(element_id, int) or isinstance(element_id, bool):
            raise ValueError("element_id must be an integer")
        element = next((entry for entry in elements if entry.id == element_id), None)
        if element is None:
            raise ValueError(f"unknown element_id: {element_id}")
        return _screen_rect(capture, element.rect)

    query = args.get("text")
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
            return _screen_rect(capture, rect)
        if not isinstance(args.get("x"), (int, float)) or isinstance(args.get("x"), bool):
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
        return _screen_rect(capture, element.rect)
    nearest = None
    nearest_distance = float("inf")
    for element in elements:
        ex, ey, ew, eh = element.rect
        distance = hypot(image_x - (ex + ew / 2), image_y - (ey + eh / 2))
        if distance < nearest_distance:
            nearest, nearest_distance = element, distance
    if nearest is not None and nearest_distance <= 40:
        return _screen_rect(capture, nearest.rect)
    screen_x, screen_y = capture.img_to_screen(image_x, image_y)
    return ScreenRect(round(screen_x - 30), round(screen_y - 30), 60, 60)
