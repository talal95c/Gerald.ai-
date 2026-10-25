import json

from PIL import Image

from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.elements import Element
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import CircleCommand, ClearCommand, TOOL_SCHEMAS, execute_tool


def test_tool_schemas_use_plain_objects_without_conditional_keywords():
    forbidden = {"oneOf", "anyOf", "allOf", "enum", "const", "not"}

    def contains_forbidden(value):
        if isinstance(value, dict):
            return any(
                key in forbidden or contains_forbidden(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_forbidden(child) for child in value)
        return False

    for tool in TOOL_SCHEMAS:
        assert tool["type"] == "function"
        assert tool["name"]
        assert tool["parameters"]["type"] == "object"
        assert not contains_forbidden(tool["parameters"])


def test_tool_handlers_validate_and_map_image_sized_arguments():
    capture = capture_from_image(Image.new("RGB", (200, 100)), MonitorRect(20, 10, 200, 100), 100)
    elements = [Element(7, "Button", "Run", (10, 8, 20, 10), "uia")]
    commands, result = execute_tool("circle", {"element_id": 7, "w": 30, "h": 12}, capture, elements)
    assert json.loads(result) == {"ok": True}
    assert commands == [CircleCommand(ScreenRect(40, 26, 60, 24))]
    commands, result = execute_tool("circle", {"element_id": "7"}, capture, elements)
    assert commands == []
    assert json.loads(result)["ok"] is False
    commands, result = execute_tool(
        "point", {"element_id": 7, "x": 10, "y": 10, "label": "conflict"}, capture, elements
    )
    assert commands == []
    assert "element_id or x and y" in json.loads(result)["error"]


def test_unknown_elements_and_clear_tool():
    capture = capture_from_image(Image.new("RGB", (20, 20)), MonitorRect(0, 0, 20, 20))
    commands, result = execute_tool("point", {}, capture, [])
    assert not commands
    assert "target requires element_id or x and y" in json.loads(result)["error"]
    commands, result = execute_tool("point", {"element_id": 44}, capture, [])
    assert not commands
    assert "unknown element_id" in json.loads(result)["error"]
    commands, result = execute_tool("clear", {}, capture, [])
    assert commands == [ClearCommand()]
    assert json.loads(result) == {"ok": True}
