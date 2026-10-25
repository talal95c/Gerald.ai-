import json
import sys
from types import ModuleType

import numpy as np
from PIL import Image

from gerald.actions.input import InputActions
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.tools.registry import PointCommand


class FakeMouse:
    def __init__(self, position=(10, 10), events=None):
        self._position = position
        self.events = events if events is not None else []

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self.events.append(("position", value))
        self._position = value

    def click(self, *, button, count):
        self.events.append(("click", button, count, self._position))

    def scroll(self, dx, dy):
        self.events.append(("scroll", dx, dy))


class FakeKeyboard:
    def __init__(self):
        self.typed = []

    def type(self, value):
        self.typed.append(value)


def setup_capture():
    image = Image.new("RGB", (100, 100), "white")
    capture = capture_from_image(image, MonitorRect(0, 0, 100, 100), max_width=100)
    return capture, np.asarray(image)


def test_unconfirmed_action_is_refused_without_creating_controllers():
    calls = []
    actions = InputActions(
        mouse_factory=lambda: calls.append("mouse"),
        keyboard_factory=lambda: calls.append("keyboard"),
    )
    capture, image = setup_capture()

    output = actions.execute(
        actions.new_session(),
        "click",
        {"x": 50, "y": 50},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )

    assert output == (
        '{"ok":false,"error":"needs_confirmation: say what you will do and ask the user for a yes first"}'
    )
    assert calls == []


def test_confirmed_click_emits_point_then_clicks_physical_coordinates(monkeypatch):
    events = []
    mouse = FakeMouse(events=events)
    actions = InputActions(
        mouse_factory=lambda: mouse,
        click_delay=0,
        delay_wait=lambda _event, _delay: False,
    )
    capture, image = setup_capture()
    pynput = ModuleType("pynput")
    pynput.__path__ = []
    mouse_module = ModuleType("pynput.mouse")
    mouse_module.Button = type("Button", (), {"left": "left-button", "right": "right-button"})
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "pynput.mouse", mouse_module)
    commands = []
    visibility = []

    output = actions.execute(
        actions.new_session(),
        "click",
        {"x": 50, "y": 50, "button": "left", "confirmed": True},
        capture,
        [],
        image,
        lambda values: (commands.extend(values), events.append(("point",))),
        visibility.append,
    )

    assert json.loads(output) == {"ok": True, "action": "click"}
    assert isinstance(commands[0], PointCommand)
    assert events[0] == ("point",)
    assert visibility == [False, True]
    assert ("click", "left-button", 1, (50, 50)) in events


def test_escape_aborts_pending_click_before_input():
    events = []
    mouse = FakeMouse(events=events)
    actions = InputActions(
        mouse_factory=lambda: mouse,
        click_delay=0.35,
        delay_wait=lambda event, _delay: (event.set() or True),
    )
    capture, image = setup_capture()
    commands = []

    output = actions.execute(
        actions.new_session(),
        "click",
        {"x": 50, "y": 50, "confirmed": True},
        capture,
        [],
        image,
        commands.extend,
        lambda _visible: None,
    )

    assert json.loads(output) == {"ok": False, "error": "action cancelled"}
    assert len(commands) == 1
    assert not any(event[0] == "click" for event in events)


def test_action_limit_and_user_mouse_movement_abort():
    capture, image = setup_capture()
    mouse = FakeMouse()
    actions = InputActions(mouse_factory=lambda: mouse)
    session = actions.new_session()

    for _ in range(8):
        result = actions.execute(
            session,
            "scroll",
            {"direction": "down", "amount": 1, "confirmed": True},
            capture,
            [],
            image,
            lambda _commands: None,
            lambda _visible: None,
        )
        assert json.loads(result)["ok"] is True
    limited = actions.execute(
        session,
        "scroll",
        {"direction": "down", "amount": 1, "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )
    assert json.loads(limited)["error"] == "action limit"

    moved_session = actions.new_session()
    actions.execute(
        moved_session,
        "scroll",
        {"direction": "down", "amount": 1, "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )
    mouse.position = (90, 90)
    moved = actions.execute(
        moved_session,
        "scroll",
        {"direction": "down", "amount": 1, "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )
    assert json.loads(moved)["error"] == "user took control"
