from __future__ import annotations

import json
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from gerald.capture.screen import Capture
from gerald.perception.elements import Element
from gerald.perception.grounding import GroundingResolution, resolve_target
from gerald.tools.registry import PointCommand

ACTION_TOOL_NAMES = frozenset({"click", "type_text", "press_keys", "scroll"})


@dataclass
class ActionSession:
    abort_event: threading.Event = field(default_factory=threading.Event)
    action_count: int = 0
    last_mouse_position: tuple[int, int] | None = None
    approved_kinds: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    confirmation_lock: threading.Lock = field(default_factory=threading.Lock)


def _mouse_controller():
    from pynput.mouse import Controller

    return Controller()


def _keyboard_controller():
    from pynput.keyboard import Controller

    return Controller()


class InputActions:
    def __init__(
        self,
        *,
        require_confirmation: bool = True,
        mouse_factory: Callable[[], Any] | None = None,
        keyboard_factory: Callable[[], Any] | None = None,
        click_delay: float = 0.35,
        delay_wait: Callable[[threading.Event, float], bool] | None = None,
        request_confirmation: Callable[[str, tuple[int, int, int, int] | None, float], bool] | None = None,
        confirmation_timeout: float = 15.0,
    ) -> None:
        self.require_confirmation = require_confirmation
        self.mouse_factory = mouse_factory or _mouse_controller
        self.keyboard_factory = keyboard_factory or _keyboard_controller
        self.click_delay = click_delay
        self.delay_wait = delay_wait or (lambda event, delay: event.wait(delay))
        self.request_confirmation = request_confirmation
        self.confirmation_timeout = confirmation_timeout

    @staticmethod
    def new_session() -> ActionSession:
        return ActionSession()

    @staticmethod
    def abort(session: ActionSession) -> None:
        session.abort_event.set()

    def execute(
        self,
        session: ActionSession,
        name: str,
        args: dict[str, Any],
        capture: Capture,
        elements: list[Element],
        image_array: np.ndarray | None,
        on_commands: Callable[[list[object]], None],
        on_marks_visible: Callable[[bool], None],
    ) -> str:
        def error(message: str) -> str:
            return json.dumps({"ok": False, "error": message}, separators=(",", ":"))

        if not isinstance(args, dict):
            return error("arguments must be an object")
        if name not in ACTION_TOOL_NAMES:
            return error(f"unknown action: {name}")
        if "confirmed" in args and not isinstance(args["confirmed"], bool):
            return error("confirmed must be a boolean")
        try:
            target_fields = {"element_id", "x", "y", "text", "description"}
            if name == "click":
                if set(args) - target_fields - {"button", "confirmed"}:
                    raise ValueError("unexpected click argument")
                if not (
                    {"element_id"} <= args.keys()
                    or {"x", "y"} <= args.keys()
                    or args.get("text")
                    or args.get("description")
                ):
                    raise ValueError("click requires a target")
                button = args.get("button", "left")
                if button not in {"left", "right", "double"}:
                    raise ValueError("button must be left, right, or double")
                target = self._resolve_target(args, capture, elements, image_array)
            elif name == "type_text":
                if set(args) - {"text", "confirmed"}:
                    raise ValueError("unexpected type_text argument")
                text = args.get("text")
                if not isinstance(text, str) or not text:
                    raise ValueError("text must be a non-empty string")
            elif name == "press_keys":
                if set(args) - {"keys", "confirmed"}:
                    raise ValueError("unexpected press_keys argument")
                keys = self._parse_keys(args.get("keys"))
            else:
                if set(args) - target_fields - {"direction", "amount", "confirmed"}:
                    raise ValueError("unexpected scroll argument")
                direction = args.get("direction")
                if direction not in {"up", "down"}:
                    raise ValueError("direction must be up or down")
                amount = args.get("amount")
                if not isinstance(amount, int) or isinstance(amount, bool) or not 1 <= amount <= 10:
                    raise ValueError("amount must be an integer from 1 to 10")
                has_target = bool(target_fields & args.keys())
                if ("x" in args) != ("y" in args):
                    raise ValueError("scroll target requires both x and y")
                target = self._resolve_target(args, capture, elements, image_array) if has_target else None
        except (KeyError, TypeError, ValueError) as failure:
            return error(str(failure))

        if session.abort_event.is_set():
            return error("action cancelled")

        target_rect = (
            (target.rect.x, target.rect.y, target.rect.w, target.rect.h)
            if name in {"click", "scroll"} and target
            else None
        )
        if name == "click" and target is not None:
            on_commands([PointCommand(target.rect)])
        elif name == "scroll" and target is not None and self.require_confirmation and name not in session.approved_kinds:
            on_commands([PointCommand(target.rect)])
        mouse = None
        if self.require_confirmation and name not in session.approved_kinds:
            prompt = self._confirmation_prompt(name, args)
            with session.confirmation_lock:
                if name not in session.approved_kinds:
                    if self.request_confirmation is None or not self.request_confirmation(
                        prompt, target_rect, self.confirmation_timeout
                    ):
                        return error("user declined")
                    try:
                        mouse = self.mouse_factory()
                        with session.lock:
                            session.last_mouse_position = self._position(mouse)
                    except Exception as failure:
                        return error(f"input unavailable: {failure}")
                    session.approved_kinds.add(name)

        try:
            if mouse is None:
                mouse = self.mouse_factory()
            initial_position = self._position(mouse)
            with session.lock:
                if session.action_count >= 8:
                    return error("action limit")
                previous_position = session.last_mouse_position
                if previous_position is not None and self._distance(initial_position, previous_position) > 40:
                    session.abort_event.set()
                    return error("user took control")
                session.action_count += 1
        except Exception as failure:
            return error(f"input unavailable: {failure}")

        expected_position = initial_position
        movement_abort = False
        try:
            if name == "click":
                assert target is not None
                if self.delay_wait(session.abort_event, self.click_delay) or session.abort_event.is_set():
                    return error("action cancelled")
                expected_position = previous_position or initial_position
                if self._distance(self._position(mouse), expected_position) > 40:
                    session.abort_event.set()
                    return error("user took control")
                x, y = target.rect.center
                expected_position = (round(x), round(y))
                on_marks_visible(False)
                try:
                    mouse.position = (round(x), round(y))
                    from pynput.mouse import Button

                    mouse.click(
                        button=Button.right if button == "right" else Button.left,
                        count=2 if button == "double" else 1,
                    )
                finally:
                    on_marks_visible(True)
            elif name == "scroll":
                if target is not None:
                    expected_position = tuple(round(value) for value in target.rect.center)
                    mouse.position = expected_position
                mouse.scroll(0, amount if direction == "up" else -amount)
            elif name == "type_text":
                keyboard = self.keyboard_factory()
                for character in text:
                    if session.abort_event.is_set():
                        return error("action cancelled")
                    keyboard.type(character)
            else:
                keyboard = self.keyboard_factory()
                self._press_keys(keyboard, keys, session.abort_event)
        except Exception as failure:
            return error(f"input action failed: {failure}")
        finally:
            try:
                position_after = self._position(mouse)
            except Exception:
                position_after = initial_position
            if self._distance(position_after, expected_position) > 40:
                session.abort_event.set()
                movement_abort = True
            with session.lock:
                session.last_mouse_position = expected_position

        if movement_abort:
            return error("user took control")
        return json.dumps({"ok": True, "action": name})

    @staticmethod
    def _resolve_target(
        args: dict[str, Any],
        capture: Capture,
        elements: list[Element],
        image_array: np.ndarray | None,
    ) -> GroundingResolution:
        fields = {"element_id", "x", "y", "text", "description"}
        target_args = {key: value for key, value in args.items() if key in fields}
        if not target_args:
            raise ValueError("target requires element_id, text, or x and y")
        return resolve_target(target_args, capture, elements, image_array, with_details=True)

    @staticmethod
    def _position(mouse) -> tuple[int, int]:
        position = mouse.position
        return round(position[0]), round(position[1])

    @staticmethod
    def _distance(first: tuple[int, int], second: tuple[int, int]) -> float:
        return math.hypot(first[0] - second[0], first[1] - second[1])

    @staticmethod
    def _parse_keys(value: Any) -> list[str]:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("keys must be a non-empty chord such as ctrl+s")
        keys = [part.strip().casefold() for part in value.split("+")]
        if len(keys) > 5 or any(not key for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("invalid key chord")
        if "esc" in keys or "escape" in keys:
            raise ValueError("Esc is reserved to cancel actions")
        return keys

    @staticmethod
    def _confirmation_prompt(name: str, args: dict[str, Any]) -> str:
        if name == "click":
            return {
                "left": "Gerald veut cliquer ici",
                "right": "Gerald veut faire un clic droit ici",
                "double": "Gerald veut double-cliquer ici",
            }[args.get("button", "left")]
        if name == "type_text":
            return f"Gerald veut taper « {args['text']} »"
        if name == "press_keys":
            formatted = "+".join(
                part.title() if part.casefold() in {"ctrl", "shift", "alt", "altgr"} else part.title()
                for part in args["keys"].split("+")
            )
            return f"Gerald veut appuyer {formatted}"
        direction = "haut" if args["direction"] == "up" else "bas"
        return f"Gerald veut défiler vers le {direction}"

    @staticmethod
    def _press_keys(keyboard, keys: list[str], abort_event: threading.Event) -> None:
        from pynput.keyboard import Key

        modifiers = {
            "ctrl": Key.ctrl,
            "control": Key.ctrl,
            "shift": Key.shift,
            "alt": Key.alt,
            "cmd": Key.cmd,
            "super": Key.cmd,
        }
        named = {
            "enter": Key.enter,
            "tab": Key.tab,
            "space": Key.space,
            "backspace": Key.backspace,
            "delete": Key.delete,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
        }
        resolved = []
        for key in keys:
            value = modifiers.get(key) or named.get(key)
            if value is None:
                if len(key) != 1:
                    raise ValueError(f"unsupported key: {key}")
                value = key
            resolved.append(value)
        pressed = []
        try:
            for key in resolved:
                if abort_event.is_set():
                    raise ValueError("action cancelled")
                keyboard.press(key)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                keyboard.release(key)
