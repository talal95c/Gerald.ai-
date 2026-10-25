from __future__ import annotations

import json
from pathlib import Path
import sys

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from gerald.home.bridge import Bridge


class _WebSurface(QWidget):
    def __init__(self, bridge: Bridge, file: str, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("bridge", bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.load(QUrl.fromLocalFile(str(Path(__file__).with_name("webui") / file)))
        layout.addWidget(self.view)


class NotchWindow(QWidget):
    sizes = {"greeting": (380, 72), "collapsed": (220, 34), "panel": (440, 300), "settings": (880, 560)}

    def __init__(self, bridge: Bridge):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(None, flags)
        self.bridge = bridge
        self._focus_requested = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.surface = _WebSurface(bridge, "index.html", self)
        layout.addWidget(self.surface)
        bridge.modeChanged.connect(self.set_mode)
        bridge.focusRequested.connect(self.request_focus)
        bridge.recapReady.connect(self._open_recap_in_view)
        self._animation = QPropertyAnimation(self, b"geometry", self)
        self._animation.setDuration(260)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anchor("greeting", animate=False)
        self._apply_capture_exclusion()

    def activateWindow(self) -> None:
        if self._focus_requested:
            super().activateWindow()

    def request_focus(self, requested: bool) -> None:
        self._focus_requested = requested
        flags = self.windowFlags()
        if requested:
            flags &= ~Qt.WindowType.WindowDoesNotAcceptFocus
            self.setWindowFlags(flags)
            self.show()
            super().activateWindow()
        else:
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
            self.setWindowFlags(flags)
            self.show()

    def set_mode(self, mode: str) -> None:
        self._anchor(mode, animate=True)

    def _anchor(self, mode: str, *, animate: bool) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width, height = self.sizes.get(mode, self.sizes["greeting"])
        target = QRect(available.center().x() - width // 2, available.top(), width, height)
        if not animate or self.geometry().isNull():
            self.setGeometry(target)
        else:
            self._animation.stop()
            self._animation.setStartValue(self.geometry())
            self._animation.setEndValue(target)
            self._animation.start()

    def _apply_capture_exclusion(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from gerald.overlay.window import _try_set_capture_exclusion

            handle = int(self.winId())
            self.capture_excluded = _try_set_capture_exclusion(handle, ctypes.windll.user32)
        except (AttributeError, OSError):
            self.capture_excluded = False

    def _open_recap_in_view(self, path: str) -> None:
        self.surface.view.page().runJavaScript(
            "window.dispatchEvent(new CustomEvent('gerald-recap-ready', "
            f"{{detail:{json.dumps(path)}}}))"
        )


class TdWindow(_WebSurface):
    def __init__(self, bridge: Bridge):
        super().__init__(bridge, "td.html")
        self.setWindowTitle("TD 4 — Polynômes du second degré.pdf")
        self.resize(960, 1040)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    def show_td(self) -> None:
        self.show()
        self.raise_()
