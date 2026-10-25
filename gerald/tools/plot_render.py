from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from gerald.tools.plot import PLOT_INSETS, PlotCommand


@dataclass(frozen=True)
class PlotPalette:
    curve: str
    secondary_curves: tuple[str, str]
    point_fill: str
    point_outline: str
    label_fill: str
    label_border: str
    label_text: str
    grid: str
    axis: str
    tick: str
    card: str
    card_border: str


def _curve_color(index: int, palette: PlotPalette) -> QColor:
    return QColor(palette.curve if index == 0 else palette.secondary_curves[index - 1])


def _nice_step(span: float) -> float:
    raw = span / 7
    power = 10 ** math.floor(math.log10(raw))
    fraction = raw / power
    nice = 1 if fraction <= 1 else 2 if fraction <= 2 else 2.5 if fraction <= 2.5 else 5 if fraction <= 5 else 10
    return nice * power


def _ticks(start: float, end: float) -> list[float]:
    step = _nice_step(end - start)
    first = math.ceil(start / step) * step
    count = min(10, max(1, math.floor((end - first) / step) + 1))
    return [first + index * step for index in range(count)]


def _format_tick(value: float) -> str:
    if abs(value) < 1e-10:
        value = 0
    text = f"{value:.6g}"
    if "e" in text:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def draw_plot(
    painter: QPainter,
    plot: PlotCommand,
    progress: float,
    font_family: str,
    palette: PlotPalette,
) -> None:
    _x, _y, width, height = plot.box
    bounds = QRectF(0, 0, width, height)
    painter.save()
    painter.setPen(QPen(QColor(palette.card_border), 1))
    painter.setBrush(QColor(palette.card))
    painter.drawRoundedRect(bounds, 16, 16)

    left, top, right, bottom = PLOT_INSETS
    graph = QRectF(left, top, max(1.0, width - left - right), max(1.0, height - top - bottom))
    x_ticks = _ticks(plot.x_min, plot.x_max)
    y_ticks = _ticks(plot.y_min, plot.y_max)
    tick_font = QFont(font_family)
    tick_font.setPixelSize(11)
    metrics = QFontMetricsF(tick_font)
    painter.setFont(tick_font)

    painter.save()
    painter.setPen(QPen(QColor(palette.grid), 1))
    for tick in x_ticks:
        x = graph.left() + (tick - plot.x_min) / (plot.x_max - plot.x_min) * graph.width()
        painter.drawLine(QPointF(x, graph.top()), QPointF(x, graph.bottom()))
    for tick in y_ticks:
        y = graph.top() + (plot.y_max - tick) / (plot.y_max - plot.y_min) * graph.height()
        painter.drawLine(QPointF(graph.left(), y), QPointF(graph.right(), y))
    painter.restore()

    axis_x = (
        graph.left() + (0 - plot.x_min) / (plot.x_max - plot.x_min) * graph.width()
        if plot.x_min <= 0 <= plot.x_max
        else graph.left()
    )
    axis_y = (
        graph.top() + (plot.y_max - 0) / (plot.y_max - plot.y_min) * graph.height()
        if plot.y_min <= 0 <= plot.y_max
        else graph.bottom()
    )
    painter.setPen(QPen(QColor(palette.axis), 1.25))
    painter.drawLine(QPointF(graph.left(), axis_y), QPointF(graph.right(), axis_y))
    painter.drawLine(QPointF(axis_x, graph.top()), QPointF(axis_x, graph.bottom()))
    arrow_size = 5
    arrow_half_width = 2.5
    painter.drawLine(
        QPointF(graph.right(), axis_y),
        QPointF(graph.right() - arrow_size, axis_y - arrow_half_width),
    )
    painter.drawLine(
        QPointF(graph.right(), axis_y),
        QPointF(graph.right() - arrow_size, axis_y + arrow_half_width),
    )
    painter.drawLine(
        QPointF(axis_x, graph.top()),
        QPointF(axis_x - arrow_half_width, graph.top() + arrow_size),
    )
    painter.drawLine(
        QPointF(axis_x, graph.top()),
        QPointF(axis_x + arrow_half_width, graph.top() + arrow_size),
    )

    painter.setPen(QColor(palette.tick))
    for tick in x_ticks:
        x = graph.left() + (tick - plot.x_min) / (plot.x_max - plot.x_min) * graph.width()
        label = _format_tick(tick)
        painter.drawText(
            QRectF(x - 30, graph.bottom() + 4, 60, metrics.height()),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            label,
        )
    for tick in y_ticks:
        y = graph.top() + (plot.y_max - tick) / (plot.y_max - plot.y_min) * graph.height()
        label = _format_tick(tick)
        painter.drawText(
            QRectF(4, y - metrics.height() / 2, left - 12, metrics.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            label,
        )

    painter.save()
    painter.setClipRect(graph)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    visible_count = max(1, math.ceil(len(plot.curves[0].samples) * min(1.0, max(0.0, progress))))
    for curve_index, curve in enumerate(plot.curves):
        color = _curve_color(curve_index, palette)
        path = QPainterPath()
        active = False
        for sample in curve.samples[:visible_count]:
            if sample is None:
                active = False
                continue
            x_value, y_value = sample
            x = graph.left() + (x_value - plot.x_min) / (plot.x_max - plot.x_min) * graph.width()
            clamped_y = min(plot.y_max, max(plot.y_min, y_value))
            y = graph.top() + (plot.y_max - clamped_y) / (plot.y_max - plot.y_min) * graph.height()
            if active:
                path.lineTo(x, y)
            else:
                path.moveTo(x, y)
                active = True
        painter.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
    painter.restore()

    if progress >= 1:
        placed_labels: list[QRectF] = []
        for point in plot.points:
            point_x = point.x_img - plot.box[0]
            point_y = point.y_img - plot.box[1]
            painter.setPen(QPen(QColor(palette.point_outline), 1))
            painter.setBrush(QColor(palette.point_fill))
            painter.drawEllipse(QPointF(point_x, point_y), 3, 3)
            if point.label:
                label_font = QFont(font_family)
                label_font.setPixelSize(12)
                painter.setFont(label_font)
                label_metrics = QFontMetricsF(label_font)
                label_width = label_metrics.horizontalAdvance(point.label) + 12
                label_height = label_metrics.height() + 6
                candidates = (
                    (point_x + 7, point_y - label_height - 5),
                    (point_x - label_width - 7, point_y - label_height - 5),
                    (point_x + 7, point_y + 7),
                    (point_x - label_width - 7, point_y + 7),
                    (point_x + 7, point_y - 2 * label_height - 8),
                    (point_x - label_width - 7, point_y - 2 * label_height - 8),
                )
                pill = None
                for candidate_x, candidate_y in candidates:
                    label_x = min(width - label_width - 4, max(4, candidate_x))
                    label_y = min(height - label_height - 4, max(4, candidate_y))
                    candidate = QRectF(label_x, label_y, label_width, label_height)
                    if not any(candidate.adjusted(-3, -3, 3, 3).intersects(other) for other in placed_labels):
                        pill = candidate
                        break
                if pill is None:
                    pill = QRectF(
                        min(width - label_width - 4, max(4, point_x + 7)),
                        min(height - label_height - 4, max(4, point_y - label_height - 5)),
                        label_width,
                        label_height,
                    )
                placed_labels.append(pill)
                painter.setPen(QPen(QColor(palette.label_border), 1))
                painter.setBrush(QColor(palette.label_fill))
                painter.drawRoundedRect(pill, 8, 8)
                painter.setPen(QColor(palette.label_text))
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, point.label)

    if len(plot.curves) > 1 or plot.curves[0].label != plot.curves[0].expr:
        legend_font = QFont(font_family)
        legend_font.setPixelSize(11)
        painter.setFont(legend_font)
        legend_x = left
        for index, curve in enumerate(plot.curves):
            color = _curve_color(index, palette)
            painter.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(legend_x, 18), QPointF(legend_x + 18, 18))
            painter.setPen(QColor(palette.label_text))
            painter.drawText(QPointF(legend_x + 24, 22), curve.label)
            legend_x += 34 + QFontMetricsF(legend_font).horizontalAdvance(curve.label)
    painter.restore()
