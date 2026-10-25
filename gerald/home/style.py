from __future__ import annotations

import os

from math import cos, pi, sin

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QWidget

TOKENS = {
    "colors": {
        "background": "#FAFAFA",
        "surface": "#FFFFFF",
        "ink": "#0F0F0F",
        "secondary": "rgba(15, 15, 15, 0.62)",
        "tertiary": "rgba(15, 15, 15, 0.40)",
        "hairline": "rgba(15, 15, 15, 0.08)",
        "inactive": "#EDEDED",
        "hover": "#E4E4E4",
        "primary": "#0F0F0F",
        "primary_text": "#FAFAFA",
        "focus": "#0A84FF",
        "signal": "#2BEE19",
        "error": "#FF3B30",
    },
    "radii": {
        "panel": 24,
        "row": 14,
        "input": 12,
        "pill": 100,
    },
    "motion": {
        "page_fade_ms": 220,
        "card_stagger_ms": 30,
        "hover_ms": 150,
        "mascot_cycle_ms": 2400,
        "background_cycle_ms": 20000,
    },
    "glass": {
        "panel_alpha": 190,
        "backdrop_scale": 0.16,
    },
}

# Palette tokens for surfaces, text, focus, and status.
BG = TOKENS["colors"]["background"]
SURFACE = TOKENS["colors"]["surface"]
TEXT = TOKENS["colors"]["ink"]
SECONDARY = TOKENS["colors"]["secondary"]
TERTIARY = TOKENS["colors"]["tertiary"]
SEPARATOR = TOKENS["colors"]["hairline"]
INACTIVE = TOKENS["colors"]["inactive"]
HOVER = TOKENS["colors"]["hover"]
SIDEBAR = "rgba(255, 255, 255, 0.70)"
ACCENT = TOKENS["colors"]["primary"]
ACCENT_PRESSED = "#262626"
ACCENT_SOFT = "rgba(15, 15, 15, 0.06)"
FOCUS = TOKENS["colors"]["focus"]
SIGNAL = TOKENS["colors"]["signal"]
DANGER = TOKENS["colors"]["error"]

# Shape tokens for cards, rows, fields, and pills.
RADIUS = TOKENS["radii"]["panel"]
RADIUS_ROW = TOKENS["radii"]["row"]
RADIUS_INPUT = TOKENS["radii"]["input"]
RADIUS_PILL = TOKENS["radii"]["pill"]


def font_family() -> str:
    installed = {name.casefold(): name for name in QFontDatabase.families()}
    for candidate in (
        "Segoe UI Variable Text",
        "Segoe UI Variable",
        "SF Pro Text",
        ".AppleSystemUIFont",
        "Inter",
    ):
        if candidate.casefold() in installed:
            return installed[candidate.casefold()]
    return "Segoe UI" if "segoe ui" in installed else QFont().defaultFamily()


def apply_tracking(widget: QWidget, spacing: float) -> None:
    font = widget.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    widget.setFont(font)


def stylesheet() -> str:
    family = font_family().replace('"', '\\"')
    return f"""
        QWidget#geraldHome, QWidget#geraldOnboarding, QWidget#geraldShell {{
            background: transparent;
            color: {TEXT};
            font-family: "{family}";
            font-size: 13px;
        }}
        QWidget {{
            font-family: "{family}";
            font-size: 13px;
            color: {TEXT};
            background: transparent;
        }}
        QLabel {{ color: {TEXT}; }}
        QLabel[secondary="true"] {{ color: {SECONDARY}; }}
        QPushButton {{
            color: {TEXT};
            border: 0;
            border-radius: 10px;
            padding: 8px 14px;
            background: transparent;
        }}
        QPushButton:hover {{ background: {HOVER}; }}
        QPushButton:pressed {{ background: {INACTIVE}; }}
        QPushButton:focus-visible {{ border: 2px solid {FOCUS}; }}
        QPushButton#primaryButton {{
            color: {TOKENS["colors"]["primary_text"]};
            background: {ACCENT};
            border: 0;
            border-radius: 22px;
            font-weight: 600;
            padding: 10px 18px;
        }}
        QPushButton#primaryButton:hover {{ background: {ACCENT_PRESSED}; }}
        QPushButton#primaryButton:pressed {{ background: #3A3A3A; }}
        QPushButton#primaryButton:disabled {{ color: rgba(250,250,250,0.62); background: #8C8C8C; }}
        QPushButton#secondaryButton {{
            background: {INACTIVE};
            border: 0;
            border-radius: 20px;
            font-weight: 500;
        }}
        QPushButton#secondaryButton:hover {{ background: {HOVER}; }}
        QPushButton#textButton {{ color: {TEXT}; padding: 5px 7px; }}
        QPushButton#textButton:hover {{ background: {HOVER}; }}
        QPushButton#homeChip {{
            color: {TEXT};
            background: {INACTIVE};
            border: 0;
            border-radius: 16px;
            padding: 6px 12px;
        }}
        QPushButton#homeChip:hover {{ background: {HOVER}; }}
        QPushButton#homeChip[selected="true"] {{
            color: {TOKENS["colors"]["primary_text"]};
            background: {ACCENT};
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
            color: {TEXT};
            background: {SURFACE};
            border: 1px solid {SEPARATOR};
            border-radius: {RADIUS_INPUT}px;
            padding: 9px 12px;
            selection-background-color: rgba(15, 15, 15, 0.12);
        }}
        QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QComboBox:hover {{
            border-color: rgba(15, 15, 15, 0.22);
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
            border: 2px solid {FOCUS};
        }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ border: 0; background: transparent; }}
        QScrollBar:vertical {{ background: transparent; width: 5px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: transparent; border-radius: 2px; min-height: 24px; }}
        QScrollBar[active="true"]::handle:vertical {{ background: rgba(15, 15, 15, 0.24); }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QToolTip {{
            color: {TEXT};
            background: {SURFACE};
            border: 1px solid {SEPARATOR};
            padding: 5px 8px;
        }}
    """


class GlassBackdrop(QWidget):
    backdrop_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._backdrop_generation = 0
        self._backdrop_pixmap = QPixmap()
        self._background_timer = QTimer(self)
        self._background_timer.setInterval(50)
        self._background_timer.timeout.connect(self._advance_background)
        if not reduced_motion():
            self._background_timer.start()
        self._render_background()

    def _advance_background(self) -> None:
        cycle_ms = TOKENS["motion"]["background_cycle_ms"]
        self._phase = (self._phase + 2 * pi * 50 / cycle_ms) % (2 * pi)
        self._render_background()
        self.update()

    def _render_background(self) -> None:
        width = max(1, self.width())
        height = max(1, self.height())
        scale = TOKENS["glass"]["backdrop_scale"]
        size = QSize(max(1, round(width * scale)), max(1, round(height * scale)))
        pixmap = QPixmap(size)
        pixmap.fill(QColor(BG))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size.width() / width, size.height() / height)
        blobs = (
            ("#D8E5FF", 0.20, 0.22, 0.07, 0.05, 0.50),
            ("#E9DFFF", 0.80, 0.19, 0.05, 0.07, 0.42),
            ("#FFE4EA", 0.56, 0.88, 0.07, 0.04, 0.44),
        )
        for index, (color_hex, x, y, dx, dy, extent) in enumerate(blobs):
            phase = self._phase + index * 2 * pi / 3
            center = QPointF(
                width * (x + dx * sin(phase)),
                height * (y + dy * cos(phase)),
            )
            radius = max(width, height) * extent
            gradient = QRadialGradient(center, radius)
            color = QColor(color_hex)
            color.setAlpha(116)
            transparent = QColor(color_hex)
            transparent.setAlpha(0)
            gradient.setColorAt(0, color)
            gradient.setColorAt(0.54, QColor(color.red(), color.green(), color.blue(), 36))
            gradient.setColorAt(1, transparent)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawEllipse(center, radius, radius)
        painter.end()
        self._backdrop_pixmap = pixmap
        self._backdrop_generation += 1
        if self._backdrop_generation % 10 == 0:
            self.backdrop_changed.emit()

    def paintEvent(self, event: QEvent) -> None:
        if self._backdrop_pixmap.isNull():
            self._render_background()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self._backdrop_pixmap)

    def resizeEvent(self, event: QEvent) -> None:
        self._render_background()
        self.backdrop_changed.emit()
        super().resizeEvent(event)


class GlassPanel(QFrame):
    def __init__(
        self,
        parent=None,
        *,
        radius: int = RADIUS,
        surface_alpha: int | None = None,
    ):
        super().__init__(parent)
        self._radius = radius
        self._surface_alpha = (
            surface_alpha
            if surface_alpha is not None
            else TOKENS["glass"]["panel_alpha"]
        )
        self._backing = QPixmap()
        self._backing_size = QSize()
        self._backdrop_root = None
        self.setFrameShape(QFrame.Shape.NoFrame)

    def _connect_backdrop(self) -> None:
        root = self.window()
        if root is self._backdrop_root:
            return
        self._backdrop_root = root
        changed = getattr(root, "backdrop_changed", None)
        if changed is not None:
            changed.connect(self._refresh_backdrop)

    def _refresh_backdrop(self, *_args) -> None:
        self._backing_size = self.size()
        self._backing = QPixmap()
        root = self.window()
        backdrop = getattr(root, "_backdrop_pixmap", QPixmap())
        if backdrop.isNull() or root.width() <= 0 or root.height() <= 0:
            self.update()
            return
        origin = self.mapTo(root, QPoint(0, 0))
        scale_x = backdrop.width() / root.width()
        scale_y = backdrop.height() / root.height()
        source_rect = QRect(
            round(origin.x() * scale_x),
            round(origin.y() * scale_y),
            max(1, round(self.width() * scale_x)),
            max(1, round(self.height() * scale_y)),
        ).intersected(backdrop.rect())
        if source_rect.isEmpty():
            self.update()
            return
        crop = backdrop.copy(source_rect)
        small_size = QSize(
            max(1, self.width() // 4),
            max(1, self.height() // 4),
        )
        small = crop.scaled(
            small_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        blur_size = QSize(max(1, small.width() // 2), max(1, small.height() // 2))
        blurred = small.scaled(
            blur_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._backing = blurred.scaled(
            self.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.update()

    def paintEvent(self, event: QEvent) -> None:
        if self._backing_size != self.size():
            self._connect_backdrop()
            self._refresh_backdrop()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), self._radius, self._radius)
        for offset, alpha in ((5, 3), (2, 5)):
            shadow = QPainterPath(path)
            shadow.translate(0, offset)
            painter.fillPath(shadow, QColor(15, 15, 15, alpha))
        painter.save()
        painter.setClipPath(path)
        if not self._backing.isNull():
            painter.drawPixmap(self.rect(), self._backing)
        painter.fillPath(path, QColor(255, 255, 255, self._surface_alpha))
        painter.restore()
        painter.setPen(QPen(QColor(15, 15, 15, 20), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def resizeEvent(self, event: QEvent) -> None:
        self._refresh_backdrop()
        super().resizeEvent(event)

    def moveEvent(self, event: QEvent) -> None:
        self._refresh_backdrop()
        super().moveEvent(event)

    def showEvent(self, event: QEvent) -> None:
        self._connect_backdrop()
        self._refresh_backdrop()
        super().showEvent(event)


def reduced_motion() -> bool:
    return os.getenv("GERALD_REDUCE_MOTION") == "1"


def fade_in(widget: QWidget, ms: int = 180) -> None:
    if reduced_motion():
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def finish() -> None:
        widget.setGraphicsEffect(None)
        animation.deleteLater()

    animation.finished.connect(finish)
    widget._home_fade_animation = animation
    animation.start()
