from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

if QApplication.instance() is None:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

_window: QWidget | None = None
_td_window: QWidget | None = None


def _remember(widget: QWidget) -> QWidget:
    global _window
    _window = widget
    widget._home_closed = False
    widget.destroyed.connect(lambda *_args: _forget(widget))
    return widget


def _forget(widget: QWidget) -> None:
    global _window
    if _window is widget:
        _window = None


def _open(widget: QWidget) -> QWidget:
    widget.show()
    widget.raise_()
    widget.activateWindow()
    return widget


def _is_open(widget: QWidget | None) -> bool:
    if widget is None or getattr(widget, "_home_closed", False):
        return False
    try:
        from PyQt6 import sip

        return not sip.isdeleted(widget)
    except (ImportError, RuntimeError):
        return True


def open_home(
    store, indexer, settings, on_library_changed, *, ask_fn=None, open_board=None, end_session=None
) -> QWidget:
    global _window, _td_window
    if _is_open(_window):
        return _open(_window)

    from gerald.home.bridge import Bridge
    from gerald.home.demo import seed_demo
    from gerald.home.notch import NotchWindow, TdWindow

    seed_demo(store, indexer)
    bridge = Bridge(
        store,
        indexer,
        settings,
        ask_fn=ask_fn,
        open_board=open_board,
        end_session=end_session,
        on_library_changed=on_library_changed,
    )
    window = NotchWindow(bridge)
    _remember(window)
    _td_window = TdWindow(bridge)
    bridge.tdRequested.connect(_td_window.show_td)
    _td_window.show_td()
    return _open(window)
