import sys
from types import ModuleType, SimpleNamespace

from PIL import Image
import pytest

from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.elements import Element, OCRProvider, collect_elements
from gerald.perception.grounding import ScreenRect, resolve_target


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


def test_unmatched_text_without_coordinates_returns_retryable_error():
    with pytest.raises(ValueError, match="text not found on screen: Missing"):
        resolve_target({"text": "Missing"}, make_capture(), [])


def test_ocr_uses_full_resolution_and_retains_word_boxes(monkeypatch):
    capture = make_capture()
    observed = {}
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")
    pytesseract.get_languages = lambda **_kwargs: ["eng", "fra"]

    def image_to_data(image, **kwargs):
        observed["size"] = image.size
        observed.update(kwargs)
        return {
            "text": ["Add", "shortcut"],
            "conf": ["95", "91"],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
            "left": [10, 28],
            "top": [20, 20],
            "width": [15, 35],
            "height": [12, 12],
        }

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)
    from gerald.perception import elements as elements_module

    elements_module._tesseract_languages.cache_clear()
    try:
        provider = OCRProvider()
        found = provider.get_elements(capture)
        assert observed["size"] == (400, 200)
        assert observed["lang"] == "fra+eng"
        assert observed["timeout"] <= 0.7
        assert found[0].name == "Add shortcut"
        assert found[0].word_boxes == (
            ("Add", (-990, 60, 15, 12)),
            ("shortcut", (-972, 60, 35, 12)),
        )

        class EmptyProvider:
            def get_elements(self, _capture):
                return []

        collected = collect_elements(capture, EmptyProvider(), provider)
        assert collected[0].word_boxes == (
            ("Add", (2, 5, 4, 3)),
            ("shortcut", (7, 5, 9, 3)),
        )
    finally:
        elements_module._tesseract_languages.cache_clear()
