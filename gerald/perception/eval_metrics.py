from __future__ import annotations

import math


def scale_box(
    box: dict[str, float],
    dpr: float,
) -> tuple[float, float, float, float]:
    return tuple(box[key] * dpr for key in ("x", "y", "width", "height"))


def prediction_hit(
    prediction: tuple[float, float, float, float],
    ground_truth: tuple[float, float, float, float],
    margin: float,
) -> bool:
    x, y, width, height = prediction
    gx, gy, gw, gh = ground_truth
    center_x, center_y = x + width / 2, y + height / 2
    return gx - margin <= center_x <= gx + gw + margin and gy - margin <= center_y <= gy + gh + margin


def center_distance(
    prediction: tuple[float, float, float, float],
    ground_truth: tuple[float, float, float, float],
) -> float:
    x, y, width, height = prediction
    gx, gy, gw, gh = ground_truth
    return math.hypot(x + width / 2 - gx - gw / 2, y + height / 2 - gy - gh / 2)
