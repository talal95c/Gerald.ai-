from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PyQt6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from gerald.capture.screen import Capture
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


def _accent_color() -> QColor:
    color = QColor(os.environ.get("GERALD_ACCENT", "#FF9F0A"))
    return color if color.isValid() else QColor("#FF9F0A")


def _reduced_motion() -> bool:
    if os.environ.get("GERALD_REDUCE_MOTION") == "1":
        return True
    if os.name != "nt":
        return False
    try:
        import ctypes

        enabled = ctypes.c_int()
        result = ctypes.windll.user32.SystemParametersInfoW(
            0x1042, 0, ctypes.byref(enabled), 0
        )
        return bool(result) and not bool(enabled.value)
    except Exception:
        return False


def _system_font_family() -> str:
    if sys.platform == "win32":
        candidates = ("Segoe UI Variable Text", "Segoe UI")
    elif sys.platform == "darwin":
        candidates = (".AppleSystemUIFont", "SF Pro Text")
    else:
        candidates = ("Inter", "Noto Sans")
    available = {family.casefold(): family for family in QFontDatabase.families()}
    return next((available[name.casefold()] for name in candidates if name.casefold() in available), candidates[-1])


ACCENT = _accent_color()


@dataclass
class _Mark:
    command: object
    created: float
    ttl: float


class _GlassTextInput(QWidget):
    def __init__(self, owner: OverlayWindow) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(520, 44)
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText("Demande à Gerald…")
        self.edit.setFrame(False)
        font = QFont(owner._font_family)
        font.setPixelSize(15)
        self.edit.setFont(font)
        self.edit.setStyleSheet(
            "QLineEdit { background: transparent; border: none; }"
        )
        self.edit.installEventFilter(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 6)
        layout.addWidget(self.edit)
        self.edit.returnPressed.connect(self._submit)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.edit and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.owner._cancel_text_input()
                return True
        return super().eventFilter(watched, event)

    def _submit(self) -> None:
        self.owner._submit_text_input(self.edit.text())

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.frameGeometry().center()
        dark = self.owner._dark_for_global_logical(center)
        self.owner._draw_glass_card(painter, QRectF(self.rect()), 22, dark)
        label = self.owner._palette_colors(dark)[1]
        palette = self.edit.palette()
        palette.setColor(QPalette.ColorRole.Text, label)
        palette.setColor(QPalette.ColorRole.PlaceholderText, label)
        self.edit.setPalette(palette)
        painter.end()


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
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.virtualGeometry())
        self._marks: list[_Mark] = []
        self._marks_visible = True
        self._status = "idle"
        self._status_visible = False
        self._status_message = ""
        self._status_changed = time.monotonic()
        self._caption = ""
        self._caption_time = 0.0
        self._mic_level = 0.0
        self._output_level = 0.0
        self._capture: Capture | None = None
        self._appearance_cache: dict[tuple[int, int, int, int], bool] = {}
        self._reduced_motion = _reduced_motion()
        self._font_family = _system_font_family()
        self._text_input_submit = None
        self._text_input_cancel = None
        self._text_input = _GlassTextInput(self)
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

    def set_capture(self, capture: Capture | None) -> None:
        self._capture = capture
        self._appearance_cache.clear()
        self.update()

    def set_status(
        self,
        status: str,
        mic_level: float | None = None,
        output_level: float | None = None,
        message: str | None = None,
    ) -> None:
        if status != self._status:
            self._status_changed = time.monotonic()
        if status != "idle" or self._status != "idle":
            self._status_visible = True
        self._status = status
        self._status_message = message or ""
        if mic_level is not None:
            self._mic_level = max(0.0, min(1.0, mic_level))
        if output_level is not None:
            self._output_level = max(0.0, min(1.0, output_level))
        if status != "idle":
            self._ensure_timer()
        self.update()

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        self._caption_time = time.monotonic()
        self._ensure_timer()
        self.update()

    def open_text_input(self, on_submit, on_cancel) -> None:
        self._text_input_submit = on_submit
        self._text_input_cancel = on_cancel
        self._text_input.edit.clear()
        area = QApplication.primaryScreen().availableGeometry()
        self._text_input.setGeometry(
            area.center().x() - self._text_input.width() // 2,
            area.bottom() - 24 - self._text_input.height(),
            self._text_input.width(),
            self._text_input.height(),
        )
        self._text_input.show()
        self._text_input.raise_()
        self._text_input.activateWindow()
        self._text_input.edit.setFocus()
        self._text_input.update()

    def close_text_input(self) -> None:
        self._text_input.hide()
        self._text_input_submit = None
        self._text_input_cancel = None

    def _submit_text_input(self, text: str) -> None:
        callback = self._text_input_submit
        if callback is not None:
            callback(text)

    def _cancel_text_input(self) -> None:
        callback = self._text_input_cancel
        if callback is not None:
            callback()

    def add_commands(self, commands: list[object], ttl: float = 12.0) -> None:
        now = time.monotonic()
        for command in commands:
            if isinstance(command, ClearCommand):
                self._marks.clear()
            else:
                self._marks.append(_Mark(command, now, ttl))
        self._ensure_timer()
        self.update()

    def set_marks_visible(self, visible: bool) -> None:
        self._marks_visible = visible
        self.update()

    def clear(self) -> None:
        self._marks.clear()
        self._status = "idle"
        self._status_visible = False
        self._status_changed = time.monotonic()
        self.update()

    def _ensure_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start(16)

    def _tick(self) -> None:
        now = time.monotonic()
        self._marks = [mark for mark in self._marks if now - mark.created < mark.ttl]
        animating = (
            any(
                now - mark.created < 0.32
                or (isinstance(mark.command, PointCommand) and now - mark.created < 1.2)
                for mark in self._marks
            )
            and not self._reduced_motion
        )
        status_age = now - self._status_changed
        animating = animating or (
            self._status in {"thinking"}
            or (self._status != "idle" and status_age < (0.15 if self._reduced_motion else 0.2))
            or (self._status == "idle" and status_age < 0.15)
        )
        caption_active = bool(self._caption) and now - self._caption_time < 6
        if animating and self._timer.interval() != 16:
            self._timer.start(16)
        elif self._marks or caption_active or self._status != "idle":
            if self._timer.interval() != 200:
                self._timer.start(200)
        else:
            self._timer.stop()
        self.update()

    def _qt_position(self, x: float, y: float) -> tuple[float, float, float]:
        for screen in QApplication.screens():
            geometry = screen.geometry()
            ratio = screen.devicePixelRatio()
            left, top = geometry.x() * ratio, geometry.y() * ratio
            right, bottom = left + geometry.width() * ratio, top + geometry.height() * ratio
            if left <= x <= right and top <= y <= bottom:
                return (
                    geometry.x() + (x - left) / ratio - self.geometry().x(),
                    geometry.y() + (y - top) / ratio - self.geometry().y(),
                    ratio,
                )
        ratio = QApplication.primaryScreen().devicePixelRatio()
        return x / ratio - self.geometry().x(), y / ratio - self.geometry().y(), ratio

    def _rect(self, rect: ScreenRect) -> QRectF:
        x, y, ratio = self._qt_position(rect.x, rect.y)
        return QRectF(x, y, rect.w / ratio, rect.h / ratio)

    def _point(self, point: tuple[int, int]) -> tuple[float, float]:
        x, y, _ratio = self._qt_position(*point)
        return x, y

    def _widget_to_physical(self, x: float, y: float) -> tuple[float, float]:
        logical_x = x + self.geometry().x()
        logical_y = y + self.geometry().y()
        for screen in QApplication.screens():
            if screen.geometry().contains(QPoint(round(logical_x), round(logical_y))):
                ratio = screen.devicePixelRatio()
                return logical_x * ratio, logical_y * ratio
        ratio = QApplication.primaryScreen().devicePixelRatio()
        return logical_x * ratio, logical_y * ratio

    def _dark_for_physical(self, x: float, y: float) -> bool:
        if self._capture is None:
            return True
        key = (round(x), round(y), 0, 0)
        if key not in self._appearance_cache:
            image = self._capture.image
            image_x, image_y = self._capture.screen_to_img(x, y)
            radius = max(2, round(12 * self._capture.scale))
            crop = image.crop(
                (
                    round(image_x) - radius,
                    round(image_y) - radius,
                    round(image_x) + radius + 1,
                    round(image_y) + radius + 1,
                )
            ).convert("L")
            luminance = crop.resize((1, 1)).getpixel((0, 0)) / 255
            self._appearance_cache[key] = luminance >= 0.52
        return self._appearance_cache[key]

    def _dark_for_global_logical(self, point: QPoint) -> bool:
        primary = QApplication.primaryScreen()
        ratio = primary.devicePixelRatio() if primary is not None else 1.0
        for screen in QApplication.screens():
            if screen.geometry().contains(point):
                ratio = screen.devicePixelRatio()
                break
        x, y = point.x() * ratio, point.y() * ratio
        return self._dark_for_physical(x, y)

    @staticmethod
    def _palette_colors(dark: bool) -> tuple[QColor, QColor, QColor]:
        if dark:
            return QColor(30, 30, 32, 199), QColor("#F5F5F7"), QColor(255, 255, 255, 41)
        return QColor(250, 250, 252, 204), QColor("#1D1D1F"), QColor(0, 0, 0, 20)

    def _draw_glass_card(self, painter: QPainter, rect: QRectF, radius: float, dark: bool) -> None:
        painter.save()
        shadow = rect.translated(0, 8)
        for width, alpha in ((24, 3), (18, 5), (12, 8), (6, 13), (2, 22)):
            painter.setPen(
                QPen(
                    QColor(0, 0, 0, alpha),
                    width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            inset = width / 2
            painter.drawRoundedRect(
                shadow.adjusted(-inset, -inset, inset, inset),
                radius + inset,
                radius + inset,
            )
        fill, _label, hairline = self._palette_colors(dark)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(hairline, 1))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        painter.restore()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = time.monotonic()
        if self._marks_visible:
            for mark in self._marks:
                age = now - mark.created
                opacity = max(0.0, min(1.0, (mark.ttl - age) / 1.2))
                if self._reduced_motion:
                    opacity *= min(1.0, age / 0.15)
                    progress = 1.0
                else:
                    opacity *= min(1.0, age / 0.12)
                    progress = 1 - (1 - min(1.0, age / 0.32)) ** 3
                painter.save()
                painter.setOpacity(opacity)
                if isinstance(mark.command, (CircleCommand, ArrowCommand, LinkCommand, UnderlineCommand, PointCommand)):
                    self._paint_mark(painter, mark.command, progress, age, outline=True)
                self._paint_mark(painter, mark.command, progress, age)
                painter.restore()
        self._paint_status(painter, now)
        painter.end()

    def _paint_mark(
        self,
        painter: QPainter,
        command: object,
        progress: float,
        age: float,
        outline: bool = False,
    ) -> None:
        color = QColor(0, 0, 0, 71) if outline else ACCENT
        pen = QPen(
            color,
            5 if outline else 3,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        if isinstance(command, LinkCommand):
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if isinstance(command, CircleCommand):
            rect = self._rect(command.rect)
            path = QPainterPath()
            points = 72
            end_angle = 2 * math.pi * min(1.0, progress)
            if progress >= 1:
                end_angle += math.radians(8)
            for index in range(points + 1):
                angle = end_angle * index / points
                wobble = math.sin(angle * 5 + age * 3) * 1.2 if age < 0.32 else 0
                x = rect.center().x() + (rect.width() / 2 + wobble) * math.cos(angle)
                y = rect.center().y() + (rect.height() / 2 + wobble) * math.sin(angle)
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        elif isinstance(command, (ArrowCommand, LinkCommand)):
            start, end = self._point(command.start), self._point(command.end)
            dx, dy = end[0] - start[0], end[1] - start[1]
            distance = max(1.0, math.hypot(dx, dy))
            bend = min(36.0, distance * 0.12)
            control = (
                start[0] + dx * 0.5 - dy / distance * bend,
                start[1] + dy * 0.5 + dx / distance * bend,
            )
            path = QPainterPath()
            path.moveTo(*start)
            path.quadTo(*control, *end)
            self._draw_progress_path(painter, path, progress)
            if isinstance(command, ArrowCommand) and progress >= 1:
                angle = math.atan2(end[1] - control[1], end[0] - control[0])
                head = QPainterPath()
                head.moveTo(*end)
                head.lineTo(end[0] - 12 * math.cos(angle - 0.45), end[1] - 12 * math.sin(angle - 0.45))
                head.moveTo(*end)
                head.lineTo(end[0] - 12 * math.cos(angle + 0.45), end[1] - 12 * math.sin(angle + 0.45))
                painter.drawPath(head)
            if isinstance(command, LinkCommand) and command.label and progress >= 1 and not outline:
                self._draw_label_card(painter, command.label, QPointF(*control))
        elif isinstance(command, UnderlineCommand):
            rect = self._rect(command.rect)
            end_x = rect.left() + rect.width() * progress
            path = QPainterPath()
            path.moveTo(rect.left(), rect.bottom())
            path.quadTo((rect.left() + end_x) / 2, rect.bottom() + 2, end_x, rect.bottom())
            painter.drawPath(path)
        elif isinstance(command, HighlightCommand):
            if outline:
                return
            rect = self._rect(command.rect)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), 46))
            painter.drawRoundedRect(
                QRectF(rect.x(), rect.y(), rect.width() * progress, rect.height()),
                8,
                8,
            )
        elif isinstance(command, PointCommand):
            x, y = self._point(command.rect.center)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if age < 1.2:
                phase = (age % 0.6) / 0.6
                ring = 7 + phase * 18
                ring_pen = QPen(
                    QColor(ACCENT.red(), ACCENT.green(), ACCENT.blue(), round(170 * (1 - phase))),
                    1 if outline else 1.5,
                )
                painter.setPen(ring_pen)
                painter.drawEllipse(QPointF(x, y), ring, ring)
            painter.setPen(QPen(QColor(0, 0, 0, 71) if outline else ACCENT, 1))
            painter.setBrush(ACCENT)
            painter.drawEllipse(QPointF(x, y), 5, 5)
            if command.label and not outline:
                self._draw_label_card(painter, command.label, QPointF(x + 12, y))
        elif isinstance(command, NoteCommand):
            if outline:
                return
            rect = self._rect(command.rect)
            font = QFont(self._font_family)
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            width = min(300.0, max(74.0, metrics.horizontalAdvance(command.text) + 22))
            card = QRectF(rect.x(), rect.y() - 36, width, 28)
            dark = self._dark_for_physical(
                command.rect.x + command.rect.w / 2,
                command.rect.y + command.rect.h / 2,
            )
            self._draw_glass_card(painter, card, 10, dark)
            _fill, label, _hairline = self._palette_colors(dark)
            painter.setPen(label)
            painter.drawText(card.adjusted(11, 0, -11, 0), Qt.AlignmentFlag.AlignVCenter, command.text)

    @staticmethod
    def _draw_progress_path(painter: QPainter, path: QPainterPath, progress: float) -> None:
        steps = max(1, int(100 * progress))
        partial = QPainterPath()
        partial.moveTo(path.pointAtPercent(0))
        for index in range(1, steps + 1):
            partial.lineTo(path.pointAtPercent(min(1.0, index / 100)))
        painter.drawPath(partial)

    def _draw_label_card(self, painter: QPainter, text: str, point: QPointF) -> None:
        font = QFont(self._font_family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 18
        rect = QRectF(point.x() - width / 2, point.y() - 16, width, 28)
        self._draw_glass_card(painter, rect, 10, self._dark_for_widget_rect(rect))
        _fill, label, _hairline = self._palette_colors(self._dark_for_widget_rect(rect))
        painter.setPen(label)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _dark_for_widget_rect(self, rect: QRectF) -> bool:
        x, y = self._widget_to_physical(rect.center().x(), rect.center().y())
        return self._dark_for_physical(x, y)

    def _local_available_geometry(self):
        screen = QApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else self.rect()
        area.translate(-self.geometry().x(), -self.geometry().y())
        local = area.intersected(self.rect())
        return local if not local.isEmpty() else self.rect()

    def _caption_lines(self, width: int = 560) -> list[str]:
        if not self._caption:
            return []
        font = QFont(self._font_family)
        font.setPixelSize(15)
        metrics = QFontMetrics(font)
        lines: list[str] = []
        line = ""
        for word in self._caption.split():
            word = metrics.elidedText(word, Qt.TextElideMode.ElideRight, width)
            candidate = f"{line} {word}".strip()
            if line and metrics.horizontalAdvance(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines[-2:]

    def _paint_status(self, painter: QPainter, now: float) -> None:
        caption_age = now - self._caption_time
        caption_active = bool(self._caption) and caption_age < 6
        if self._status == "idle" and not caption_active and not self._status_visible:
            return
        age = now - self._status_changed
        if self._status == "idle":
            status_alpha = max(0.0, 1 - age / 0.15)
            caption_alpha = max(0.0, 1 - caption_age / 6) if caption_active else 0.0
            alpha = max(status_alpha, caption_alpha)
            scale = 1.0
            if alpha <= 0:
                self._status_visible = False
        else:
            duration = 0.15 if self._reduced_motion else 0.2
            amount = min(1.0, age / duration)
            alpha = 1 - (1 - amount) ** 3
            scale = 0.96 + 0.04 * alpha
        if alpha <= 0:
            return
        lines = self._caption_lines()
        caption_font = QFont(self._font_family)
        caption_font.setPixelSize(15)
        line_width = max((QFontMetrics(caption_font).horizontalAdvance(line) for line in lines), default=0)
        area = self._local_available_geometry()
        width = min(area.width() - 24, max(210, int(min(560, line_width) + 132)))
        height = 50 + (38 if lines else 0)
        pill = QRectF(
            area.center().x() - width / 2,
            area.bottom() - 24 - height,
            width,
            height,
        )
        painter.save()
        painter.setOpacity(alpha)
        painter.translate(pill.center())
        painter.scale(scale, scale)
        painter.translate(-pill.center())
        dark = self._dark_for_widget_rect(pill)
        self._draw_glass_card(painter, pill, height / 2, dark)
        _fill, label_color, _hairline = self._palette_colors(dark)
        font = QFont(self._font_family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        label = self._status_message or {
            "listening": "Écoute",
            "thinking": "Réflexion",
            "speaking": "Gerald parle",
            "error": "audio indisponible",
        }.get(self._status, "")
        painter.setPen(label_color)
        painter.drawText(
            QRectF(pill.left() + 18, pill.top() + 6, pill.width() - 72, 22),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        if self._status == "listening":
            self._draw_level_bars(painter, pill, ACCENT, self._mic_level)
        elif self._status == "speaking":
            self._draw_level_bars(painter, pill, label_color, self._output_level)
        elif self._status == "thinking":
            self._draw_thinking_dots(painter, pill, label_color, now)
        if lines:
            caption_font = QFont(self._font_family)
            caption_font.setPixelSize(15)
            caption_font.setWeight(QFont.Weight.Normal)
            painter.setFont(caption_font)
            painter.setPen(label_color)
            painter.drawText(
                pill.adjusted(18, 32, -18, -4),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                "\n".join(lines),
            )
        painter.restore()

    def closeEvent(self, event) -> None:
        self._text_input.close()
        super().closeEvent(event)

    @staticmethod
    def _draw_level_bars(
        painter: QPainter,
        pill: QRectF,
        color: QColor,
        level: float,
    ) -> None:
        center_x = pill.right() - 25
        center_y = pill.top() + 17
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        heights = (0.45, 0.7, 1.0, 0.75, 0.5)
        for index in range(5):
            height = 3 + 14 * level * heights[index]
            bar = QRectF(center_x - 20 + index * 5, center_y - height / 2, 3, height)
            painter.drawRoundedRect(bar, 1.5, 1.5)

    @staticmethod
    def _draw_thinking_dots(painter: QPainter, pill: QRectF, color: QColor, now: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for index in range(3):
            amount = (math.sin(now * 7 - index * 0.9) + 1) / 2
            radius = 2.2 + amount * 1.4
            painter.drawEllipse(QPointF(pill.right() - 29 + index * 7, pill.center().y()), radius, radius)
