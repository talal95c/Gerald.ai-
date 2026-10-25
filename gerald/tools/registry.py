from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from gerald.capture.screen import Capture
from gerald.perception.elements import Element
from gerald.perception.grounding import GroundingResolution, ScreenRect, resolve_target

TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "element_id": {"type": "integer"},
        "x": {"type": "number"},
        "y": {"type": "number"},
        "text": {"type": "string"},
    },
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
    _targeted_schema(
        "note",
        "Add a short note next to a target; target_text can locate its target by text.",
        {"text": {"type": "string"}, "target_text": {"type": "string"}},
        ["text"],
    ),
    _schema("clear", "Clear all drawing marks.", {}, []),
    _targeted_schema(
        "click",
        "Click a target after explaining the action and receiving an explicit yes; button is left, right, or double.",
        {
            "button": {"type": "string", "description": "left, right, or double"},
            "confirmed": {"type": "boolean", "description": "true only after the user explicitly confirms"},
        },
    ),
    _schema(
        "type_text",
        "Type text only after explaining the action and receiving an explicit yes.",
        {
            "text": {"type": "string"},
            "confirmed": {"type": "boolean", "description": "true only after the user explicitly confirms"},
        },
        ["text"],
    ),
    _schema(
        "press_keys",
        "Press a key chord such as ctrl+s only after explaining it and receiving an explicit yes.",
        {
            "keys": {"type": "string"},
            "confirmed": {"type": "boolean", "description": "true only after the user explicitly confirms"},
        },
        ["keys"],
    ),
    _targeted_schema(
        "scroll",
        "Scroll up or down 1–10 steps, optionally at a target; require an explicit yes before acting.",
        {
            "direction": {"type": "string", "description": "up or down"},
            "amount": {"type": "integer", "description": "integer from 1 to 10"},
            "confirmed": {"type": "boolean", "description": "true only after the user explicitly confirms"},
        },
    ),
    _schema("save_recap", "Save the lesson recap as a Markdown file and open it.", {"markdown": {"type": "string"}}, ["markdown"]),
    _schema("write", "Write text on the open teaching board.", {"text": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "size": {"type": "number"}}, ["text", "x", "y"]),
    _schema("write_math", "Write a math expression on the open teaching board.", {"latex": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "size": {"type": "number"}}, ["latex", "x", "y"]),
    _schema("draw_path", "Draw a path on the open teaching board.", {"points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2}}, "closed": {"type": "boolean"}}, ["points"]),
    _schema("clear_gerald", "Clear Gerald's board layer without changing user ink.", {}, []),
]
BOARD_TOOL_NAMES = frozenset({"write", "write_math", "draw_path", "clear_gerald"})


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


def _target(
    args: dict[str, Any],
    key: str,
    capture: Capture,
    elements: list[Element],
    image_array: np.ndarray | None,
) -> GroundingResolution:
    value = args.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a target object")
    if set(value) - {"element_id", "x", "y", "text"}:
        raise ValueError(f"{key} contains unexpected properties")
    return resolve_target(value, capture, elements, image_array, with_details=True)


def _validate_root_target(
    args: dict[str, Any],
    name: str,
    optional: set[str] | None = None,
    required: set[str] | None = None,
) -> None:
    target_fields = {"element_id", "x", "y", "text"}
    allowed = target_fields | (optional or set())
    extra = set(args) - allowed
    if extra:
        raise ValueError(f"unexpected argument: {sorted(extra)[0]}")
    if required and not required <= args.keys():
        raise ValueError(f"{sorted(required - args.keys())[0]} is required")
    has_target = (
        "element_id" in args
        or (isinstance(args.get("text"), str) and bool(args.get("text")))
        or {"x", "y"} <= args.keys()
    )
    if not has_target:
        raise ValueError("target requires element_id, text, or x and y")


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
    image_array: np.ndarray | None = None,
) -> tuple[list[DrawCommand], str]:
    try:
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        command: DrawCommand
        resolutions: list[tuple[str, GroundingResolution]] = []
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
                "note": {"text", "target_text"},
            }[name]
            required = {"text"} if name == "note" else set()
            _validate_root_target(args, name, optional, required)
            target_args = args
            if name == "note":
                target_args = {
                    key: value
                    for key, value in args.items()
                    if key in {"element_id", "x", "y"}
                }
                target_text = args.get("target_text")
                if target_text is None and not target_args:
                    target_text = args.get("text")
                if target_text is not None:
                    target_args["text"] = target_text
            resolution = resolve_target(
                target_args,
                capture,
                elements,
                image_array,
                with_details=True,
            )
            resolutions.append(("target", resolution))
            rect = resolution.rect
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
            from_resolution = _target(args, "from", capture, elements, image_array)
            to_resolution = _target(args, "to", capture, elements, image_array)
            resolutions.extend((("from", from_resolution), ("to", to_resolution)))
            command = ArrowCommand(_center(from_resolution.rect), _center(to_resolution.rect))
        elif name == "link":
            if not {"a", "b"} <= args.keys() or set(args) - {"a", "b", "label"}:
                raise ValueError("link requires a and b targets")
            label = args.get("label", "")
            if not isinstance(label, str):
                raise ValueError("label must be a string")
            a_resolution = _target(args, "a", capture, elements, image_array)
            b_resolution = _target(args, "b", capture, elements, image_array)
            resolutions.extend((("a", a_resolution), ("b", b_resolution)))
            command = LinkCommand(
                _center(a_resolution.rect),
                _center(b_resolution.rect),
                label[:80],
            )
        else:
            raise ValueError(f"unknown tool: {name}")
        result: dict[str, Any] = {"ok": True}
        if resolutions:
            result["grounding"] = (
                resolutions[0][1].layer
                if len(resolutions) == 1
                else {key: resolution.layer for key, resolution in resolutions}
            )
            notes = [resolution.note for _key, resolution in resolutions if resolution.note]
            if notes:
                result["note"] = "; ".join(notes)
        return [command], json.dumps(result)
    except (KeyError, TypeError, ValueError) as error:
        return [], json.dumps({"ok": False, "error": str(error)})
