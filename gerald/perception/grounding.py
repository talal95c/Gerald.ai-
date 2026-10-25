from __future__ import annotations

from dataclasses import dataclass
from math import hypot

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
        x, y, w, h = element.rect
        x, y = capture.img_to_screen(x, y)
        return ScreenRect(round(x), round(y), round(w / capture.scale), round(h / capture.scale))

    if "x" not in args or "y" not in args:
        raise ValueError("target requires element_id or x and y")
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
        ex, ey, ew, eh = element.rect
        sx, sy = capture.img_to_screen(ex, ey)
        return ScreenRect(round(sx), round(sy), round(ew / capture.scale), round(eh / capture.scale))
    nearest = None
    nearest_distance = float("inf")
    for element in elements:
        ex, ey, ew, eh = element.rect
        distance = hypot(image_x - (ex + ew / 2), image_y - (ey + eh / 2))
        if distance < nearest_distance:
            nearest, nearest_distance = element, distance
    if nearest is not None and nearest_distance <= 40:
        ex, ey, ew, eh = nearest.rect
        sx, sy = capture.img_to_screen(ex, ey)
        return ScreenRect(round(sx), round(sy), round(ew / capture.scale), round(eh / capture.scale))
    screen_x, screen_y = capture.img_to_screen(image_x, image_y)
    return ScreenRect(round(screen_x - 30), round(screen_y - 30), 60, 60)
