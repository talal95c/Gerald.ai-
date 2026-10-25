from __future__ import annotations

import math
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, QTimer, QPropertyAnimation
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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
    TipCommand,
    UnderlineCommand,
)
from gerald.tools.diagram import DiagramCommand
from gerald.tools.diagram_render import draw_diagram


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
logger = logging.getLogger(__name__)
_capture_exclusion_warning_logged = False
Rect = tuple[int, int, int, int]


def _confirmation_position(
    target: Rect,
    area: Rect,
    pill_size: tuple[int, int],
    gap: int = 12,
) -> tuple[int, int]:
    target_x, target_y, target_width, target_height = target
    area_x, area_y, area_width, area_height = area
    pill_width, pill_height = pill_size
    x = round(target_x + target_width / 2 - pill_width / 2)
    x = min(max(area_x, x), area_x + area_width - pill_width)
    below = target_y + target_height + gap
    y = below if below + pill_height <= area_y + area_height else target_y - gap - pill_height
    y = min(max(area_y, y), area_y + area_height - pill_height)
    return x, y


def _try_set_capture_exclusion(hwnd: int, user32) -> bool:
    global _capture_exclusion_warning_logged
    try:
        import ctypes

        ctypes.set_last_error(0)
    except Exception:
        ctypes = None
    try:
        result = user32.SetWindowDisplayAffinity(hwnd, 0x11)
    except Exception:
        result = 0
    if result:
        return True
    if not _capture_exclusion_warning_logged:
        if ctypes is None:
            error = 0
        else:
            try:
                error = ctypes.windll.kernel32.GetLastError()
            except Exception:
                error = ctypes.get_last_error()
        logger.warning("SetWindowDisplayAffinity failed (GetLastError=%s)", error)
        _capture_exclusion_warning_logged = True
    return False


@dataclass(frozen=True)
class _ScreenMapping:
    physical: Rect
    logical: Rect
    ratio: float


def _build_screen_mappings(
    screens: list[tuple[str, Rect, float]],
    native_monitors: list[tuple[str, Rect]] | None = None,
) -> list[_ScreenMapping]:
    if not native_monitors:
        return [
            _ScreenMapping(
                (round(x * ratio), round(y * ratio), round(width * ratio), round(height * ratio)),
                (x, y, width, height),
                ratio,
            )
            for _name, (x, y, width, height), ratio in screens
        ]
    remaining = list(range(len(screens)))
    mappings = []
    for monitor_index, (name, physical) in enumerate(native_monitors):
        match = next(
            (index for index in remaining if screens[index][0].casefold() == name.casefold()),
            None,
        )
        if match is None:
            left, top, width, height = physical
            overlaps = []
            for index in remaining:
                _screen_name, (x, y, w, h), ratio = screens[index]
                projected = (round(x * ratio), round(y * ratio), round(w * ratio), round(h * ratio))
                area = max(0, min(left + width, projected[0] + projected[2]) - max(left, projected[0]))
                area *= max(0, min(top + height, projected[1] + projected[3]) - max(top, projected[1]))
                overlaps.append((area, index))
            best = max(overlaps, default=(0, -1))
            match = best[1] if best[0] else None
        if match is None and monitor_index in remaining:
            match = monitor_index
        if match is None:
            continue
        remaining.remove(match)
        _screen_name, logical, dpr = screens[match]
        ratio = physical[2] / max(1, logical[2]) or dpr
        mappings.append(_ScreenMapping(physical, logical, ratio))
    return mappings


def _physical_to_logical(
    x: float,
    y: float,
    mappings: list[_ScreenMapping],
) -> tuple[float, float, float] | None:
    for mapping in mappings:
        left, top, width, height = mapping.physical
        if left <= x < left + width and top <= y < top + height:
            logical_x, logical_y, _logical_width, _logical_height = mapping.logical
            return (
                logical_x + (x - left) / mapping.ratio,
                logical_y + (y - top) / mapping.ratio,
                mapping.ratio,
            )
    return None


def _logical_to_physical(
    x: float,
    y: float,
    mappings: list[_ScreenMapping],
) -> tuple[float, float] | None:
    for mapping in mappings:
        left, top, width, height = mapping.logical
        if left <= x < left + width and top <= y < top + height:
            physical_x, physical_y, _physical_width, _physical_height = mapping.physical
            return (
                physical_x + (x - left) * mapping.ratio,
                physical_y + (y - top) * mapping.ratio,
            )
    return None


def _native_windows_monitors() -> list[tuple[str, Rect]]:
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    class NativeRect(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", NativeRect),
            ("rcWork", NativeRect),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    found: list[tuple[str, Rect]] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(NativeRect), wintypes.LPARAM
    )

    def enumerate_monitor(handle, _dc, _rect, _data):
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if ctypes.windll.user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            rect = info.rcMonitor
            found.append((info.szDevice, (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)))
        return True

    callback = callback_type(enumerate_monitor)
    ctypes.windll.user32.EnumDisplayMonitors(0, None, callback, 0)
    return found


def _screen_mappings() -> list[_ScreenMapping]:
    screens = [
        (
            screen.name(),
            (screen.geometry().x(), screen.geometry().y(), screen.geometry().width(), screen.geometry().height()),
            screen.devicePixelRatio(),
        )
        for screen in QApplication.screens()
    ]
    platform_name = QApplication.platformName().casefold()
    native = _native_windows_monitors() if os.name == "nt" and platform_name != "offscreen" else None
    return _build_screen_mappings(screens, native)


def screen_mapping_for_qscreen(screen) -> _ScreenMapping | None:
    geometry = screen.geometry()
    logical = (geometry.x(), geometry.y(), geometry.width(), geometry.height())
    return next((mapping for mapping in _screen_mappings() if mapping.logical == logical), None)


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


class _ConfirmationPill(QWidget):
    def __init__(self, owner: OverlayWindow, text: str, finish) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.owner = owner
        self.finish = finish
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)
        self.setToolTip(text)
        display_text = text
        opening = text.find("«")
        closing = text.rfind("»")
        if opening >= 0 and closing > opening:
            inner = text[opening + 1 : closing].strip()
            if len(inner) > 120:
                inner = f"{inner[:59]}…{inner[-60:]}"
            display_text = f"{text[: opening + 1]}\u00a0{inner}\u00a0{text[closing:]}"
        display_text = display_text.replace("« ", "«\u00a0").replace(" »", "\u00a0»")
        self.label = QLabel(display_text, self)
        self.label.setToolTip(text)
        label_font = QFont(owner._font_family, 13, QFont.Weight.Medium)
        self.label.setFont(label_font)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("QLabel { background: transparent; color: #F5F5F7; }")
        self.label.setMaximumWidth(280)
        words = display_text.split(" ")
        metrics = QFontMetrics(label_font)
        lines = 1
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and metrics.horizontalAdvance(candidate) > 280:
                lines += 1
                line = word
            else:
                line = candidate
        self.setFixedSize(520, max(68, lines * metrics.lineSpacing() + 20))
        layout.addWidget(self.label, 1)
        self.buttons: list[tuple[QPushButton, bool]] = []
        for title, approved in (("Autoriser", True), ("Annuler", False)):
            button = QPushButton(title, self)
            button.setMinimumHeight(40)
            button.setFont(QFont(owner._font_family, 11, QFont.Weight.Medium))
            button.clicked.connect(lambda _checked=False, value=approved: self.finish(value))
            layout.addWidget(button)
            self.buttons.append((button, approved))
        QTimer.singleShot(15000, lambda: self.finish(False))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        dark = self.owner._dark_for_global_logical(self.frameGeometry().center())
        card = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(card, self.height() / 2, self.height() / 2)
        painter.save()
        painter.setClipPath(path)
        self.owner._draw_glass_card(painter, card, self.height() / 2, dark)
        painter.restore()
        _fill, label, _hairline = self.owner._palette_colors(dark)
        self.label.setStyleSheet(
            f"QLabel {{ background: transparent; color: {label.name()}; }}"
        )
        cancel_background = "rgba(255,255,255,0.12)" if dark else "rgba(0,0,0,0.06)"
        for button, approved in self.buttons:
            background = ACCENT.name() if approved else cancel_background
            foreground = "#1D1D1F" if approved else label.name()
            button.setStyleSheet(
                f"QPushButton {{ color: {foreground}; background: {background}; border: none; "
                "border-radius: 20px; padding: 0 14px; }"
                "QPushButton:hover { background: rgba(127,127,127,0.22); }"
            )
        painter.end()


class _SuggestionBubble(QWidget):
    def __init__(self, owner: OverlayWindow, text: str, choices, on_choice, ttl: float) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.owner = owner
        self.on_choice = on_choice
        self.tail_x = 0.5
        self.tail_up = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setToolTip(text)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 18)
        layout.setSpacing(8)
        self.label = QLabel(text, self)
        label_font = QFont(owner._font_family)
        label_font.setPixelSize(13)
        self.label.setFont(label_font)
        self.label.setWordWrap(True)
        self.label.setMaximumWidth(292)
        layout.addWidget(self.label)
        self.buttons: list[QPushButton] = []
        if choices:
            row = QHBoxLayout()
            row.addStretch(1)
            for index, choice in enumerate(choices):
                button = QPushButton(choice, self)
                button.setMinimumHeight(30)
                button_font = QFont(owner._font_family)
                button_font.setPixelSize(11)
                button_font.setWeight(QFont.Weight.Medium)
                button.setFont(button_font)
                button.setStyleSheet(
                    "QPushButton { color: white; background: #0A84FF; border: none; "
                    "border-radius: 15px; padding: 0 14px; }"
                    if index == 0
                    else "QPushButton { color: #0A84FF; background: transparent; border: none; "
                    "border-radius: 15px; padding: 0 14px; }"
                )
                button.clicked.connect(lambda _checked=False, value=choice: owner.dismiss_bubble(value))
                row.addWidget(button)
                self.buttons.append(button)
            layout.addLayout(row)
        self.setMaximumWidth(320)
        self.adjustSize()
        self.setWindowOpacity(0.0)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._ttl = QTimer(self)
        self._ttl.setSingleShot(True)
        self._ttl.timeout.connect(owner.dismiss_bubble)
        self._ttl.start(max(1, round(ttl * 1000)))

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(self.rect()).adjusted(2, 2, -2, -9)
        for outset, alpha in ((10, 3), (8, 4), (6, 5), (4, 6), (2, 7)):
            shadow = card.translated(0, 3).adjusted(-outset, -outset, outset, outset)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(shadow, 14 + outset, 14 + outset)
        fill = QColor(255, 255, 255, 250)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(card, 14, 14)
        path = QPainterPath()
        center = self.width() * self.tail_x
        if self.tail_up:
            path.moveTo(center - 7, 9)
            path.lineTo(center, 0)
            path.lineTo(center + 7, 9)
        else:
            path.moveTo(center - 7, self.height() - 18)
            path.lineTo(center, self.height() - 2)
            path.lineTo(center + 7, self.height() - 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPath(path)
        painter.end()


class OverlayWindow(QWidget):
    def __init__(self, cursor_enabled: bool | None = None) -> None:
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
        self._diagrams: list[dict] = []
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
        self._cursor_enabled = (
            os.getenv("GERALD_CURSOR", "1").strip().casefold() not in {"0", "false", "no", "off"}
            if cursor_enabled is None
            else cursor_enabled
        )
        mouse = QCursor.pos()
        self._mouse_position = QPointF(mouse.x(), mouse.y())
        self._cursor_position = QPointF(mouse.x() + 18, mouse.y() + 14)
        self._cursor_target = QPointF(self._cursor_position)
        self._cursor_flight: tuple[QPointF, QPointF, float] | None = None
        self._cursor_hold_until = 0.0
        self._cursor_target_rect: QRectF | None = None
        self._cursor_poll_timer = QTimer(self)
        self._cursor_poll_timer.setInterval(30)
        self._cursor_poll_timer.timeout.connect(self._poll_cursor_position)
        if self._cursor_enabled:
            self._cursor_poll_timer.start()
        self._bubble: _SuggestionBubble | None = None
        self._bubble_choice = None
        self._font_family = _system_font_family()
        self._text_input_submit = None
        self._text_input_cancel = None
        self._text_input = _GlassTextInput(self)
        self._confirmation: _ConfirmationPill | None = None
        self._confirmation_token: str | None = None
        self._confirmation_completion = None
        self._confirmation_result = None
        self._expired_confirmation_tokens: set[str] = set()
        self.capture_excluded = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timed_error_timer = QTimer(self)
        self._timed_error_timer.setSingleShot(True)
        self._timed_error_timer.timeout.connect(self._expire_timed_error)
        self._timed_error_message: str | None = None
        self._recent_timed_errors: dict[str, float] = {}
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
            self.capture_excluded = _try_set_capture_exclusion(hwnd, ctypes.windll.user32)
        except Exception:
            self.capture_excluded = False

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
        level_only: bool = False,
    ) -> None:
        if level_only and (
            self._timed_error_timer.isActive() or self._status == "offline"
        ):
            return
        if self._timed_error_timer.isActive() and (
            status != "error" or message != self._timed_error_message
        ):
            self._timed_error_timer.stop()
            self._timed_error_message = None
        if status != self._status:
            self._status_changed = time.monotonic()
        if status != "idle" or self._status != "idle":
            self._status_visible = True
        self._status = status
        self._status_message = message or ""
        self.setToolTip(message or "")
        if mic_level is not None:
            self._mic_level = max(0.0, min(1.0, mic_level))
        if output_level is not None:
            self._output_level = max(0.0, min(1.0, output_level))
        if status != "idle":
            self._ensure_timer()
        self.update()

    def show_timed_error(self, message: str, duration_ms: int = 5000) -> bool:
        now = time.monotonic()
        self._recent_timed_errors = {
            text: shown_at
            for text, shown_at in self._recent_timed_errors.items()
            if now - shown_at < 30
        }
        if (
            (self._status == "error" and self._status_message == message)
            or message in self._recent_timed_errors
        ):
            return False
        self._recent_timed_errors[message] = now
        self.show()
        self._timed_error_message = message
        self.set_status("error", message=message)
        self._timed_error_timer.start(duration_ms)
        return True

    def _expire_timed_error(self) -> None:
        if (
            self._status == "error"
            and self._timed_error_message is not None
            and self._status_message == self._timed_error_message
        ):
            self._timed_error_message = None
            self.set_status("idle")

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
                self._diagrams.clear()
                self._cursor_target_rect = None
                self._start_cursor_flight(self._mouse_position + QPointF(18, 14), now, 0.0)
            elif isinstance(command, TipCommand):
                self.show_bubble(command.text)
            elif isinstance(command, DiagramCommand):
                self._diagrams.append(self._diagram_state(command, now, 30.0))
            else:
                self._marks.append(_Mark(command, now, ttl))
                target = self._cursor_target_for(command)
                if target is not None:
                    self._cursor_target_rect = self._cursor_rect_for(command)
                    self._start_cursor_flight(target, now, now + ttl)
        self._ensure_timer()
        self.update()

    def _diagram_state(self, command: DiagramCommand, now: float, ttl: float) -> dict:
        layout = command.layout
        screen = QApplication.screenAt(QPoint(round(self._cursor_position.x()), round(self._cursor_position.y())))
        screen = screen or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else self.geometry()
        max_w, max_h = area.width() * 0.46, area.height() * 0.46
        scale = max(0.85, min(1.0, max_w / max(1, layout.width), max_h / max(1, layout.height)))
        width, height = layout.width * scale, layout.height * scale
        cursor = self._cursor_position
        quadrants = [
            QRectF(area.left(), area.top(), area.width() / 2, area.height() / 2),
            QRectF(area.center().x(), area.top(), area.width() / 2, area.height() / 2),
            QRectF(area.left(), area.center().y(), area.width() / 2, area.height() / 2),
            QRectF(area.center().x(), area.center().y(), area.width() / 2, area.height() / 2),
        ]
        quadrant = max(quadrants, key=lambda rect: (rect.center().x() - cursor.x()) ** 2 + (rect.center().y() - cursor.y()) ** 2)
        x = min(max(quadrant.left(), quadrant.center().x() - width / 2), area.x() + area.width() - width)
        y = min(max(quadrant.top(), quadrant.center().y() - height / 2), area.y() + area.height() - height)
        x = max(area.left(), x)
        y = max(area.top(), y)
        return {"command": command, "created": now, "ttl": ttl, "x": x, "y": y, "scale": scale}

    def _cursor_target_for(self, command: object) -> QPointF | None:
        if isinstance(command, (CircleCommand, NoteCommand, HighlightCommand, UnderlineCommand)):
            rect = command.rect
            left, top = self._point((rect.x, rect.y))
            right, bottom = self._point((rect.x + rect.w, rect.y + rect.h))
            return QPointF(
                self.geometry().x() + (left + right) / 2 - 20,
                self.geometry().y() + bottom + 10,
            )
        point = command.end if isinstance(command, ArrowCommand) else (
            command.rect.center if isinstance(command, PointCommand) else None
        )
        if point is None:
            return None
        x, y = self._point(point)
        return QPointF(self.geometry().x() + x, self.geometry().y() + y)

    def _cursor_rect_for(self, command: object) -> QRectF | None:
        if not isinstance(command, (CircleCommand, NoteCommand, HighlightCommand, UnderlineCommand)):
            return None
        rect = command.rect
        left, top = self._point((rect.x, rect.y))
        right, bottom = self._point((rect.x + rect.w, rect.y + rect.h))
        return QRectF(
            self.geometry().x() + left,
            self.geometry().y() + top,
            right - left,
            bottom - top,
        )

    def _start_cursor_flight(self, target: QPointF, now: float, hold_until: float) -> None:
        if not self._cursor_enabled:
            return
        self._cursor_target = QPointF(target)
        self._cursor_flight = (QPointF(self._cursor_position), QPointF(target), now)
        self._cursor_hold_until = hold_until
        self._ensure_timer()

    def set_mouse_position(self, x: float, y: float, physical: bool = True) -> None:
        if physical:
            mapped = self._global_physical_to_logical(x, y)
            if mapped is not None:
                x, y = mapped[:2]
        new_position = QPointF(x, y)
        if new_position == self._mouse_position:
            return
        self._mouse_position = new_position
        if not self._cursor_enabled and self._bubble is None:
            return
        if time.monotonic() >= self._cursor_hold_until:
            self._cursor_target = self._mouse_position + QPointF(18, 14)
        self._ensure_timer()

    def _poll_cursor_position(self) -> None:
        if not self._cursor_enabled and self._bubble is None:
            self._cursor_poll_timer.stop()
            return
        position = QCursor.pos()
        self.set_mouse_position(position.x(), position.y(), physical=False)

    def show_bubble(
        self,
        text: str,
        choices: list[str] | None = None,
        on_choice: Callable[[str | None], None] | None = None,
        ttl: float = 8.0,
    ) -> None:
        self.dismiss_bubble()
        bubble = _SuggestionBubble(self, text, choices, on_choice, ttl)
        self._bubble = bubble
        self._bubble_choice = on_choice
        if not self._cursor_poll_timer.isActive():
            self._cursor_poll_timer.start()
        self._position_bubble()
        final_geometry = bubble.geometry()
        bubble.setGeometry(final_geometry.adjusted(0, 5, 0, 5))
        bubble.show()
        bubble.raise_()
        bubble._fade.start()
        bubble._rise = QPropertyAnimation(bubble, b"geometry", bubble)
        bubble._rise.setDuration(180)
        bubble._rise.setStartValue(bubble.geometry())
        bubble._rise.setEndValue(final_geometry)
        bubble._rise.start()
        self._ensure_timer()

    def dismiss_bubble(self, choice: str | None = None) -> None:
        bubble = self._bubble
        if bubble is None:
            return
        callback = self._bubble_choice
        self._bubble = None
        self._bubble_choice = None
        bubble._ttl.stop()
        bubble.close()
        if not self._cursor_enabled:
            self._cursor_poll_timer.stop()
        if callback is not None:
            callback(choice)

    def has_bubble(self) -> bool:
        return self._bubble is not None

    def _position_bubble(self) -> None:
        bubble = self._bubble
        if bubble is None:
            return
        cursor = self._cursor_position
        anchor = cursor + QPointF(8, 8)
        screen = QApplication.screenAt(QPoint(round(cursor.x()), round(cursor.y()))) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else self.geometry()
        max_x = area.x() + area.width() - bubble.width()
        max_y = area.y() + area.height() - bubble.height()
        candidates = [
            (round(anchor.x() + 8), round(anchor.y()), True),
            (round(anchor.x() - bubble.width() - 8), round(anchor.y()), True),
            (round(anchor.x() - bubble.width() / 2), round(anchor.y() - bubble.height()), False),
        ]
        if self._cursor_target_rect is not None:
            target = self._cursor_target_rect
            candidates.extend(
                [
                    (round(target.right() + 8), round(target.center().y() - bubble.height() / 2), True),
                    (round(target.left() - bubble.width() - 8), round(target.center().y() - bubble.height() / 2), True),
                    (round(target.center().x() - bubble.width() / 2), round(target.top() - bubble.height() - 8), False),
                    (round(target.center().x() - bubble.width() / 2), round(target.bottom() + 8), True),
                ]
            )
        target = self._cursor_target_rect
        selected = None
        for candidate_x, candidate_y, tail_up in candidates:
            candidate_x = max(area.left(), min(max_x, candidate_x))
            candidate_y = max(area.top(), min(max_y, candidate_y))
            candidate = QRectF(candidate_x, candidate_y, bubble.width(), bubble.height())
            if target is None or not candidate.intersects(target):
                selected = (candidate_x, candidate_y, tail_up)
                break
        if selected is None and target is not None:
            candidate_x = max(area.left(), min(max_x, round(target.right() + 8)))
            candidate_y = max(area.top(), min(max_y, round(target.bottom() + 8)))
            candidate = QRectF(candidate_x, candidate_y, bubble.width(), bubble.height())
            if not candidate.intersects(target):
                selected = (candidate_x, candidate_y, True)
        if selected is None:
            candidate_x = max(area.left(), min(max_x, round(anchor.x() - bubble.width() / 2)))
            candidate_y = max(area.top(), min(max_y, round(anchor.y() - bubble.height())))
            selected = (candidate_x, candidate_y, False)
        x, y, bubble.tail_up = selected
        bubble.move(x, y)
        bubble.tail_x = min(0.975, max(0.025, (anchor.x() - x) / max(1, bubble.width())))
        bubble.update()

    def set_marks_visible(self, visible: bool) -> None:
        self._marks_visible = visible
        self.update()

    def show_confirmation(self, text, target_rect, completion, result, token=None) -> None:
        self.dismiss_confirmation()
        token = token or uuid.uuid4().hex
        self._expired_confirmation_tokens.discard(token)
        holder: dict[str, _ConfirmationPill] = {}

        def finish(approved: bool) -> None:
            pill = holder.get("pill")
            if (
                pill is None
                or self._confirmation is not pill
                or self._confirmation_token != token
                or token in self._expired_confirmation_tokens
                or result.get("expired")
            ):
                return
            result["approved"] = approved
            completion.set()
            self._confirmation = None
            self._confirmation_token = None
            self._confirmation_completion = None
            self._confirmation_result = None
            pill.close()

        pill = _ConfirmationPill(self, text, finish)
        holder["pill"] = pill
        self._confirmation = pill
        self._confirmation_token = token
        self._confirmation_completion = completion
        self._confirmation_result = result
        if target_rect is None:
            from PyQt6.QtGui import QCursor

            cursor = QCursor.pos()
            target = (cursor.x(), cursor.y(), 0, 0)
        else:
            left, top, width, height = target_rect
            mapped_top = self._global_physical_to_logical(left, top)
            mapped_bottom = self._global_physical_to_logical(left + width, top + height)
            if mapped_top is None or mapped_bottom is None:
                ratio = QApplication.primaryScreen().devicePixelRatio()
                mapped_top = (left / ratio, top / ratio, ratio)
                mapped_bottom = ((left + width) / ratio, (top + height) / ratio, ratio)
            target = (
                round(mapped_top[0]),
                round(mapped_top[1]),
                max(1, round(mapped_bottom[0] - mapped_top[0])),
                max(1, round(mapped_bottom[1] - mapped_top[1])),
            )
        center = QPoint(round(target[0] + target[2] / 2), round(target[1] + target[3] / 2))
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            x, y = _confirmation_position(
                target,
                (area.x(), area.y(), area.width(), area.height()),
                (pill.width(), pill.height()),
            )
        else:
            x, y = target[0], target[1] + target[3] + 12
        pill.move(x, y)
        pill.show()
        pill.raise_()

    def dismiss_confirmation(self) -> bool:
        if self._confirmation is None:
            return False
        pill = self._confirmation
        pill.finish(False)
        return True

    def expire_confirmation(self, token: str) -> None:
        self._expired_confirmation_tokens.add(token)
        if token != self._confirmation_token:
            return
        if self._confirmation_result is not None:
            self._confirmation_result["expired"] = True
            self._confirmation_result["approved"] = False
        if self._confirmation_completion is not None:
            self._confirmation_completion.set()
        pill = self._confirmation
        self._confirmation = None
        self._confirmation_token = None
        self._confirmation_completion = None
        self._confirmation_result = None
        if pill is not None:
            pill.close()

    def has_confirmation(self) -> bool:
        return self._confirmation is not None

    def clear(self) -> None:
        self.dismiss_bubble()
        self._marks.clear()
        self._diagrams.clear()
        self._start_cursor_flight(self._mouse_position + QPointF(18, 14), time.monotonic(), 0.0)
        self._status = "idle"
        self._status_visible = False
        self._status_changed = time.monotonic()
        self.update()

    def _ensure_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start(16)

    def _cursor_update_rect(self, position: QPointF) -> QRect:
        local_x = position.x() - self.geometry().x()
        local_y = position.y() - self.geometry().y()
        margin = 28
        return QRect(
            round(local_x) - margin,
            round(local_y) - margin,
            margin * 2,
            margin * 2,
        )

    def _tick(self) -> None:
        now = time.monotonic()
        previous_cursor_position = QPointF(self._cursor_position)
        previous_mark_count = len(self._marks)
        previous_diagram_count = len(self._diagrams)
        self._marks = [mark for mark in self._marks if now - mark.created < mark.ttl]
        self._diagrams = [item for item in self._diagrams if now - item["created"] < item["ttl"]]
        cursor_animating = False
        track_pointer = self._cursor_enabled or self._bubble is not None
        if track_pointer and self._cursor_hold_until and now >= self._cursor_hold_until:
            self._cursor_target_rect = None
            self._start_cursor_flight(self._mouse_position + QPointF(18, 14), now, 0.0)
        if not track_pointer:
            self._cursor_flight = None
        elif self._cursor_flight is not None:
            start, end, started = self._cursor_flight
            progress = min(1.0, max(0.0, (now - started) / 0.35))
            eased = 1 - (1 - progress) ** 3
            self._cursor_position = start + (end - start) * eased
            cursor_animating = progress < 1.0
            if progress >= 1.0:
                self._cursor_position = end
                self._cursor_flight = None
                if not self._cursor_hold_until:
                    self._cursor_target = self._mouse_position + QPointF(18, 14)
        elif now < self._cursor_hold_until:
            self._cursor_position = QPointF(self._cursor_target)
        else:
            target = self._mouse_position + QPointF(18, 14)
            delta = target - self._cursor_position
            if math.hypot(delta.x(), delta.y()) > 0.5:
                self._cursor_position += delta * 0.32
                cursor_animating = True
        if self._bubble is not None:
            self._position_bubble()
        visual_animating = (
            any(
                now - mark.created < 0.32
                or (isinstance(mark.command, PointCommand) and now - mark.created < 1.2)
                for mark in self._marks
            )
            and not self._reduced_motion
        )
        visual_animating = visual_animating or any(
            now - item["created"] < len(item["command"].layout.nodes) * 0.09 + 0.2
            for item in self._diagrams
        )
        status_age = now - self._status_changed
        visual_animating = visual_animating or (
            self._status in {"listening", "thinking"}
            or (
                self._status not in {"idle", "offline"}
                and status_age < (0.15 if self._reduced_motion else 0.2)
            )
            or (self._status == "idle" and status_age < 0.15)
        )
        caption_active = bool(self._caption) and now - self._caption_time < 6
        visual_animating = visual_animating or caption_active
        animating = visual_animating or (cursor_animating and not self._reduced_motion)
        if animating and self._timer.interval() != 16:
            self._timer.start(16)
        elif self._marks or self._diagrams or caption_active or self._status not in {"idle", "offline"}:
            if self._timer.interval() != 200:
                self._timer.start(200)
        else:
            self._timer.stop()
        cursor_moved = self._cursor_position != previous_cursor_position
        content_expired = (
            len(self._marks) != previous_mark_count
            or len(self._diagrams) != previous_diagram_count
        )
        if visual_animating or content_expired:
            self.update()
        elif cursor_moved:
            region = self._cursor_update_rect(previous_cursor_position).united(
                self._cursor_update_rect(self._cursor_position)
            )
            self.update(region)

    def _screen_mappings(self) -> list[_ScreenMapping]:
        return _screen_mappings()

    def _global_physical_to_logical(self, x: float, y: float) -> tuple[float, float, float] | None:
        return _physical_to_logical(x, y, self._screen_mappings())

    def _qt_position(self, x: float, y: float) -> tuple[float, float, float]:
        mapped = self._global_physical_to_logical(x, y)
        if mapped is not None:
            logical_x, logical_y, ratio = mapped
            return logical_x - self.geometry().x(), logical_y - self.geometry().y(), ratio
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
        mapped = _logical_to_physical(logical_x, logical_y, self._screen_mappings())
        if mapped is not None:
            return mapped
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
        for item in self._diagrams:
            age = now - item["created"]
            opacity = min(1.0, max(0.0, (item["ttl"] - age) / 1.2))
            painter.save()
            painter.setOpacity(opacity)
            draw_diagram(
                painter,
                item["command"].layout,
                item["x"] - self.geometry().x(),
                item["y"] - self.geometry().y(),
                item["scale"],
                age,
                self._font_family,
            )
            painter.restore()
        self._paint_status(painter, now)
        if self._cursor_enabled:
            self._paint_cursor(painter, now)
        painter.end()

    def _paint_cursor(self, painter: QPainter, now: float) -> None:
        position = QPointF(
            self._cursor_position.x() - self.geometry().x(),
            self._cursor_position.y() - self.geometry().y(),
        )
        painter.save()
        pulse = self._status in {"listening", "thinking"}
        if pulse:
            phase = (now % 1.1) / 1.1
            painter.setPen(QPen(QColor(10, 132, 255, round(90 * (1 - phase))), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            center = position + QPointF(8, 8)
            painter.drawEllipse(center, 9 + phase * 7, 9 + phase * 7)
        path = QPainterPath()
        path.moveTo(0, 0)
        path.quadTo(1, -0.2, 2.5, 0.5)
        path.lineTo(15, 7)
        path.quadTo(16, 7.5, 15, 9)
        path.lineTo(8, 10.5)
        path.lineTo(6.2, 15.5)
        path.quadTo(5.5, 17, 4.2, 15.3)
        path.lineTo(0, 1.5)
        path.quadTo(-0.2, 0.3, 0, 0)
        path.closeSubpath()
        painter.translate(position)
        painter.rotate(-20)
        painter.save()
        painter.translate(0, 1)
        painter.scale(1.08, 1.08)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.drawPath(path)
        painter.restore()
        painter.setPen(QPen(QColor("white"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor("#0A84FF"))
        painter.drawPath(path)
        painter.restore()

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

    def _status_label_layout(
        self,
        label: str,
        available_width: int,
        caption_width: int,
        level_indicators: bool,
    ) -> tuple[int, str]:
        font = QFont(self._font_family)
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Medium)
        metrics = QFontMetrics(font)
        horizontal_padding = 72 if level_indicators else 36
        max_width = min(520, max(1, available_width - 24))
        caption_requirement = int(min(560, caption_width) + 132) if caption_width else 0
        required_width = max(
            210,
            metrics.horizontalAdvance(label) + horizontal_padding,
            caption_requirement,
        )
        width = min(max_width, required_width)
        label_width = max(1, width - horizontal_padding)
        return width, metrics.elidedText(label, Qt.TextElideMode.ElideMiddle, label_width)

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
            alpha = 0.62 if self._status == "offline" else 1 - (1 - amount) ** 3
            scale = 1.0 if self._status == "offline" else 0.96 + 0.04 * alpha
        if alpha <= 0:
            return
        lines = self._caption_lines()
        caption_font = QFont(self._font_family)
        caption_font.setPixelSize(15)
        line_width = max((QFontMetrics(caption_font).horizontalAdvance(line) for line in lines), default=0)
        area = self._local_available_geometry()
        label = self._status_message or {
            "listening": "Écoute",
            "thinking": "Réflexion",
            "speaking": "Gerald parle",
            "error": "audio indisponible",
            "offline": "Hors ligne",
        }.get(self._status, "")
        level_indicators = self._status in {"listening", "speaking"}
        width, label = self._status_label_layout(
            label,
            area.width(),
            line_width,
            level_indicators,
        )
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
        painter.setPen(label_color)
        label_width = max(1, width - (72 if level_indicators else 36))
        painter.drawText(
            QRectF(pill.left() + 18, pill.top() + 6, label_width, 22),
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
