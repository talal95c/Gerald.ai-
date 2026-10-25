import threading
from types import SimpleNamespace

from PIL import Image

from gerald.app import (
    _activate_hold_turn,
    _dispatch_key_after_hold_conflict,
    _discard_early_hold,
    _finalize_board_collection,
    _include_board_ink,
    _key_name,
    _show_runtime_error,
)
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.grounding import ScreenRect, resolve_target


def test_key_name_maps_windows_control_character_and_virtual_key_codes():
    assert _key_name(SimpleNamespace(char="\x02", vk=66)) == "b"
    assert _key_name(SimpleNamespace(char=None, vk=48)) == "0"
    assert _key_name(SimpleNamespace(char="\x03", vk=None)) == "c"


def test_short_hold_cancels_before_board_hotkey_and_never_starts_a_turn():
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication

    from gerald.board import BoardWindow

    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    screen = SimpleNamespace(geometry=lambda: QRect(0, 0, 320, 240))
    request_events = []
    status_events = []
    mic_events = []
    request = SimpleNamespace(cancel=lambda: request_events.append("cancel"))
    mic = SimpleNamespace(stop=lambda: mic_events.append("stop"))
    overlay = SimpleNamespace(set_status=lambda status: status_events.append(status))
    app_state = {
        "active": True,
        "typed": False,
        "released": False,
        "started": 10.0,
        "capture_generation": 4,
        "capture_request": request,
        "capture": None,
        "audio_sent_bytes": 1200,
        "realtime_turn_started": False,
        "pending_audio": [b"early audio"],
    }
    audio_lock = threading.Lock()
    dispatch_events = []
    realtime_events = []

    def cancel_hold():
        _discard_early_hold(app_state, mic, overlay, audio_lock)
        dispatch_events.append("cancelled")

    def dispatch_board_hotkey():
        board.open_on_screen(screen, dark=False)
        dispatch_events.append("board")

    assert _dispatch_key_after_hold_conflict(
        app_state,
        "b",
        10.25,
        cancel_hold,
        dispatch_board_hotkey,
    )
    assert dispatch_events == ["cancelled", "board"]
    assert board.isVisible()
    assert not app_state["active"]
    assert app_state["pending_audio"] == []
    assert request_events == ["cancel"]
    assert mic_events == ["stop"]
    assert status_events == ["idle"]
    assert not _activate_hold_turn(
        app_state,
        4,
        audio_lock,
        lambda: realtime_events.append("start_turn"),
        lambda _audio: realtime_events.append("send_audio"),
    )
    assert realtime_events == []
    board.close()
    app.processEvents()


def test_long_hold_ignores_nonmodifier_key_without_cancelling_or_dispatching():
    app_state = {
        "active": True,
        "typed": False,
        "released": False,
        "started": 10.0,
    }
    events = []

    assert not _dispatch_key_after_hold_conflict(
        app_state,
        "b",
        10.6,
        lambda: events.append("cancel"),
        lambda: events.append("dispatch"),
    )
    assert events == []


def test_runtime_capture_error_uses_timed_overlay_without_message_box(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    def unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("runtime errors must not open a QMessageBox")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_dialog)
    events = []
    overlay = SimpleNamespace(
        show=lambda: events.append("show"),
        show_timed_error=lambda message: events.append(("error", message)),
    )

    _show_runtime_error(overlay, "Realtime disconnected")

    assert events == ["show", ("error", "Realtime disconnected")]


def test_board_ink_rect_maps_from_screen_to_image_and_back():
    capture = capture_from_image(
        Image.new("RGB", (200, 100), "white"),
        MonitorRect(1000, 0, 200, 100),
        max_width=200,
    )

    elements = _include_board_ink([], capture, [(1050, 20, 24, 12)])

    assert elements[0].rect == (50, 20, 24, 12)
    assert resolve_target({"element_id": 0}, capture, elements) == ScreenRect(1050, 20, 24, 12)


def test_final_board_collection_publishes_each_ink_element_once():
    capture = capture_from_image(
        Image.new("RGB", (200, 100), "white"),
        MonitorRect(1000, 0, 200, 100),
        max_width=200,
    )
    partial_capture = {}

    elements = _finalize_board_collection(
        [],
        capture,
        [(1050, 20, 24, 12)],
        partial_capture,
    )

    assert partial_capture["elements"] == elements
    assert [element.name for element in elements if element.source == "board"] == ["ink 1"]
