import json

import numpy as np
from PIL import Image

from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception import grounder as grounder_module
from gerald.perception.elements import Element
from gerald.perception.grounding import GroundingResolution, ScreenRect, resolve_target


def test_smart_resize_respects_pixel_factor_and_limits():
    height, width = grounder_module.smart_resize(3200, 2400)
    small_height, small_width = grounder_module.smart_resize(40, 40)

    assert height % 28 == 0
    assert width % 28 == 0
    assert height * width <= grounder_module.MAX_PIXELS
    assert small_height * small_width >= 3136


def test_openrouter_grounder_maps_absolute_resized_coordinates(monkeypatch):
    requested = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "<point>154 98</point>"}}]}
            ).encode()

    def fake_urlopen(request, timeout):
        requested["request"] = request
        requested["timeout"] = timeout
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", fake_urlopen)
    image = Image.new("RGB", (320, 200), "white")

    point = grounder_module.OpenRouterGrounder().locate(image, "button")

    assert np.allclose(point, (160, 100))
    assert requested["timeout"] == 4.0
    payload = json.loads(requested["request"].data)
    assert payload["messages"][0]["content"][0]["text"] == (
        "Output only the coordinate of one point in your answer. "
        "What element matches the following task: button"
    )


def test_openrouter_grounder_maps_qwen_normalized_coordinates(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"choices":[{"message":{"content":"[500, 250]"}}]}'

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    point = grounder_module.OpenRouterGrounder(
        model="qwen/qwen3.5-27b",
        coord_mode="norm1000",
    ).locate(Image.new("RGB", (320, 200)), "search field")

    assert np.allclose(point, (160, 50))


def test_coordinate_parser_accepts_supported_formats():
    assert grounder_module._parse_point("(12, 34)") == (12.0, 34.0)
    assert grounder_module._parse_point("[12,34]") == (12.0, 34.0)
    assert grounder_module._parse_point("<point>12 34</point>") == (12.0, 34.0)
    assert grounder_module._parse_point("start_box='(12,34)'") == (12.0, 34.0)
    assert grounder_module._parse_point("no coordinates") is None


def test_moondream_maps_normalized_point_to_image_pixels():
    class Model:
        def point(self, _image, _description):
            return {"points": [{"x": 0.25, "y": 0.5}]}

    grounder = grounder_module.MoondreamLocalGrounder()
    grounder._model = Model()

    assert grounder.locate(Image.new("RGB", (200, 100)), "login") == (50, 50)


def test_resolve_target_uses_grounder_then_visual_snap(monkeypatch):
    image = Image.new("RGB", (240, 160), "white")
    pixels = np.asarray(image).copy()
    pixels[70:90, 120:140] = 0
    capture = capture_from_image(Image.fromarray(pixels), MonitorRect(0, 0, 240, 160), max_width=120)

    class FakeGrounder:
        def locate(self, seen_image, description):
            assert seen_image.size == (240, 160)
            assert description == "microphone icon"
            return 130, 80

    monkeypatch.setattr(grounder_module, "configured_grounder", lambda: FakeGrounder())
    result = resolve_target(
        {"description": "microphone icon"},
        capture,
        [],
        pixels,
        with_details=True,
    )

    assert isinstance(result, GroundingResolution)
    assert result.layer == "grounder"
    assert result.rect.x <= 120
    assert result.rect.y <= 70
    assert result.rect.x + result.rect.w >= 140
    assert result.rect.y + result.rect.h >= 90


def test_grounder_result_prefers_containing_element(monkeypatch):
    capture = capture_from_image(
        Image.new("RGB", (240, 160), "white"),
        MonitorRect(0, 0, 240, 160),
        max_width=120,
    )
    element = Element(0, "button", "Search", (55, 32, 20, 15), "uia")

    class FakeGrounder:
        def locate(self, _image, _description):
            return 130, 80

    monkeypatch.setattr(grounder_module, "configured_grounder", lambda: FakeGrounder())
    result = resolve_target(
        {"description": "search button"},
        capture,
        [element],
        np.asarray(capture.full_image),
        with_details=True,
    )

    assert result == GroundingResolution(ScreenRect(110, 64, 40, 30), "grounder")
