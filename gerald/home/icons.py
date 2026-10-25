from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from gerald.home.style import ACCENT, SECONDARY


def icon(name: str, color: str = SECONDARY) -> QIcon:
    pixmap = QPixmap(32, 32)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(
            QColor(color),
            1.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    if name == "home":
        path.moveTo(2.5, 7.2)
        path.lineTo(8, 2.8)
        path.lineTo(13.5, 7.2)
        path.lineTo(13.5, 13.7)
        path.lineTo(9.6, 13.7)
        path.lineTo(9.6, 9.5)
        path.lineTo(6.4, 9.5)
        path.lineTo(6.4, 13.7)
        path.lineTo(2.5, 13.7)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "chat":
        path.addRoundedRect(QRectF(2.4, 2.5, 11.2, 8.8), 2.2, 2.2)
        path.moveTo(5, 11.2)
        path.lineTo(4.2, 14)
        path.lineTo(7.5, 11.2)
        painter.drawPath(path)
    elif name == "book":
        path.moveTo(2.2, 3.1)
        path.lineTo(6.6, 3.1)
        path.quadTo(8, 3.1, 8, 4.6)
        path.lineTo(8, 13.5)
        path.quadTo(8, 12, 6.6, 12)
        path.lineTo(2.2, 12)
        path.closeSubpath()
        painter.drawPath(path)
        path = QPainterPath()
        path.moveTo(13.8, 3.1)
        path.lineTo(9.4, 3.1)
        path.quadTo(8, 3.1, 8, 4.6)
        path.lineTo(8, 13.5)
        path.quadTo(8, 12, 9.4, 12)
        path.lineTo(13.8, 12)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "plus":
        painter.drawLine(QPointF(8, 3), QPointF(8, 13))
        painter.drawLine(QPointF(3, 8), QPointF(13, 8))
    elif name == "gear":
        painter.drawEllipse(QPointF(8, 8), 3.1, 3.1)
        painter.drawEllipse(QPointF(8, 8), 5.8, 5.8)
        for angle in range(0, 360, 45):
            painter.save()
            painter.translate(8, 8)
            painter.rotate(angle)
            painter.drawLine(QPointF(0, -5.5), QPointF(0, -7))
            painter.restore()
    elif name == "document":
        path.moveTo(4, 1.5)
        path.lineTo(9.5, 1.5)
        path.lineTo(13, 5)
        path.lineTo(13, 14.5)
        path.lineTo(4, 14.5)
        path.closeSubpath()
        path.moveTo(9.5, 1.8)
        path.lineTo(9.5, 5)
        path.lineTo(12.6, 5)
        painter.drawPath(path)
        painter.drawLine(QPointF(6, 8), QPointF(11, 8))
        painter.drawLine(QPointF(6, 10.5), QPointF(11, 10.5))
    elif name == "trash":
        painter.drawLine(QPointF(3, 4), QPointF(13, 4))
        painter.drawLine(QPointF(6, 2), QPointF(10, 2))
        path.moveTo(4, 5)
        path.lineTo(4.8, 14)
        path.lineTo(11.2, 14)
        path.lineTo(12, 5)
        painter.drawPath(path)
        painter.drawLine(QPointF(6.5, 7), QPointF(6.8, 12))
        painter.drawLine(QPointF(9.5, 7), QPointF(9.2, 12))
    elif name == "send":
        path.moveTo(2, 7.8)
        path.lineTo(14, 2)
        path.lineTo(10, 14)
        path.lineTo(7.8, 9.8)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(7.8, 9.8), QPointF(14, 2))
    elif name == "chevron-down":
        painter.drawLine(QPointF(4, 6), QPointF(8, 10))
        painter.drawLine(QPointF(8, 10), QPointF(12, 6))
    elif name == "close":
        painter.drawLine(QPointF(5, 5), QPointF(11, 11))
        painter.drawLine(QPointF(11, 5), QPointF(5, 11))
    else:
        path.addEllipse(QPointF(8, 8), 5, 5)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def accent_icon(name: str) -> QIcon:
    return icon(name, ACCENT)
