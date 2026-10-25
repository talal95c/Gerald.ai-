import asyncio
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
    _map_windows_ocr_box,
    _split_ocr_words,
    _tile_bounds,
    _run_windows_ocr_passes,
    _windows_inverted_strips,
    _windows_ocr_scale,
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


def test_hn_long_navigation_label_uses_ocr_word_rect_before_container():
    capture = make_capture()
    bar = Element(1, "DataItem", "login submit past comments ask", (0, 10, 100, 10), "uia")
    navigation = Element(
        2,
        "text",
        "login submit past",
        (0, 10, 60, 10),
        "ocr",
        (
            ("login", (0, 10, 20, 10)),
            ("submit", (22, 10, 25, 10)),
            ("past", (50, 10, 18, 10)),
        ),
    )

    result = resolve_target({"text": "login"}, capture, [bar, navigation])

    assert result == ScreenRect(-1000, 80, 80, 40)


def test_hn_long_navigation_label_falls_through_to_configured_grounder(monkeypatch):
    capture = make_capture()
    bar = Element(1, "DataItem", "login submit past comments ask", (0, 10, 100, 10), "uia")
    monkeypatch.setattr("gerald.perception.grounder.configured_grounder", lambda: object())
    monkeypatch.setattr(
        "gerald.perception.grounder.locate_with_timeout",
        lambda *_args, **_kwargs: (80, 50),
    )

    result = resolve_target(
        {"text": "login", "description": "login link at top right"},
        capture,
        [bar],
        with_details=True,
    )

    assert result.layer == "grounder"
    assert result.rect.center[0] != -800


def test_hn_long_navigation_label_keeps_weak_match_without_grounder(monkeypatch):
    capture = make_capture()
    bar = Element(1, "DataItem", "login submit past comments ask", (0, 10, 100, 10), "uia")
    monkeypatch.setattr("gerald.perception.grounder.configured_grounder", lambda: None)

    assert resolve_target({"text": "login"}, capture, [bar]) == ScreenRect(-1000, 80, 400, 40)


def test_weak_text_matches_use_coordinates_before_score(monkeypatch):
    capture = make_capture()
    first = Element(1, "DataItem", "login submit past comments ask", (0, 10, 30, 10), "uia")
    second = Element(2, "DataItem", "login submit past comments ask", (60, 10, 30, 10), "uia")
    monkeypatch.setattr("gerald.perception.grounder.configured_grounder", lambda: None)

    assert resolve_target(
        {"text": "login", "x": 75, "y": 15},
        capture,
        [first, second],
    ) == ScreenRect(-760, 80, 120, 40)


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


def test_ocr_phrase_match_requires_all_contiguous_query_words():
    capture = make_capture()
    elements = [
        Element(
            1,
            "Text",
            "Delete draft",
            (0, 10, 70, 10),
            "ocr",
            (
                ("Delete", (0, 10, 35, 10)),
                ("draft", (38, 10, 32, 10)),
            ),
        ),
        Element(
            2,
            "Text",
            "Delete account now",
            (0, 30, 120, 10),
            "ocr",
            (
                ("Delete", (10, 30, 30, 10)),
                ("account", (43, 30, 40, 10)),
                ("now", (87, 30, 20, 10)),
            ),
        ),
    ]

    assert resolve_target({"text": "Delete account"}, capture, elements) == ScreenRect(-960, 160, 292, 40)


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


@pytest.mark.parametrize("separator", ["|", "·", "•", "›", "»", "/", "–"])
def test_ocr_splits_lines_at_separator_tokens(separator):
    words = [
        ("past", (0, 10, 25, 12)),
        (separator, (27, 10, 5, 12)),
        ("comments", (34, 10, 45, 12)),
    ]

    groups = _split_ocr_words(words)

    assert [[word for word, _rect in group] for group in groups] == [
        ["past"],
        ["comments"],
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
        provider = OCRProvider(backend="tesseract")
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


def test_full_window_uia_container_does_not_suppress_ocr_search_label():
    capture = make_capture()

    class Provider:
        def __init__(self, elements):
            self.elements = elements

        def get_elements(self, _capture):
            return self.elements

    collection = collect_elements(
        capture,
        Provider([Element(0, "Window", "Chrome", (-1000, 40, 400, 200), "uia")]),
        Provider([Element(0, "text", "Search", (-950, 60, 60, 18), "ocr")]),
    )

    assert any(element.name == "Search" and element.source == "ocr" for element in collection)


def test_named_window_does_not_suppress_ocr_but_small_button_does():
    capture = make_capture()

    class Provider:
        def __init__(self, elements):
            self.elements = elements

        def get_elements(self, _capture):
            return self.elements

    ocr = Element(0, "text", "Save", (-950, 60, 48, 20), "ocr")
    window_result = collect_elements(
        capture,
        Provider([Element(0, "Window", "Save document", (-1000, 40, 400, 200), "uia")]),
        Provider([ocr]),
    )
    assert any(element.source == "ocr" and element.name == "Save" for element in window_result)

    button_result = collect_elements(
        capture,
        Provider([Element(0, "ButtonControl", "Save", (-950, 60, 48, 20), "uia")]),
        Provider([ocr]),
    )
    assert not any(element.source == "ocr" and element.name == "Save" for element in button_result)


def test_empty_edit_container_keeps_ocr_but_named_button_dedupes_it():
    capture = make_capture()

    class Provider:
        def __init__(self, elements):
            self.elements = elements

        def get_elements(self, _capture):
            return self.elements

    editor = Element(0, "EditControl", "", (-1000, 40, 400, 200), "uia")
    editor_ocr = Element(0, "text", "print", (-950, 60, 40, 18), "ocr")
    editor_result = collect_elements(capture, Provider([editor]), Provider([editor_ocr]))
    assert any(element.name == "print" for element in editor_result)

    button = Element(0, "ButtonControl", "Save", (-950, 60, 48, 20), "uia")
    button_ocr = Element(0, "text", "Save", (-950, 60, 48, 20), "ocr")
    button_result = collect_elements(capture, Provider([button]), Provider([button_ocr]))
    assert not any(element.source == "ocr" and element.name == "Save" for element in button_result)


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

    class EmptyUIA:
        def get_elements(self, _capture):
            return []

    try:
        result = collect_elements_detailed(
            capture,
            uia_provider=EmptyUIA(),
            ocr_provider=OCRProvider(upscale=True, backend="tesseract"),
            budget=0.05,
            on_update=lambda elements: updates.append(elements),
        )
    finally:
        release_slow_tiles.set()

    assert not result.complete
    assert any(element.name == "login" for element in result.elements)
    assert any(any(element.name == "login" for element in update) for update in updates)


def test_windows_uia_breadth_first_keeps_top_children_before_later_items(monkeypatch):
    from gerald.perception import elements as elements_module

    class Rect:
        left, top, right, bottom = -990, 50, -950, 70

    class Control:
        BoundingRectangle = Rect()
        ControlTypeName = "ButtonControl"
        IsOffscreen = False

        def __init__(self, name, children=()):
            self.Name = name
            self.children = list(children)

        def GetChildren(self):
            return self.children

    root = Control("root", [Control("top"), Control("middle"), Control("bottom")])
    automation = ModuleType("uiautomation")
    automation.SetGlobalSearchTimeout = lambda _timeout: None
    automation.GetForegroundControl = lambda: root
    monkeypatch.setitem(sys.modules, "uiautomation", automation)
    monkeypatch.setattr(elements_module, "os", SimpleNamespace(name="nt"))
    ticks = iter(index / 10 for index in range(20))
    monkeypatch.setattr(elements_module, "time", SimpleNamespace(monotonic=lambda: next(ticks)))

    found = elements_module.UIAProvider().get_elements(make_capture())

    names = [element.name for element in found]
    assert "top" in names
    assert "bottom" not in names


def test_windows_ocr_worker_returns_partial_results_on_budget_timeout(monkeypatch):
    from gerald.perception import elements as elements_module

    capture = make_capture()
    partial = Element(1, "text", "login", (1, 2, 20, 10), "ocr")

    class Future:
        def result(self, timeout=None):
            assert timeout is not None and timeout > 0
            raise TimeoutError

        def cancel(self):
            return True

    class Executor:
        def submit(self, function, seen_capture, timeout, publish):
            assert function == OCRProvider._windows_ocr
            assert seen_capture is capture
            publish([partial])
            return Future()

    monkeypatch.setattr(elements_module, "_WINDOWS_OCR_EXECUTOR", Executor())
    elements, complete, _seconds = OCRProvider(backend="windows").get_elements_detailed(
        capture,
        deadline=__import__("time").monotonic() + 1,
    )

    assert elements == [partial]
    assert not complete


def test_windows_ocr_scale_respects_engine_dimension_limit():
    class FakeEngine:
        max_image_dimension = 3000

    assert _windows_ocr_scale(1920, _tile_bounds(1080), FakeEngine()) == 1


def test_windows_ocr_scale_reads_class_dimension_limit():
    class FakeEngine:
        max_image_dimension = 3000

    assert _windows_ocr_scale(1920, _tile_bounds(1080), FakeEngine(), FakeEngine) == 1


def test_windows_ocr_passes_use_one_engine_sequentially():
    class FakeEngine:
        active = 0
        calls = 0

        async def recognize_async(self, value):
            self.active += 1
            if self.active > 1:
                raise OSError(22, "Another RecognizeAsync operation is already running!")
            await asyncio.sleep(0)
            self.calls += 1
            self.active -= 1
            return [value]

    engine = FakeEngine()

    async def invoke(value):
        return await engine.recognize_async(value)

    results = asyncio.run(
        _run_windows_ocr_passes([lambda value=value: invoke(value) for value in range(4)])
    )
    assert results == [[0], [1], [2], [3]]
    assert engine.calls == 4


def test_windows_inverted_passes_are_per_strip_and_bounded():
    image = Image.new("RGB", (240, 480), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 12, 239, 58), fill="#ff8c00")
    draw.rectangle((0, 240, 239, 287), fill="#222222")

    strips = _windows_inverted_strips(image, [(0, 120), (120, 240), (240, 360), (360, 480)])

    assert len(strips) <= 6
    assert any(top < 60 for _band, top, _bottom in strips)
    assert any(240 <= top < 300 for _band, top, _bottom in strips)


def test_windows_ocr_boxes_map_back_using_actual_scale():
    assert _map_windows_ocr_box((20, 40, 30, 12), 100, 0.5, 0.5) == (40, 180, 60, 24)
