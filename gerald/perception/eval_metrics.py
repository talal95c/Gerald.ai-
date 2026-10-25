from __future__ import annotations

import math

from PIL import Image, ImageDraw


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


def annotate_screenshot(
    image: Image.Image,
    gt: tuple[float, float, float, float] | None,
    prediction: tuple[float, float, float, float] | None,
) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    if gt is not None:
        x, y, width, height = (round(value) for value in gt)
        draw.rectangle((x, y, x + width, y + height), outline="#22C55E", width=3)
    if prediction is not None:
        x, y, width, height = (round(value) for value in prediction)
        if width <= 0 or height <= 0:
            draw.rectangle((x - 5, y - 5, x + 5, y + 5), outline="#FF9F0A", width=3)
        else:
            draw.rectangle((x, y, x + width, y + height), outline="#FF9F0A", width=3)
    return annotated
