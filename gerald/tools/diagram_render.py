from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from gerald.tools.diagram import DiagramLayout


def draw_diagram(
    painter: QPainter,
    layout: DiagramLayout,
    x: float,
    y: float,
    scale: float = 1.0,
    elapsed: float = 10.0,
    font_family: str = "Inter",
    background_alpha: int = 235,
) -> None:
    painter.save()
    painter.translate(x, y)
    painter.scale(scale, scale)
    bounds = QRectF(0, 0, layout.width, layout.height)
    for outset, alpha in ((12, 3), (10, 4), (8, 4), (6, 5), (4, 5), (2, 6)):
        shadow = bounds.translated(0, 2).adjusted(-outset, -outset, outset, outset)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.drawRoundedRect(shadow, 16 + outset, 16 + outset)
    painter.setPen(QPen(QColor("#E5E5EA"), 1))
    painter.setBrush(QColor(255, 255, 255, background_alpha))
    painter.drawRoundedRect(bounds, 16, 16)
    if layout.title:
        title_font = QFont(font_family)
        title_font.setPixelSize(17)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor("#1D1D1F"))
        title = QFontMetricsF(title_font).elidedText(
            layout.title,
            Qt.TextElideMode.ElideRight,
            max(1, layout.width - 32),
        )
        painter.drawText(QRectF(16, 8, layout.width - 32, 24), Qt.AlignmentFlag.AlignCenter, title)
    order = {node_id: index for index, node_id in enumerate(layout.reveal_order)}
    for edge in layout.edges:
        start_time = order.get(edge.target, 0) * 0.09 + 0.08
        progress = min(1.0, max(0.0, (elapsed - start_time) / 0.16))
        if progress <= 0:
            continue
        segment_lengths = [
            math.hypot(second[0] - first[0], second[1] - first[1])
            for first, second in zip(edge.points, edge.points[1:])
        ]
        total_length = sum(segment_lengths)
        remaining = total_length * progress
        edge_path = QPainterPath(QPointF(*edge.points[0]))
        for first, second, length in zip(edge.points, edge.points[1:], segment_lengths):
            if remaining >= length:
                edge_path.lineTo(QPointF(*second))
                remaining -= length
            elif remaining > 0:
                ratio = remaining / max(1e-9, length)
                edge_path.lineTo(
                    QPointF(first[0] + (second[0] - first[0]) * ratio, first[1] + (second[1] - first[1]) * ratio)
                )
                break
            else:
                break
        painter.setOpacity(progress)
        painter.setPen(QPen(QColor("#6E6E73"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(edge_path)
        if progress >= 1:
            penultimate, last = edge.points[-2], edge.points[-1]
            angle = math.atan2(last[1] - penultimate[1], last[0] - penultimate[0])
            for delta in (-0.45, 0.45):
                painter.drawLine(
                    QPointF(*last),
                    QPointF(last[0] - 8 * math.cos(angle + delta), last[1] - 8 * math.sin(angle + delta)),
                )
            if edge.label:
                font = QFont(font_family)
                font.setPixelSize(12)
                painter.setFont(font)
                metrics = QFontMetricsF(font)
                width = metrics.horizontalAdvance(edge.label) + 12
                pill = QRectF(edge.label_pos[0] - width / 2, edge.label_pos[1] - 10, width, 20)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 245))
                painter.drawRoundedRect(pill, 8, 8)
                painter.setPen(QColor("#6E6E73"))
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, edge.label)
        painter.setOpacity(1.0)
    for node in layout.nodes:
        progress = min(1.0, max(0.0, (elapsed - order.get(node.id, 0) * 0.09) / 0.18))
        if progress <= 0:
            continue
        painter.save()
        painter.setOpacity(progress)
        center = QPointF(node.x + node.w / 2, node.y + node.h / 2)
        painter.translate(center)
        painter.scale(0.96 + progress * 0.04, 0.96 + progress * 0.04)
        painter.translate(-center)
        rect = QRectF(node.x, node.y, node.w, node.h)
        painter.setPen(QPen(QColor("#E5E5EA"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(rect, 10, 10)
        font = QFont(font_family)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.setPen(QColor("#1D1D1F"))
        metrics = QFontMetricsF(font)
        line_height = metrics.height()
        block_height = len(node.lines) * line_height
        top = node.y + (node.h - block_height) / 2
        max_text_width = max(1, node.w - 28)
        for index, line in enumerate(node.lines):
            display_line = metrics.elidedText(line, Qt.TextElideMode.ElideRight, max_text_width)
            painter.drawText(
                QRectF(node.x + 14, top + index * line_height, max_text_width, line_height),
                Qt.AlignmentFlag.AlignCenter,
                display_line,
            )
        painter.restore()
    painter.restore()
