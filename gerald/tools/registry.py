from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from gerald.capture.screen import Capture
from gerald.perception.elements import Element
from gerald.perception.grounding import ScreenRect, resolve_target

TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "element_id": {"type": "integer"},
        "x": {"type": "number"},
        "y": {"type": "number"},
    },
    "oneOf": [
        {"required": ["element_id"]},
        {"required": ["x", "y"]},
    ],
    "additionalProperties": False,
}


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


def _targeted_schema(
    name: str,
    description: str,
    optional: dict[str, Any] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    properties = {**TARGET_SCHEMA["properties"], **(optional or {})}
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "oneOf": [
            {"required": ["element_id"]},
            {"required": ["x", "y"]},
        ],
        "additionalProperties": False,
    }
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }


TOOL_SCHEMAS = [
    _targeted_schema("point", "Point to a screen element or image coordinate.", {"label": {"type": "string"}}),
    _targeted_schema("circle", "Circle a screen element or image region.", {"w": {"type": "number"}, "h": {"type": "number"}}),
    _schema("arrow", "Draw an arrow from one target to another.", {"from": TARGET_SCHEMA, "to": TARGET_SCHEMA}, ["from", "to"]),
    _schema("link", "Connect two targets with a labeled line.", {"a": TARGET_SCHEMA, "b": TARGET_SCHEMA, "label": {"type": "string"}}, ["a", "b"]),
    _targeted_schema("underline", "Underline a target or image-coordinate line.", {"w": {"type": "number"}}),
    _targeted_schema("highlight", "Highlight a target or image-coordinate region.", {"w": {"type": "number"}, "h": {"type": "number"}}),
    _targeted_schema("note", "Add a short note next to a target.", {"text": {"type": "string"}}, ["text"]),
    _schema("clear", "Clear all drawing marks.", {}, []),
]


@dataclass(frozen=True)
class DrawCommand:
    pass


@dataclass(frozen=True)
class PointCommand(DrawCommand):
    rect: ScreenRect
    label: str = ""


@dataclass(frozen=True)
class CircleCommand(DrawCommand):
    rect: ScreenRect


@dataclass(frozen=True)
class ArrowCommand(DrawCommand):
    start: tuple[int, int]
    end: tuple[int, int]


@dataclass(frozen=True)
class LinkCommand(DrawCommand):
    start: tuple[int, int]
    end: tuple[int, int]
    label: str = ""


@dataclass(frozen=True)
class UnderlineCommand(DrawCommand):
    rect: ScreenRect


@dataclass(frozen=True)
class HighlightCommand(DrawCommand):
    rect: ScreenRect


@dataclass(frozen=True)
class NoteCommand(DrawCommand):
    rect: ScreenRect
    text: str


@dataclass(frozen=True)
class ClearCommand(DrawCommand):
    pass


def _target(args: dict[str, Any], key: str, capture: Capture, elements: list[Element]) -> ScreenRect:
    value = args.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a target object")
    if set(value) - {"element_id", "x", "y"}:
        raise ValueError(f"{key} contains unexpected properties")
    if "element_id" in value and ({"x", "y"} & value.keys()):
        raise ValueError(f"{key} must use element_id or x and y")
    return resolve_target(value, capture, elements)


def _validate_root_target(
    args: dict[str, Any],
    name: str,
    optional: set[str] | None = None,
    required: set[str] | None = None,
) -> None:
    target_fields = {"element_id", "x", "y"}
    allowed = target_fields | (optional or set())
    extra = set(args) - allowed
    if extra:
        raise ValueError(f"unexpected argument: {sorted(extra)[0]}")
    if required and not required <= args.keys():
        raise ValueError(f"{sorted(required - args.keys())[0]} is required")
    if "element_id" in args and ({"x", "y"} & args.keys()):
        raise ValueError(f"{name} must use element_id or x and y")
    if "element_id" not in args and not {"x", "y"} <= args.keys():
        raise ValueError("target requires element_id or x and y")


def _center(rect: ScreenRect) -> tuple[int, int]:
    x, y = rect.center
    return round(x), round(y)


def _positive_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return float(value)


def execute_tool(
    name: str,
    args: dict[str, Any],
    capture: Capture,
    elements: list[Element],
) -> tuple[list[DrawCommand], str]:
    try:
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        command: DrawCommand
        if name == "clear":
            if args:
                raise ValueError("clear accepts no arguments")
            command = ClearCommand()
        elif name in {"point", "circle", "underline", "highlight", "note"}:
            optional = {
                "point": {"label"},
                "circle": {"w", "h"},
                "underline": {"w"},
                "highlight": {"w", "h"},
                "note": {"text"},
            }[name]
            required = {"text"} if name == "note" else set()
            _validate_root_target(args, name, optional, required)
            rect = resolve_target(args, capture, elements)
            if name == "point":
                label = args.get("label", "")
                if not isinstance(label, str):
                    raise ValueError("label must be a string")
                command = PointCommand(rect, label[:80])
            elif name == "circle":
                width = _positive_number(args["w"], "w") / capture.scale if "w" in args else rect.w
                height = _positive_number(args["h"], "h") / capture.scale if "h" in args else rect.h
                command = CircleCommand(ScreenRect(rect.x, rect.y, round(width), round(height)))
            elif name == "underline":
                width = _positive_number(args["w"], "w") / capture.scale if "w" in args else rect.w
                command = UnderlineCommand(ScreenRect(rect.x, rect.y + rect.h - 2, round(width), 2))
            elif name == "highlight":
                width = _positive_number(args["w"], "w") / capture.scale if "w" in args else rect.w
                height = _positive_number(args["h"], "h") / capture.scale if "h" in args else rect.h
                command = HighlightCommand(ScreenRect(rect.x, rect.y, round(width), round(height)))
            else:
                text = args.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("text must be a non-empty string")
                command = NoteCommand(rect, text.strip()[:200])
        elif name == "arrow":
            if set(args) != {"from", "to"}:
                raise ValueError("arrow requires from and to targets")
            command = ArrowCommand(_center(_target(args, "from", capture, elements)), _center(_target(args, "to", capture, elements)))
        elif name == "link":
            if not {"a", "b"} <= args.keys() or set(args) - {"a", "b", "label"}:
                raise ValueError("link requires a and b targets")
            label = args.get("label", "")
            if not isinstance(label, str):
                raise ValueError("label must be a string")
            command = LinkCommand(
                _center(_target(args, "a", capture, elements)),
                _center(_target(args, "b", capture, elements)),
                label[:80],
            )
        else:
            raise ValueError(f"unknown tool: {name}")
        return [command], json.dumps({"ok": True})
    except (KeyError, TypeError, ValueError) as error:
        return [], json.dumps({"ok": False, "error": str(error)})
