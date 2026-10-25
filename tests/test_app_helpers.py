from PIL import Image

from gerald.app import _finalize_board_collection, _include_board_ink
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.grounding import ScreenRect, resolve_target


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
