from __future__ import annotations

from PyQt6.QtWidgets import QWidget

_window: QWidget | None = None


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


def open_home(store, indexer, settings, on_library_changed, *, ask_fn=None) -> QWidget:
    global _window
    from gerald.home.fonts import ensure_fonts

    ensure_fonts()
    if _is_open(_window):
        return _open(_window)

    from gerald.home.window import GeraldWindow

    window = GeraldWindow(
        store,
        indexer,
        settings,
        on_library_changed,
        ask_fn=ask_fn,
    )
    _remember(window)
    return _open(window)
