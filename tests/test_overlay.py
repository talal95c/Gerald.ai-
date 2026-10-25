import os
import threading
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.overlay.window import (
    OverlayWindow,
    _build_screen_mappings,
    _confirmation_position,
    _physical_to_logical,
    _try_set_capture_exclusion,
)
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import ArrowCommand, CircleCommand, NoteCommand


def test_display_affinity_failure_is_recorded_and_warned_once(monkeypatch, caplog):
    import ctypes
    from gerald.overlay import window as window_module

    monkeypatch.setattr(window_module, "_capture_exclusion_warning_logged", False)
    monkeypatch.setattr(ctypes, "set_last_error", lambda _error: None, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 8, raising=False)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(kernel32=SimpleNamespace(GetLastError=lambda: 8)),
        raising=False,
    )
    user32 = SimpleNamespace(SetWindowDisplayAffinity=lambda _hwnd, _affinity: 0)

    assert not _try_set_capture_exclusion(123, user32)
    assert "GetLastError=8" in caplog.text


def test_overlay_renders_circle_and_arrow_with_transparent_surroundings():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 640, 400)
    overlay.add_commands(
        [
            CircleCommand(ScreenRect(100, 100, 80, 60)),
            ArrowCommand((210, 100), (310, 100)),
            NoteCommand(ScreenRect(400, 150, 40, 20), "micro"),
        ]
    )
    for mark in overlay._marks:
        mark.created -= 1
    overlay.set_status("speaking", output_level=0.7)
    overlay._status_changed -= 1
    overlay.set_caption("Clique sur le micro pour dicter une recherche.")
    image = QImage(640, 400, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    overlay.render(painter)
    painter.end()
    assert image.pixelColor(140, 100).alpha() > 0
    assert image.pixelColor(260, 106).alpha() > 0
    assert image.pixelColor(410, 128).alpha() > 0
    assert image.pixelColor(320, 330).alpha() > 0
    assert image.pixelColor(600, 200).alpha() == 0
    overlay.close()
    app.processEvents()


def test_mixed_dpi_screen_maps_from_native_physical_origins():
    mappings = _build_screen_mappings(
        [
            ("DISPLAY1", (0, 0, 1920, 1080), 2.0),
            ("DISPLAY2", (1920, 0, 1920, 1080), 1.0),
        ],
        [
            ("DISPLAY1", (0, 0, 3840, 2160)),
            ("DISPLAY2", (3840, 0, 1920, 1080)),
        ],
    )

    assert _physical_to_logical(4000, 500, mappings) == (2080, 500, 1.0)


def test_negative_origin_monitor_maps_relative_to_native_origin():
    mappings = _build_screen_mappings(
        [("LEFT", (-1280, 0, 1280, 720), 1.0), ("MAIN", (0, 0, 1920, 1080), 1.0)],
        [("LEFT", (-1280, 0, 1280, 720)), ("MAIN", (0, 0, 1920, 1080))],
    )

    assert _physical_to_logical(-640, 120, mappings) == (-640, 120, 1.0)


def test_confirmation_pill_renders_and_declines_without_accepting_focus():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 640, 400)
    completion = threading.Event()
    result = {"approved": False}
    overlay.show_confirmation("Gerald veut cliquer ici", (100, 100, 20, 20), completion, result)
    app.processEvents()

    pill = overlay._confirmation
    assert pill is not None
    assert pill.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert not pill.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert pill.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pill.label.font().pointSize() == 13
    assert pill.height() >= 32
    assert all(button.minimumHeight() >= 24 for button, _approved in pill.buttons)
    image = QImage(pill.width(), pill.height(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    pill.render(painter)
    painter.end()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() - 1, image.height() - 1).alpha() == 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() > 0

    assert overlay.dismiss_confirmation()
    assert completion.is_set()
    assert result["approved"] is False
    overlay.close()
    app.processEvents()


def test_confirmation_position_avoids_target_and_flips_above_when_needed():
    assert _confirmation_position((90, 90, 20, 20), (0, 0, 600, 400), (300, 68)) == (0, 122)
    assert _confirmation_position((190, 330, 20, 20), (0, 0, 400, 400), (300, 68)) == (50, 250)


def test_expired_confirmation_ignores_late_approval():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    completion = threading.Event()
    result = {"approved": False, "expired": False}
    token = "expired"
    overlay.show_confirmation("Confirmer", (100, 100, 20, 20), completion, result, token)
    pill = overlay._confirmation

    overlay.expire_confirmation(token)
    pill.buttons[0][0].click()

    assert completion.is_set()
    assert result == {"approved": False, "expired": True}
    overlay.close()
    app.processEvents()


def test_new_confirmation_replaces_old_and_old_button_is_stale():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    old_completion = threading.Event()
    old_result = {"approved": False}
    overlay.show_confirmation("Ancienne demande", (100, 100, 20, 20), old_completion, old_result, "old")
    old_pill = overlay._confirmation
    new_completion = threading.Event()
    new_result = {"approved": False}

    overlay.show_confirmation("Nouvelle demande", (200, 100, 20, 20), new_completion, new_result, "new")
    old_pill.buttons[0][0].click()

    assert overlay._confirmation is not old_pill
    assert not new_completion.is_set()
    assert not new_result["approved"]
    overlay.close()
    app.processEvents()
