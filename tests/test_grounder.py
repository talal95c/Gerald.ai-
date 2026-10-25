import base64
import io
import json
import os
import stat

import numpy as np
from PIL import Image
import pytest

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
    headers = {
        name.casefold(): value
        for name, value in requested["request"].header_items()
    }
    assert headers["user-agent"] == grounder_module.USER_AGENT
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


def test_moondream_cloud_request_and_normalized_point_mapping(monkeypatch):
    requested = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"points":[{"x":0.25,"y":0.75}]}'

    def fake_urlopen(request, timeout):
        requested["request"] = request
        requested["timeout"] = timeout
        return Response()

    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", fake_urlopen)
    image = Image.new("RGB", (1800, 800), "white")
    grounder = grounder_module.MoondreamCloudGrounder("secret-key")

    assert grounder.locate(image, "search field") == (450, 600)
    request = requested["request"]
    assert request.full_url == "https://api.moondream.ai/v1/point"
    assert request.get_method() == "POST"
    assert requested["timeout"] == 4.0
    headers = {name.casefold(): value for name, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    assert headers["x-moondream-auth"] == "secret-key"
    assert headers["user-agent"] == grounder_module.USER_AGENT
    payload = json.loads(request.data)
    assert payload["model"] == "moondream3.1-9B-A2B"
    assert payload["object"] == "search field"
    assert payload["image_url"].startswith("data:image/jpeg;base64,")
    jpeg = base64.b64decode(payload["image_url"].split(",", 1)[1])
    assert Image.open(io.BytesIO(jpeg)).size == (1568, 697)


def test_moondream_cloud_empty_points_return_none(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"points":[]}'

    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    grounder = grounder_module.MoondreamCloudGrounder("secret-key")
    image = Image.new("RGB", (200, 100))

    assert grounder.locate(image, "login") is None


def test_moondream_cloud_http_401_raises_and_timeout_wrapper_returns_none(monkeypatch):
    class Response:
        status = 401

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    grounder = grounder_module.MoondreamCloudGrounder("secret-key")
    image = Image.new("RGB", (200, 100))

    with pytest.raises(RuntimeError, match="HTTP 401"):
        grounder.locate(image, "login")
    assert grounder_module.locate_with_timeout(grounder, image, "login") is None


@pytest.mark.parametrize("point", [{"x": 1.1, "y": 0.5}, {"x": 0.5, "y": -0.1}])
def test_moondream_cloud_rejects_points_outside_normalized_range(monkeypatch, point):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"points": [point]}).encode()

    monkeypatch.setattr(grounder_module.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    grounder = grounder_module.MoondreamCloudGrounder("secret-key")

    assert grounder.locate(Image.new("RGB", (200, 100)), "login") is None


def test_configured_moondream_cloud_requires_key_and_uses_model_override(tmp_path, monkeypatch):
    monkeypatch.setattr(grounder_module, "_grounder_settings_path", lambda: tmp_path / "grounder.json")
    monkeypatch.setattr(grounder_module, "_instances", {})
    monkeypatch.setattr(grounder_module, "_runtime_backend", None)
    monkeypatch.delenv("GERALD_GROUNDER", raising=False)
    monkeypatch.delenv("MOONDREAM_API_KEY", raising=False)
    assert grounder_module.configured_grounder("moondream-cloud") is None

    monkeypatch.setenv("MOONDREAM_API_KEY", "secret-key")
    monkeypatch.setenv("GERALD_GROUNDER_MODEL", "custom-model")
    grounder = grounder_module.configured_grounder("moondream-cloud")

    assert isinstance(grounder, grounder_module.MoondreamCloudGrounder)
    assert grounder.model == "custom-model"
    assert grounder.api_key == "secret-key"


def test_moondream_cloud_settings_file_permissions_and_precedence(tmp_path, monkeypatch):
    settings_path = tmp_path / ".gerald" / "grounder.json"
    saved_path = grounder_module.save_moondream_cloud_settings(
        "https://colab.example/v1/",
        "saved-key",
        settings_path,
    )

    assert saved_path == settings_path
    if os.name != "nt":
        assert stat.S_IMODE(saved_path.stat().st_mode) == 0o600
    assert grounder_module.load_moondream_cloud_settings(settings_path) == {
        "endpoint": "https://colab.example/v1",
        "api_key": "saved-key",
    }

    monkeypatch.setenv("MOONDREAM_ENDPOINT", "https://env.example/v1/")
    monkeypatch.setenv("MOONDREAM_API_KEY", "env-key")
    assert grounder_module.load_moondream_cloud_settings(settings_path) == {
        "endpoint": "https://colab.example/v1",
        "api_key": "saved-key",
    }

    settings_path.write_text(json.dumps({"endpoint": "", "api_key": ""}), encoding="utf-8")
    assert grounder_module.load_moondream_cloud_settings(settings_path) == {
        "endpoint": "https://env.example/v1",
        "api_key": "env-key",
    }


def test_configured_moondream_cloud_hot_swaps_saved_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(grounder_module, "_grounder_settings_path", lambda: tmp_path / "grounder.json")
    monkeypatch.setattr(grounder_module, "_instances", {})
    monkeypatch.setattr(grounder_module, "_runtime_backend", None)
    monkeypatch.delenv("GERALD_GROUNDER", raising=False)
    monkeypatch.setenv("MOONDREAM_ENDPOINT", "https://env.example/v1")
    monkeypatch.setenv("MOONDREAM_API_KEY", "env-key")
    grounder_module.save_moondream_cloud_settings("https://first.example/v1", "first-key")
    grounder_module.set_runtime_grounder_backend("moondream-cloud")
    first = grounder_module.configured_grounder()
    grounder_module.save_moondream_cloud_settings("https://second.example/v1", "second-key")
    second = grounder_module.configured_grounder()

    assert first.endpoint == "https://first.example/v1"
    assert first.api_key == "first-key"
    assert second.endpoint == "https://second.example/v1"
    assert second.api_key == "second-key"


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


def test_text_match_does_not_call_grounder(monkeypatch):
    capture = capture_from_image(
        Image.new("RGB", (240, 160), "white"),
        MonitorRect(0, 0, 240, 160),
    )
    element = Element(0, "text", "Search Wikipedia", (20, 10, 80, 18), "ocr")
    calls = []

    class FakeGrounder:
        def locate(self, _image, _description):
            calls.append(True)
            return None

    monkeypatch.setattr(grounder_module, "configured_grounder", lambda: FakeGrounder())

    result = resolve_target(
        {"text": "Search Wikipedia", "description": "search input"},
        capture,
        [element],
        with_details=True,
    )

    assert result == GroundingResolution(ScreenRect(20, 10, 80, 18), "text")
    assert calls == []


def test_unmatched_text_uses_description_grounder(monkeypatch):
    capture = capture_from_image(
        Image.new("RGB", (240, 160), "white"),
        MonitorRect(0, 0, 240, 160),
    )
    descriptions = []

    class FakeGrounder:
        def locate(self, _image, description):
            descriptions.append(description)
            return 120, 80

    monkeypatch.setattr(grounder_module, "configured_grounder", lambda: FakeGrounder())

    result = resolve_target(
        {"text": "Mic", "description": "microphone icon"},
        capture,
        [],
        with_details=True,
    )

    assert isinstance(result, GroundingResolution)
    assert result.layer == "grounder"
    assert descriptions == ["microphone icon"]


def test_grounder_uses_full_image_and_scales_point_to_capture_image(monkeypatch):
    capture = capture_from_image(
        Image.new("RGB", (400, 200), "white"),
        MonitorRect(10, 20, 400, 200),
        max_width=200,
    )
    element = Element(0, "button", "Target", (145, 45, 20, 10), "uia")
    seen_sizes = []

    class FakeGrounder:
        def locate(self, image, _description):
            seen_sizes.append(image.size)
            return 300, 100

    monkeypatch.setattr(grounder_module, "configured_grounder", lambda: FakeGrounder())

    result = resolve_target(
        {"description": "target button"},
        capture,
        [element],
        np.asarray(capture.image),
        with_details=True,
    )

    assert result == GroundingResolution(ScreenRect(300, 110, 40, 20), "grounder")
    assert seen_sizes == [(400, 200)]
