import json
import sys
import threading
from types import ModuleType, SimpleNamespace

from PIL import Image
from PIL import ImageDraw
import numpy as np
import pytest

from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.elements import (
    Element,
    OCRProvider,
    _dedupe_ocr_words,
    _split_ocr_words,
    _tile_bounds,
    collect_elements,
    collect_elements_detailed,
)
from gerald.perception.grounding import GroundingResolution, ScreenRect, resolve_target
from gerald.tools.registry import execute_tool


def make_capture():
    return capture_from_image(
        Image.new("RGB", (400, 200), "white"),
        MonitorRect(-1000, 40, 400, 200),
        max_width=100,
    )


def test_text_grounding_matches_exact_and_ignores_accents():
    capture = make_capture()
    elements = [Element(1, "Button", "Paramètres", (20, 10, 40, 20), "uia")]
    expected = ScreenRect(-920, 80, 160, 80)

    assert resolve_target({"text": "Paramètres"}, capture, elements) == expected
    assert resolve_target({"text": "PARAMETRES"}, capture, elements) == expected


def test_text_grounding_accepts_typographical_errors():
    capture = make_capture()
    elements = [Element(2, "Button", "Settings", (20, 10, 40, 20), "uia")]

    assert resolve_target({"text": "Settngs"}, capture, elements) == ScreenRect(-920, 80, 160, 80)


def test_text_ambiguity_uses_nearest_coordinate():
    capture = make_capture()
    elements = [
        Element(1, "Button", "Save", (10, 10, 20, 10), "uia"),
        Element(2, "Button", "Save", (100, 10, 20, 10), "ocr"),
    ]

    assert resolve_target(
        {"text": "Save", "x": 112, "y": 14},
        capture,
        elements,
    ) == ScreenRect(-600, 80, 80, 40)


def test_ocr_text_match_narrows_to_matched_word_boxes():
    capture = make_capture()
    elements = [
        Element(
            1,
            "Text",
            "Add shortcut to Chrome",
            (10, 10, 100, 20),
            "ocr",
            (
                ("Add", (10, 12, 12, 10)),
                ("shortcut", (24, 12, 24, 10)),
                ("to", (52, 12, 8, 10)),
                ("Chrome", (62, 12, 30, 10)),
            ),
        )
    ]

    assert resolve_target({"text": "shortcut"}, capture, elements) == ScreenRect(-904, 88, 96, 40)


def test_ocr_splits_a_line_at_large_horizontal_word_gaps():
    words = [
        ("Store", (35, 10, 30, 12)),
        ("shortcut", (425, 10, 50, 12)),
        ("Web", (0, 10, 30, 12)),
        ("Add", (400, 10, 20, 12)),
    ]

    groups = _split_ocr_words(words)

    assert [[word for word, _rect in group] for group in groups] == [
        ["Web", "Store"],
        ["Add", "shortcut"],
    ]


def test_ocr_tiles_overlap_by_48_pixels_and_deduplicate_by_confidence():
    bounds = _tile_bounds(900)
    assert len(bounds) == 4
    assert [bounds[index + 1][0] - bounds[index][1] for index in range(3)] == [-48, -48, -48]

    words = [
        ("login", (20, 40, 30, 12), 65, (0, 1, 1, 1)),
        ("login", (21, 40, 30, 12), 92, (1, 1, 1, 1)),
        ("submit", (80, 40, 40, 12), 88, (1, 1, 1, 2)),
    ]

    assert _dedupe_ocr_words(words) == [words[1], words[2]]


def test_unmatched_text_without_coordinates_returns_retryable_error():
    with pytest.raises(ValueError, match="text not found on screen: Missing"):
        resolve_target({"text": "Missing"}, make_capture(), [])


def test_unmatched_text_with_coordinates_uses_visual_snap_and_adds_note():
    image = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(image).rectangle((242, 92, 257, 112), fill="black")
    capture = capture_from_image(image, MonitorRect(0, 0, 300, 200), max_width=300)
    overlapping_text = Element(1, "text", "Other text", (240, 90, 30, 30), "ocr")
    args = {"text": "Missing", "x": 250, "y": 102}

    result = resolve_target(args, capture, [overlapping_text], np.asarray(image), with_details=True)
    commands, output = execute_tool("point", args, capture, [overlapping_text], np.asarray(image))

    assert isinstance(result, GroundingResolution)
    assert result.layer == "snap"
    assert result.note == "text not found, used x,y"
    assert commands
    assert json.loads(output) == {
        "ok": True,
        "grounding": "snap",
        "note": "text not found, used x,y",
    }
    flat = Image.new("RGB", (300, 200), "white")
    raw = resolve_target(args, capture_from_image(flat, MonitorRect(0, 0, 300, 200)), [], np.asarray(flat), with_details=True)
    assert raw.layer == "raw"
    assert raw.note == "text not found, used x,y"


def test_visual_snap_selects_a_small_icon_component():
    image = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(image).rectangle((132, 82, 147, 102), fill="black")
    capture = capture_from_image(image, MonitorRect(0, 0, 300, 200), max_width=300)

    result = resolve_target(
        {"x": 139, "y": 92},
        capture,
        [],
        np.asarray(image),
        with_details=True,
    )

    assert isinstance(result, GroundingResolution)
    assert result.layer == "snap"
    assert result.rect.x < 132 and result.rect.y < 82
    assert result.rect.x + result.rect.w > 147
    assert result.rect.y + result.rect.h > 102


def test_visual_snap_uses_raw_box_when_the_crop_is_flat():
    image = Image.new("RGB", (300, 200), "white")
    capture = capture_from_image(image, MonitorRect(0, 0, 300, 200), max_width=300)

    result = resolve_target(
        {"x": 140, "y": 100},
        capture,
        [],
        np.asarray(image),
        with_details=True,
    )

    assert result == GroundingResolution(ScreenRect(110, 70, 60, 60), "raw")


def test_distant_xy_overrides_ocr_element_id_and_adds_tool_result_note():
    image = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(image).rectangle((242, 92, 257, 112), fill="black")
    capture = capture_from_image(image, MonitorRect(0, 0, 300, 200), max_width=300)
    element = Element(9, "text", "Search Google", (10, 10, 100, 20), "ocr")

    commands, output = execute_tool(
        "point",
        {"element_id": 9, "x": 250, "y": 102},
        capture,
        [element],
        np.asarray(image),
    )

    result = json.loads(output)
    assert commands
    assert result["grounding"] == "snap"
    assert "element_id ignored" in result["note"]


def test_ocr_uses_full_resolution_and_retains_word_boxes(monkeypatch):
    capture = make_capture()
    observed = {"sizes": [], "configs": [], "languages": []}
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")
    pytesseract.get_languages = lambda **_kwargs: ["eng", "fra"]

    def image_to_data(image, **kwargs):
        observed["sizes"].append(image.size)
        observed["configs"].append(kwargs["config"])
        observed["languages"].append(kwargs["lang"])
        return {
            "text": ["Add", "shortcut", "!!!", "weak"],
            "conf": ["95", "91", "99", "49"],
            "block_num": [1, 1, 1, 1],
            "par_num": [1, 1, 1, 1],
            "line_num": [1, 1, 1, 1],
            "left": [10, 28, 70, 90],
            "top": [20, 20, 20, 20],
            "width": [15, 35, 15, 20],
            "height": [12, 12, 12, 12],
        }

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)
    from gerald.perception import elements as elements_module

    elements_module._tesseract_languages.cache_clear()
    try:
        provider = OCRProvider()
        found = provider.get_elements(capture)
        assert len(observed["sizes"]) == 6
        assert all(width == 800 for width, _height in observed["sizes"])
        assert observed["configs"] == ["--psm 11 -c omp_thread_limit=1"] * 6
        assert observed["languages"] == ["fra+eng"] * 6
        assert found[0].role == "text"
        assert found[0].name == "Add shortcut"
        assert found[0].word_boxes == (
            ("Add", (-995, 50, 8, 6)),
            ("shortcut", (-986, 50, 18, 6)),
        )

        class EmptyProvider:
            def get_elements(self, _capture):
                return []

        collected = collect_elements(capture, EmptyProvider(), provider)
        assert collected[0].word_boxes == (
            ("Add", (1, 2, 2, 2)),
            ("shortcut", (4, 2, 4, 2)),
        )
    finally:
        elements_module._tesseract_languages.cache_clear()


def test_ocr_budget_returns_completed_tiles_as_partial_results(monkeypatch):
    capture = capture_from_image(
        Image.new("RGB", (400, 200), "white"),
        MonitorRect(0, 0, 400, 200),
        max_width=400,
    )
    release_slow_tiles = threading.Event()
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")

    def image_to_data(image, **_kwargs):
        if image.height == 196:
            release_slow_tiles.wait(1)
        return {
            "text": ["login"],
            "conf": ["90"],
            "block_num": [1],
            "par_num": [1],
            "line_num": [1],
            "left": [20],
            "top": [20],
            "width": [30],
            "height": [12],
        }

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)
    from gerald.perception import elements as elements_module

    monkeypatch.setattr(elements_module, "_tesseract_languages", lambda: "eng")
    updates = []
    try:
        result = collect_elements_detailed(
            capture,
            ocr_provider=OCRProvider(upscale=True),
            budget=0.05,
            on_update=lambda elements: updates.append(elements),
        )
    finally:
        release_slow_tiles.set()

    assert not result.complete
    assert any(element.name == "login" for element in result.elements)
    assert any(any(element.name == "login" for element in update) for update in updates)
