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


def test_action_without_user_approval_is_refused_without_creating_controllers():
    calls = []
    actions = InputActions(
        mouse_factory=lambda: calls.append("mouse"),
        keyboard_factory=lambda: calls.append("keyboard"),
    )
    capture, image = setup_capture()

    output = actions.execute(
        actions.new_session(),
        "click",
        {"x": 50, "y": 50, "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )

    assert output == '{"ok":false,"error":"user declined"}'
    assert calls == []


def test_action_approval_is_scoped_to_tool_kind_and_text_prompt_is_exact(monkeypatch):
    prompts = []
    keyboard = FakeKeyboard()
    mouse = FakeMouse()
    actions = InputActions(
        mouse_factory=lambda: mouse,
        keyboard_factory=lambda: keyboard,
        click_delay=0,
        delay_wait=lambda _event, _delay: False,
        request_confirmation=lambda text, *_args: (prompts.append(text) or len(prompts) == 1),
    )
    pynput = ModuleType("pynput")
    pynput.__path__ = []
    mouse_module = ModuleType("pynput.mouse")
    mouse_module.Button = type("Button", (), {"left": "left-button", "right": "right-button"})
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "pynput.mouse", mouse_module)
    capture, image = setup_capture()
    session = actions.new_session()

    first = actions.execute(
        session, "click", {"x": 50, "y": 50}, capture, [], image,
        lambda _commands: None, lambda _visible: None,
    )
    second = actions.execute(
        session, "type_text", {"text": "texte exact à écrire"}, capture, [], image,
        lambda _commands: None, lambda _visible: None,
    )

    assert json.loads(first)["ok"] is True
    assert json.loads(second)["error"] == "user declined"
    assert prompts == ["Gerald veut cliquer ici", "Gerald veut taper « texte exact à écrire »"]
    assert session.approved_kinds == {"click"}


def test_confirmed_click_emits_point_then_clicks_physical_coordinates(monkeypatch):
    events = []
    mouse = FakeMouse(events=events)
    actions = InputActions(
        mouse_factory=lambda: mouse,
        click_delay=0,
        delay_wait=lambda _event, _delay: False,
        request_confirmation=lambda *_args: True,
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
        request_confirmation=lambda *_args: True,
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
    actions = InputActions(mouse_factory=lambda: mouse, require_confirmation=False)
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


def test_action_approval_is_once_per_session_and_repeats_for_new_turn():
    prompts = []
    actions = InputActions(
        mouse_factory=FakeMouse,
        request_confirmation=lambda *args: (prompts.append(args) or True),
    )
    capture, image = setup_capture()

    def scroll(session):
        return actions.execute(
            session,
            "scroll",
            {"direction": "down", "amount": 1, "confirmed": False},
            capture,
            [],
            image,
            lambda _commands: None,
            lambda _visible: None,
        )

    first_turn = actions.new_session()
    assert json.loads(scroll(first_turn))["ok"] is True
    assert json.loads(scroll(first_turn))["ok"] is True
    assert len(prompts) == 1
    assert json.loads(scroll(actions.new_session()))["ok"] is True
    assert len(prompts) == 2


def test_confirmation_cursor_movement_is_rebaselined_between_click_and_type():
    mouse = FakeMouse()
    prompt_count = 0

    def approve(*_args):
        nonlocal prompt_count
        prompt_count += 1
        mouse.position = (100 + prompt_count * 100, 100 + prompt_count * 100)
        return True

    actions = InputActions(
        mouse_factory=lambda: mouse,
        request_confirmation=approve,
        click_delay=0,
        delay_wait=lambda *_args: False,
    )
    capture, image = setup_capture()
    session = actions.new_session()
    click = actions.execute(
        session,
        "click",
        {"x": 50, "y": 50, "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )
    typed = actions.execute(
        session,
        "type_text",
        {"text": "hello", "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )

    assert json.loads(click)["ok"] is True
    assert json.loads(typed)["ok"] is True
    assert prompt_count == 2


def test_decline_or_timeout_returns_user_declined_without_input():
    calls = []
    actions = InputActions(
        mouse_factory=lambda: calls.append("mouse"),
        request_confirmation=lambda *_args: False,
    )
    capture, image = setup_capture()
    output = actions.execute(
        actions.new_session(),
        "type_text",
        {"text": "hello", "confirmed": True},
        capture,
        [],
        image,
        lambda _commands: None,
        lambda _visible: None,
    )

    assert json.loads(output) == {"ok": False, "error": "user declined"}
    assert calls == []
