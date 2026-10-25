import threading
from types import SimpleNamespace

from PIL import Image

from gerald.app import (
    _activate_hold_turn,
    _cancel_turn_for_escape,
    _dispatch_key_after_hold_conflict,
    _discard_early_hold,
    _finalize_board_collection,
    _include_board_ink,
    _key_name,
    make_home_opener,
    _show_offline_status,
    _show_runtime_error,
)
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.grounding import ScreenRect, resolve_target


def test_key_name_maps_windows_control_character_and_virtual_key_codes():
    assert _key_name(SimpleNamespace(char="\x02", vk=66)) == "b"
    assert _key_name(SimpleNamespace(char=None, vk=48)) == "0"
    assert _key_name(SimpleNamespace(char="\x03", vk=None)) == "c"


def test_make_home_opener_forwards_callbacks_and_reuses_widget():
    class FakeWidget:
        def __init__(self):
            self.show_count = 0
            self.raise_count = 0
            self.activate_count = 0

        def show(self):
            self.show_count += 1

        def raise_(self):
            self.raise_count += 1

        def activateWindow(self):
            self.activate_count += 1

    calls = []
    widgets = []

    def open_home(*args, **kwargs):
        calls.append((args, kwargs))
        widget = FakeWidget()
        widgets.append(widget)
        return widget

    store = object()
    indexer = object()
    settings = object()
    on_library_changed = object()
    open_board = object()
    end_session = object()
    open_window = make_home_opener(
        open_home,
        store,
        indexer,
        settings,
        on_library_changed,
        open_board=open_board,
        end_session=end_session,
    )

    open_window()
    open_window()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (store, indexer, settings, on_library_changed)
    assert kwargs["open_board"] is open_board
    assert kwargs["end_session"] is end_session
    assert (widgets[0].show_count, widgets[0].raise_count, widgets[0].activate_count) == (
        2,
        2,
        2,
    )


def test_make_home_opener_with_no_factory_is_a_noop():
    open_window = make_home_opener(
        None,
        object(),
        object(),
        object(),
        object(),
        open_board=object(),
        end_session=object(),
    )

    open_window()


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


def test_escape_during_two_second_hold_cancels_without_submitting_turn():
    _assert_escape_cancels_turn(
        {
            "active": True,
            "released": False,
            "started": 10.0,
            "capture_generation": 4,
            "capture_request": None,
            "capture": None,
            "audio_sent_bytes": 24000,
            "response_active": False,
            "recap_pending": False,
            "realtime_turn_started": True,
            "pending_audio": [],
        },
        pressed_at=12.0,
    )


def test_escape_after_release_cancels_pending_capture_without_submission():
    _assert_escape_cancels_turn(
        {
            "active": True,
            "released": True,
            "started": 10.0,
            "capture_generation": 4,
            "capture_request": SimpleNamespace(cancel=lambda: None),
            "capture": None,
            "audio_sent_bytes": 24000,
            "response_active": False,
            "recap_pending": False,
            "realtime_turn_started": True,
            "pending_audio": [],
        },
        pressed_at=10.2,
    )


def _assert_escape_cancels_turn(app_state, pressed_at):
    audio_lock = threading.Lock()
    request = app_state["capture_request"]
    request_events = []
    if request is not None:
        request.cancel = lambda: request_events.append("cancel")
    mic_events = []
    realtime_events = []
    mic = SimpleNamespace(stop=lambda: mic_events.append("stop"))
    events = []

    def dispatch_escape():
        _cancel_turn_for_escape(
            app_state,
            mic,
            audio_lock,
            lambda: realtime_events.append("cancel"),
        )
        events.append("escape")

    assert _dispatch_key_after_hold_conflict(
        app_state,
        "esc",
        pressed_at,
        lambda: events.append("short-hold-cancel"),
        dispatch_escape,
    )
    assert events == ["escape"]
    assert mic_events == ["stop"]
    assert realtime_events == ["cancel"]
    assert request_events == (["cancel"] if request is not None else [])
    assert not app_state["active"]
    assert app_state["capture"] is None
    assert app_state["capture_request"] is None
    assert app_state["capture_generation"] == 5


def test_runtime_capture_error_uses_timed_overlay_without_message_box(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    def unexpected_dialog(*_args, **_kwargs):
        raise AssertionError("runtime errors must not open a QMessageBox")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_dialog)
    events = []
    overlay = SimpleNamespace(
        show=lambda: events.append("show"),
        show_timed_error=lambda message: (
            events.append(("error", message)),
            True,
        )[1],
    )

    _show_runtime_error(overlay, "Realtime disconnected")

    assert events == ["show", ("error", "Realtime disconnected")]


def test_repeated_capture_errors_restore_overlay_and_marks_before_dedup(caplog):
    class Overlay:
        visible = False
        marks_visible = False
        calls = 0
        renders = 0
        shows = 0

        def show(self):
            self.visible = True
            self.shows += 1

        def hide(self):
            self.visible = False

        def set_marks_visible(self, visible):
            self.marks_visible = visible

        def show_timed_error(self, _message):
            self.calls += 1
            if self.calls == 1:
                self.renders += 1
                return True
            return False

    overlay = Overlay()
    state = {"capture_overlay_hidden": True, "capture_marks_hidden": True}

    def set_visibility(visible):
        overlay.show() if visible else overlay.hide()

    caplog.set_level("WARNING", logger="gerald.app")
    for attempt in range(2):
        if attempt:
            overlay.hide()
            overlay.set_marks_visible(False)
            state.update(capture_overlay_hidden=True, capture_marks_hidden=True)
        _show_runtime_error(
            overlay,
            "Capture failed",
            state,
            set_visibility,
        )
        assert overlay.visible
        assert overlay.marks_visible
        assert not state["capture_overlay_hidden"]
        assert not state["capture_marks_hidden"]

    assert overlay.calls == 2
    assert overlay.renders == 1
    assert overlay.shows == 4
    assert caplog.text.count("Runtime capture/audio error") == 1


def test_offline_status_shows_overlay_even_when_already_offline():
    overlay = SimpleNamespace(
        show=lambda: setattr(overlay, "shows", overlay.shows + 1),
        set_status=lambda status: setattr(overlay, "status", status),
        shows=0,
        status="offline",
    )

    _show_offline_status(overlay)
    _show_offline_status(overlay)

    assert overlay.shows == 2
    assert overlay.status == "offline"


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
