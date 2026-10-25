import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

from gerald.overlay.window import (
    OverlayWindow,
    _build_screen_mappings,
    _confirmation_position,
    _physical_to_logical,
    _try_set_capture_exclusion,
)
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import ArrowCommand, CircleCommand, ClearCommand, NoteCommand, PointCommand, TipCommand
from gerald.tools.diagram import DiagramCommand, layout_diagram


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


def test_timed_error_status_returns_to_idle():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 640, 400)

    overlay.show_timed_error("Realtime disconnected", duration_ms=10000)

    assert overlay._status == "error"
    assert overlay._status_message == "Realtime disconnected"
    assert overlay._timed_error_timer.isActive()
    overlay._expire_timed_error()
    assert overlay._status == "idle"
    assert not overlay._timed_error_timer.isActive()
    overlay.close()
    app.processEvents()


def test_level_updates_preserve_timed_error_until_new_hold_status():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 640, 400)
    overlay.show_timed_error("Realtime disconnected", duration_ms=10000)

    for level in (0.1, 0.4, 0.8):
        overlay.set_status("listening", mic_level=level, level_only=True)

    assert overlay._status == "error"
    assert overlay._status_message == "Realtime disconnected"
    assert overlay._timed_error_timer.isActive()

    overlay.set_status("listening")

    assert overlay._status == "listening"
    assert overlay._status_message == ""
    assert not overlay._timed_error_timer.isActive()
    overlay.close()
    app.processEvents()


def test_long_timed_error_text_fits_or_middle_elides_and_keeps_tooltip():
    from PyQt6.QtGui import QFont, QFontMetrics

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    message = (
        "Connexion Realtime indisponible. Vérifiez votre réseau puis réessayez "
        "dans quelques instants depuis les réglages de Gerald."
    )
    overlay.show_timed_error(message, duration_ms=10000)
    font = QFont(overlay._font_family)
    font.setPixelSize(13)
    font.setWeight(QFont.Weight.Medium)
    metrics = QFontMetrics(font)

    width, display_text = overlay._status_label_layout(
        message,
        available_width=800,
        caption_width=0,
        level_indicators=False,
    )

    assert width <= 520
    assert metrics.horizontalAdvance(message) <= width - 36 or "…" in display_text
    assert overlay.toolTip() == message
    overlay.close()
    app.processEvents()


def test_repeated_timed_error_is_rendered_once_within_thirty_seconds():
    class CountingOverlay(OverlayWindow):
        def __init__(self):
            self.show_count = 0
            super().__init__()

        def show(self):
            self.show_count += 1
            super().show()

    app = QApplication.instance() or QApplication([])
    overlay = CountingOverlay()

    assert overlay.show_timed_error("Realtime disconnected")
    assert not overlay.show_timed_error("Realtime disconnected")
    assert not overlay.show_timed_error("Realtime disconnected")

    assert overlay.show_count == 1
    overlay.close()
    app.processEvents()


def test_offline_status_survives_level_updates_and_clears_on_idle():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.set_status("offline")
    for level in (0.1, 0.4, 0.8):
        overlay.set_status("listening", mic_level=level, level_only=True)

    assert overlay._status == "offline"

    overlay.set_status("idle")
    assert overlay._status == "idle"
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


def test_confirmation_text_elides_display_only_and_keeps_guillemets_together():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    text = f"Gerald veut taper « {'a' * 140} »"
    overlay.show_confirmation(text, (100, 100, 20, 20), threading.Event(), {"approved": False})
    app.processEvents()

    pill = overlay._confirmation
    assert pill is not None
    assert "…" in pill.label.text()
    assert "«\u00a0" in pill.label.text()
    assert "\u00a0»" in pill.label.text()
    assert pill.toolTip() == text
    assert pill.label.toolTip() == text
    overlay.close()
    app.processEvents()


def test_confirmation_position_avoids_target_and_flips_above_when_needed():
    assert _confirmation_position((90, 90, 20, 20), (0, 0, 600, 400), (300, 68)) == (0, 122)
    assert _confirmation_position((190, 330, 20, 20), (0, 0, 400, 400), (300, 68)) == (50, 250)


def test_expired_confirmation_ignores_late_approval():
    _app = QApplication.instance() or QApplication([])
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


def test_tip_command_opens_bubble_and_choice_click_calls_callback():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    choices = []
    overlay.add_commands([TipCommand("Astuce : Ctrl+F")])
    assert overlay.has_bubble()
    assert overlay._bubble.label.text() == "Astuce : Ctrl+F"

    overlay.show_bubble("Continuer ?", ["Oui", "Non"], choices.append)
    bubble = overlay._bubble
    assert bubble is not None
    assert bubble.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert len(bubble.buttons) == 2
    bubble.buttons[0].click()
    assert choices == ["Oui"]
    assert not overlay.has_bubble()
    overlay.close()
    app.processEvents()


def test_bubble_timeout_calls_none():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    choices = []
    overlay.show_bubble("Astuce", ["Oui", "Non"], choices.append, ttl=0.02)
    QTest.qWait(260)
    assert choices == [None]
    overlay.close()
    app.processEvents()


def test_tip_bubble_avoids_circle_target_and_uses_window_opacity():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(cursor_enabled=True)
    overlay.setGeometry(0, 0, 640, 400)
    overlay._screen_mappings = lambda: _build_screen_mappings(
        [("fake", (0, 0, 640, 400), 1.0)]
    )

    overlay.add_commands(
        [CircleCommand(ScreenRect(200, 100, 160, 80)), TipCommand("Astuce : Ctrl+F")]
    )

    bubble = overlay._bubble
    assert bubble is not None
    bubble_rect = QRectF(
        bubble.geometry().translated(-overlay.geometry().x(), -overlay.geometry().y())
    )
    target_rect = overlay._cursor_target_rect.translated(
        -overlay.geometry().x(), -overlay.geometry().y()
    )
    assert not bubble_rect.intersects(target_rect)
    assert bubble.graphicsEffect() is None
    assert bubble._fade.propertyName() == b"windowOpacity"
    bubble.setWindowOpacity(1.0)
    image = QImage(bubble.width(), bubble.height(), QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    bubble.render(painter)
    painter.end()
    assert image.pixelColor(bubble.width() // 2, 10).alpha() >= 248
    overlay.close()
    app.processEvents()


def test_floating_diagram_never_scales_below_point_eight_five():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(cursor_enabled=True)
    layout = layout_diagram(
        title="Grand diagram",
        layout="flow",
        nodes=[
            {"id": str(index), "text": "A very wide label"}
            for index in range(8)
        ],
    )

    state = overlay._diagram_state(DiagramCommand(layout), time.monotonic(), 30)

    assert state["scale"] >= 0.85
    overlay.close()
    app.processEvents()


def test_cursor_flies_to_mark_and_returns_after_clear():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(cursor_enabled=True)
    overlay.setGeometry(0, 0, 640, 400)
    overlay.set_mouse_position(40, 50, physical=False)
    target_command = PointCommand(ScreenRect(100, 80, 20, 20))
    target = overlay._cursor_target_for(target_command)
    overlay.add_commands([target_command])
    assert overlay._cursor_flight is not None
    start, end, _started = overlay._cursor_flight
    assert end == target
    overlay._cursor_flight = (start, end, time.monotonic() - 0.36)
    overlay._tick()
    assert abs(overlay._cursor_position.x() - target.x()) < 0.1
    assert abs(overlay._cursor_position.y() - target.y()) < 0.1

    overlay.add_commands([ClearCommand()])
    assert overlay._cursor_flight is not None
    return_target = overlay._mouse_position + type(overlay._mouse_position)(18, 14)
    overlay._cursor_flight = (*overlay._cursor_flight[:2], time.monotonic() - 0.36)
    overlay._tick()
    assert abs(overlay._cursor_position.x() - return_target.x()) < 0.1
    assert abs(overlay._cursor_position.y() - return_target.y()) < 0.1
    overlay.close()
    app.processEvents()


def test_cursor_environment_setting_disables_paint(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("GERALD_CURSOR", "0")
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 200, 150)
    image = QImage(200, 150, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    overlay.render(painter)
    painter.end()
    assert not overlay._cursor_enabled
    assert image.pixelColor(20, 20).alpha() == 0
    overlay.close()
    app.processEvents()


def test_cursor_poll_keeps_qt_logical_coordinates_at_150_percent_scale(monkeypatch):
    from gerald.overlay import window as window_module

    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(cursor_enabled=True)
    overlay._screen_mappings = lambda: _build_screen_mappings(
        [("fake", (0, 0, 1000, 600), 1.5)]
    )
    monkeypatch.setattr(window_module.QCursor, "pos", staticmethod(lambda: QPoint(50, 40)))

    assert _physical_to_logical(75, 60, overlay._screen_mappings()) == (50.0, 40.0, 1.5)
    overlay._poll_cursor_position()
    assert overlay._mouse_position == QPointF(50, 40)
    overlay.close()
    app.processEvents()


def test_cursor_only_motion_requests_a_partial_repaint(monkeypatch):
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow(cursor_enabled=True)
    overlay._mouse_position = QPointF(100, 100)
    overlay._cursor_position = QPointF(100, 100)
    overlay._status_changed = time.monotonic() - 1
    calls = []
    monkeypatch.setattr(overlay, "update", lambda *args: calls.append(args))

    overlay._tick()

    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert isinstance(calls[0][0], QRect)
    assert calls[0][0].width() >= 56
    overlay.close()
    app.processEvents()


def test_floating_diagram_expires_after_30_seconds_and_clear_removes_it():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    layout = layout_diagram(
        title="Cycle",
        layout="cycle",
        nodes=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    )
    overlay.add_commands([DiagramCommand(layout)])
    assert overlay._diagrams[0]["ttl"] == 30.0
    overlay._diagrams[0]["created"] -= 31
    overlay._tick()
    assert overlay._diagrams == []
    overlay.add_commands([DiagramCommand(layout)])
    overlay.add_commands([ClearCommand()])
    assert overlay._diagrams == []
    overlay.close()
    app.processEvents()
    app.processEvents()


def test_offscreen_screen_mappings_skip_native_monitor_pairing(monkeypatch):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    from gerald.overlay import window as window_module

    native_calls = []
    monkeypatch.setattr(window_module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(
        window_module,
        "_native_windows_monitors",
        lambda: native_calls.append(True) or [("NATIVE", (0, 0, 1600, 1600))],
    )

    mappings = window_module._screen_mappings()

    assert native_calls == []
    assert mappings
    assert mappings[0].physical[2] == round(mappings[0].logical[2] * mappings[0].ratio)


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
