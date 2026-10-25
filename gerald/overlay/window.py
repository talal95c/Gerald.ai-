from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import (
    ArrowCommand,
    CircleCommand,
    ClearCommand,
    HighlightCommand,
    LinkCommand,
    NoteCommand,
    PointCommand,
    UnderlineCommand,
)

ACCENT = QColor("#FF5A36")
DARK = QColor(28, 29, 33, 225)


@dataclass
class _Mark:
    command: object
    created: float
    ttl: float


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self._marks: list[_Mark] = []
        self._status = "idle"
        self._caption = ""
        self._caption_time = 0.0
        self._mic_level = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._set_capture_exclusion()

    def _set_capture_exclusion(self) -> None:
        if os.name != "nt":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            get_window_long = ctypes.windll.user32.GetWindowLongPtrW
            set_window_long = ctypes.windll.user32.SetWindowLongPtrW
            exstyle = get_window_long(hwnd, -20)
            set_window_long(hwnd, -20, exstyle | 0x20 | 0x80000 | 0x8000000)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)
        except Exception:
            pass

    def set_status(self, status: str, mic_level: float | None = None) -> None:
        self._status = status
        if mic_level is not None:
            self._mic_level = max(0.0, min(1.0, mic_level))
        self.update()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        self._caption_time = time.monotonic()
        self._ensure_timer()
        self.update()

    def add_commands(self, commands: list[object], ttl: float = 12.0) -> None:
        now = time.monotonic()
        for command in commands:
            if isinstance(command, ClearCommand):
                self._marks.clear()
            else:
                self._marks.append(_Mark(command, now, ttl))
        self._ensure_timer()
        self.update()

    def clear(self) -> None:
        self._marks.clear()
        self._status = "idle"
        self.update()

    def _ensure_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self) -> None:
        now = time.monotonic()
        self._marks = [mark for mark in self._marks if now - mark.created < mark.ttl]
        animating = any(now - mark.created < 0.35 for mark in self._marks)
        if animating and self._timer.interval() != 16:
            self._timer.start(16)
        elif not animating and self._timer.interval() != 200:
            self._timer.start(200)
        self.update()
        if not self._marks and now - self._caption_time > 6:
            self._timer.stop()

    def _qt_position(self, x: float, y: float) -> tuple[float, float, float]:
        for screen in QApplication.screens():
            geometry = screen.geometry()
            ratio = screen.devicePixelRatio()
            left, top = geometry.x() * ratio, geometry.y() * ratio
            right, bottom = left + geometry.width() * ratio, top + geometry.height() * ratio
            if left <= x <= right and top <= y <= bottom:
                return (
                    geometry.x() + (x - left) / ratio,
                    geometry.y() + (y - top) / ratio,
                    ratio,
                )
        ratio = QApplication.primaryScreen().devicePixelRatio()
        return x / ratio, y / ratio, ratio

    def _rect(self, rect: ScreenRect) -> QRectF:
        x, y, ratio = self._qt_position(rect.x, rect.y)
        return QRectF(x, y, rect.w / ratio, rect.h / ratio)

    def _point(self, point: tuple[int, int]) -> tuple[float, float]:
        x, y, _ratio = self._qt_position(*point)
        return x, y

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        for mark in self._marks:
            age = now - mark.created
            opacity = max(0.0, min(1.0, (mark.ttl - age) / 1.2))
            painter.setOpacity(opacity)
            painter.setPen(QPen(ACCENT, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            self._paint_mark(painter, mark.command, min(1.0, age / 0.35), age)
        painter.setOpacity(1.0)
        self._paint_status(painter, now)
        painter.end()

    def _paint_mark(self, painter: QPainter, command: object, progress: float, age: float) -> None:
        if isinstance(command, CircleCommand):
            rect = self._rect(command.rect)
            path = QPainterPath()
            points = 64
            for index in range(points + 1):
                if index / points > progress:
                    break
                angle = 2 * math.pi * index / points
                wobble = math.sin(angle * 5 + age * 3) * 1.2 if age < 0.35 else 0
                x = rect.center().x() + (rect.width() / 2 + wobble) * math.cos(angle)
                y = rect.center().y() + (rect.height() / 2 + wobble) * math.sin(angle)
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        elif isinstance(command, (ArrowCommand, LinkCommand)):
            start = self._point(command.start)
            end = self._point(command.end)
            dx, dy = end[0] - start[0], end[1] - start[1]
            distance = max(1.0, math.hypot(dx, dy))
            bend = min(36.0, distance * 0.12)
            control = (start[0] + dx * 0.5 - dy / distance * bend, start[1] + dy * 0.5 + dx / distance * bend)
            path = QPainterPath()
            path.moveTo(*start)
            path.quadTo(*control, *end)
            self._draw_progress_path(painter, path, progress)
            if progress >= 1 and isinstance(command, ArrowCommand):
                angle = math.atan2(end[1] - control[1], end[0] - control[0])
                head = QPainterPath()
                head.moveTo(*end)
                head.lineTo(end[0] - 12 * math.cos(angle - 0.45), end[1] - 12 * math.sin(angle - 0.45))
                head.moveTo(*end)
                head.lineTo(end[0] - 12 * math.cos(angle + 0.45), end[1] - 12 * math.sin(angle + 0.45))
                painter.drawPath(head)
            if isinstance(command, LinkCommand) and command.label and progress >= 1:
                painter.drawText(QPointF(control[0], control[1]), command.label)
        elif isinstance(command, (UnderlineCommand, HighlightCommand)):
            rect = self._rect(command.rect)
            if isinstance(command, UnderlineCommand):
                painter.drawLine(rect.topLeft(), QPointF(rect.left() + rect.width() * progress, rect.top()))
            else:
                painter.setBrush(QColor(255, 90, 54, 35))
                painter.drawRect(QRectF(rect.x(), rect.y(), rect.width() * progress, rect.height()))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(rect)
        elif isinstance(command, PointCommand):
            x, y = self._point(command.rect.center)
            radius = 5 + 2 * math.sin(age * 5)
            painter.setBrush(ACCENT)
            painter.drawEllipse(QPointF(x, y), radius, radius)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(x, y), radius + 7, radius + 7)
            if command.label:
                painter.drawText(QPointF(x + 12, y), command.label)
        elif isinstance(command, NoteCommand):
            rect = self._rect(command.rect)
            pill = QRectF(rect.x(), rect.y() - 34, max(70, len(command.text) * 7 + 20), 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(DARK)
            painter.drawRoundedRect(pill, 8, 8)
            painter.setPen(QColor("white"))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, command.text)

    @staticmethod
    def _draw_progress_path(painter: QPainter, path: QPainterPath, progress: float) -> None:
        steps = max(1, int(100 * progress))
        partial = QPainterPath()
        partial.moveTo(path.pointAtPercent(0))
        for index in range(1, steps + 1):
            partial.lineTo(path.pointAtPercent(index / 100))
        painter.drawPath(partial)

    def _paint_status(self, painter: QPainter, now: float) -> None:
        if self._status == "idle" and (not self._caption or now - self._caption_time > 6):
            return
        width = min(self.width() - 40, max(190, len(self._caption) * 7 + 150))
        pill = QRectF((self.width() - width) / 2, self.height() - 72, width, 42)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(DARK)
        painter.drawRoundedRect(pill, 14, 14)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Sans Serif", 10))
        label = {"listening": "Écoute", "thinking": "Réflexion", "speaking": "Gerald parle"}.get(self._status, "")
        painter.drawText(pill.adjusted(12, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, label)
        if self._status == "listening":
            bar = QRectF(pill.right() - 26, pill.center().y() - 3, 14, max(2, 6 + self._mic_level * 16))
            painter.setBrush(ACCENT)
            painter.drawRoundedRect(bar, 3, 3)
        if self._caption and now - self._caption_time < 6:
            fade = max(0.0, 1 - (now - self._caption_time) / 6)
            painter.setOpacity(fade)
            painter.drawText(pill.adjusted(80, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, self._caption[:100])
            painter.setOpacity(1)
