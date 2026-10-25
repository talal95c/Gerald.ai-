from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

SAMPLE_COUNT = 96
SHAPES_BY_STATUS = {
    "idle": "circle",
    "listening": "circle",
    "thinking": "triangle",
    "speaking": "squircle",
    "error": "circle",
    "offline": "circle",
}

_BLUE = QColor("#6F7BFF")
_VIOLET = QColor("#9AA3FF")
_LILAC = QColor("#D9C8FF")
_PINK = QColor("#F1BDE8")


def shape_for_status(status: str) -> str:
    return SHAPES_BY_STATUS.get(status, "circle")


def target_radius(shape: str, angle: float) -> float:
    if shape == "circle":
        return 1.0
    if shape == "triangle":
        sector = 2 * math.pi / 3
        face_angle = (angle + math.pi / 6 + sector / 2) % sector - sector / 2
        radius = 0.64 / math.cos(face_angle)
        corner = max(0.0, min(1.0, (radius - 0.82) / 0.18))
        corner = corner * corner * (3 - 2 * corner)
        return radius + (1 - radius) * corner
    if shape == "squircle":
        exponent = 4
        radius = (
            abs(math.cos(angle)) ** exponent + abs(math.sin(angle)) ** exponent
        ) ** (-1 / exponent)
        return radius / (2 ** (1 / exponent))
    raise ValueError(f"Unknown agent shape: {shape}")


def interpolated_radius(
    start_shape: str,
    end_shape: str,
    angle: float,
    progress: float,
) -> float:
    amount = max(0.0, min(1.0, progress))
    start = target_radius(start_shape, angle)
    end = target_radius(end_shape, angle)
    return start + (end - start) * amount


def _shape_points(
    center: QPointF,
    size: float,
    start_shape: str,
    end_shape: str,
    progress: float,
    rotation: float = 0.0,
) -> list[QPointF]:
    points = []
    for index in range(SAMPLE_COUNT):
        angle = 2 * math.pi * index / SAMPLE_COUNT
        radius = interpolated_radius(
            start_shape, end_shape, angle - rotation, progress
        )
        distance = size * radius / 2
        points.append(
            QPointF(
                center.x() + math.cos(angle) * distance,
                center.y() + math.sin(angle) * distance,
            )
        )
    return points


def _smooth_closed_path(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    midpoint = QPointF(
        (points[-1].x() + points[0].x()) / 2,
        (points[-1].y() + points[0].y()) / 2,
    )
    path.moveTo(midpoint)
    for index, point in enumerate(points):
        following = points[(index + 1) % len(points)]
        midpoint = QPointF(
            (point.x() + following.x()) / 2,
            (point.y() + following.y()) / 2,
        )
        path.quadTo(point, midpoint)
    path.closeSubpath()
    return path


def _shape_path(
    center: QPointF,
    size: float,
    start_shape: str,
    end_shape: str,
    progress: float,
    rotation: float = 0.0,
) -> tuple[QPainterPath, list[QPointF]]:
    points = _shape_points(center, size, start_shape, end_shape, progress, rotation)
    return _smooth_closed_path(points), points


def paint_orb(
    painter: QPainter,
    rect: QRectF,
    *,
    status: str,
    start_shape: str,
    end_shape: str,
    progress: float,
    mic_level: float,
    output_level: float,
    now: float,
    reduced_motion: bool,
    thinking_rotation: float = 0.0,
    opacity: float = 1.0,
) -> None:
    center = rect.center()
    size = min(rect.width(), rect.height())
    gray = status in {"error", "offline"}
    if gray:
        body_colors = (QColor("#A6AAB4"), QColor("#C2C5CD"), QColor("#E5E6EA"), QColor("#EEE7EF"))
        halo_color = QColor("#A8AFCA")
        size *= 0.72
    else:
        body_colors = (_BLUE, _VIOLET, _LILAC, _PINK)
        halo_color = _VIOLET

    if status == "listening":
        size *= 0.91 + max(0.0, min(1.0, mic_level)) * 0.11
        if not reduced_motion:
            size *= 1 + math.sin(now * 3.4) * (0.018 + mic_level * 0.025)
    elif status == "speaking":
        size *= 0.91 + max(0.0, min(1.0, output_level)) * 0.11
    rotation = (
        thinking_rotation if status == "thinking" and not reduced_motion else 0.0
    )
    painter.save()
    painter.setOpacity(max(0.0, min(1.0, opacity)))

    halo_radius = rect.width() * 0.82
    halo = QRadialGradient(center, halo_radius)
    halo.setColorAt(
        0.0, QColor(halo_color.red(), halo_color.green(), halo_color.blue(), 116)
    )
    halo.setColorAt(
        0.42, QColor(halo_color.red(), halo_color.green(), halo_color.blue(), 52)
    )
    halo.setColorAt(1.0, QColor(halo_color.red(), halo_color.green(), halo_color.blue(), 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(
        QRectF(
            center.x() - halo_radius,
            center.y() - halo_radius,
            halo_radius * 2,
            halo_radius * 2,
        )
    )

    path, _points = _shape_path(
        center,
        size,
        start_shape,
        end_shape,
        progress,
        rotation,
    )
    gradient = QLinearGradient(
        center.x() - size * 0.45,
        center.y() - size * 0.55,
        center.x() + size * 0.45,
        center.y() + size * 0.55,
    )
    gradient.setColorAt(0.0, body_colors[0])
    gradient.setColorAt(0.42, body_colors[1])
    gradient.setColorAt(0.78, body_colors[2])
    gradient.setColorAt(1.0, body_colors[3])
    painter.setBrush(gradient)
    painter.setPen(QPen(QColor(255, 255, 255, 92), 0.8))
    painter.drawPath(path)

    painter.save()
    painter.setClipPath(path)
    pink = QRadialGradient(
        QPointF(center.x() + size * 0.18, center.y() - size * 0.23),
        size * 0.58,
    )
    pink.setColorAt(0.0, QColor(255, 207, 241, 112))
    pink.setColorAt(1.0, QColor(255, 207, 241, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(pink)
    painter.drawEllipse(
        QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
    )
    painter.restore()

    inner_center = QPointF(center.x() - size * 0.015, center.y() - size * 0.015)
    inner_path, inner_points = _shape_path(
        inner_center,
        size * 0.70,
        start_shape,
        end_shape,
        progress,
        rotation,
    )
    inner_gradient = QLinearGradient(
        inner_center.x() - size * 0.2,
        inner_center.y() - size * 0.25,
        inner_center.x() + size * 0.25,
        inner_center.y() + size * 0.25,
    )
    inner_gradient.setColorAt(0.0, QColor(255, 255, 255, 104))
    inner_gradient.setColorAt(1.0, QColor(255, 255, 255, 24))
    painter.setBrush(inner_gradient)
    painter.setPen(QPen(QColor(255, 255, 255, 196), 1.3))
    painter.drawPath(inner_path)

    rim = QPainterPath()
    for index, point in enumerate(inner_points):
        angle = 2 * math.pi * index / SAMPLE_COUNT
        if 0.04 <= angle <= math.pi / 2 + 0.3:
            if rim.isEmpty():
                rim.moveTo(point)
            else:
                rim.lineTo(point)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(
        QPen(
            QColor(255, 255, 255, 228),
            1.3,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
        )
    )
    painter.drawPath(rim)
    painter.restore()
