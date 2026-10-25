import sys
from types import ModuleType, SimpleNamespace

from PIL import Image
from PIL import ImageGrab
import pytest

from gerald.capture.screen import MonitorRect, capture_from_image, capture_screen
from gerald.perception.elements import Element, serialize_context
from gerald.perception.grounding import ScreenRect, resolve_target


def make_capture():
    return capture_from_image(
        Image.new("RGB", (200, 100), "white"),
        MonitorRect(-1000, 40, 200, 100),
        max_width=100,
    )


def test_capture_scale_and_negative_monitor_round_trip():
    capture = make_capture()
    assert capture.scale == 0.5
    assert (capture.image_width, capture.image_height) == (100, 50)
    assert capture.data_url.startswith("data:image/jpeg;base64,")
    screen = capture.img_to_screen(25, 20)
    assert screen == (-950, 80)
    assert capture.screen_to_img(*screen) == (25, 20)


def test_resolve_element_id_and_unknown_id():
    capture = make_capture()
    elements = [Element(3, "Button", "Save", (10, 10, 20, 12), "uia")]
    assert resolve_target({"element_id": 3}, capture, elements) == ScreenRect(-980, 60, 40, 24)
    with pytest.raises(ValueError, match="unknown element_id"):
        resolve_target({"element_id": 99}, capture, elements)


def test_resolve_point_prefers_smallest_containing_element():
    capture = make_capture()
    elements = [
        Element(1, "Window", "outer", (0, 0, 80, 50), "uia"),
        Element(2, "Button", "inner", (20, 10, 10, 10), "uia"),
    ]
    assert resolve_target({"x": 24, "y": 14}, capture, elements) == ScreenRect(-960, 60, 20, 20)


def test_resolve_nearest_within_40_image_pixels_and_raw_fallback():
    capture = make_capture()
    elements = [Element(5, "Button", "near", (20, 20, 10, 10), "uia")]
    assert resolve_target({"x": 45, "y": 25}, capture, elements) == ScreenRect(-960, 80, 20, 20)
    assert resolve_target({"x": 80, "y": 40}, capture, elements) == ScreenRect(-870, 90, 60, 60)


def test_element_context_truncates_names_and_obeys_character_cap():
    elements = [Element(i, "Text", "x" * 100, (i, 2, 3, 4), "ocr") for i in range(30)]
    context = serialize_context(elements, 100, 50, max_chars=300, app_name="demo.exe", window_title="title")
    assert len(context) <= 300
    assert "x" * 61 not in context
    assert "x" * 60 in context
    assert context.startswith("SCREEN CONTEXT\nActive app: demo.exe")


def test_capture_screen_uses_imagegrab_when_mss_grab_fails(monkeypatch):
    selected = {"left": 100, "top": 50, "width": 640, "height": 480}

    class FakeMSS:
        monitors = [{"left": 0, "top": 0, "width": 800, "height": 600}, selected]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def grab(self, _monitor):
            raise OSError("drawable's visual not found in screen's supported visuals")

    mouse_module = ModuleType("pynput.mouse")
    mouse_module.Controller = lambda: SimpleNamespace(position=(120, 80))
    monkeypatch.setitem(sys.modules, "mss", SimpleNamespace(MSS=FakeMSS))
    monkeypatch.setitem(sys.modules, "pynput.mouse", mouse_module)
    calls = []

    def grab(**kwargs):
        calls.append(kwargs)
        return Image.new("RGB", (640, 480), "white")

    monkeypatch.setattr(ImageGrab, "grab", grab)

    capture = capture_screen(max_width=320)

    assert capture.monitor == MonitorRect(100, 50, 640, 480)
    assert (capture.image_width, capture.image_height) == (320, 240)
    assert calls == [{"bbox": (100, 50, 740, 530), "all_screens": True}]
