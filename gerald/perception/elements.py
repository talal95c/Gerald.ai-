from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import shutil
from statistics import median
import subprocess
import threading
import time
from typing import Callable, Literal, Protocol

import numpy as np
from PIL import Image, ImageOps, ImageStat

from gerald.capture.screen import Capture, MonitorRect, capture_from_image

logger = logging.getLogger(__name__)
_WINDOWS_OCR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gerald-winocr")

ElementSource = Literal["uia", "ocr", "board"]
Rect = tuple[int, int, int, int]
WordBox = tuple[str, Rect]
OCRWord = tuple[str, Rect, float, tuple[int, int, int, int]]


def _split_ocr_words(words: list[WordBox]) -> list[list[WordBox]]:
    ordered = sorted(words, key=lambda item: item[1][0])
    if not ordered:
        return []
    separators = {"|", "·", "•", "›", "»", "/", "–"}
    heights = [max(1, rect[3]) for word, rect in ordered if word.strip() not in separators]
    if not heights:
        return []
    gap_limit = 1.2 * median(heights)
    groups: list[list[WordBox]] = []
    current: list[WordBox] = []
    for word, rect in ordered:
        if word.strip() in separators:
            if current:
                groups.append(current)
                current = []
            continue
        if current:
            previous = current[-1][1]
            gap = rect[0] - (previous[0] + previous[2])
            if gap > gap_limit:
                groups.append(current)
                current = []
        current.append((word, rect))
    if current:
        groups.append(current)
    return groups


@dataclass(frozen=True)
class Element:
    id: int
    role: str
    name: str
    rect: Rect
    source: ElementSource
    word_boxes: tuple[tuple[str, Rect], ...] = ()


class ElementProvider(Protocol):
    def get_elements(self, capture: Capture) -> list[Element]: ...


def _intersects(rect: Rect, monitor: tuple[int, int, int, int]) -> bool:
    x, y, width, height = rect
    left, top, right, bottom = monitor
    return width > 0 and height > 0 and x < right and x + width > left and y < bottom and y + height > top


@dataclass(frozen=True)
class ElementCollection:
    elements: list[Element]
    ocr_seconds: float
    complete: bool


def _rect_iou(first: Rect, second: Rect) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = first[2] * first[3] + second[2] * second[3] - intersection
    return intersection / union if union > 0 else 0.0


def _dedupe_ocr_words(words: list[OCRWord]) -> list[OCRWord]:
    accepted: list[OCRWord] = []
    for word in sorted(words, key=lambda item: (item[2], len(item[0])), reverse=True):
        if any(_rect_iou(word[1], existing[1]) > 0.5 for existing in accepted):
            continue
        accepted.append(word)
    return accepted


def _group_ocr_words(words: list[OCRWord]) -> list[list[OCRWord]]:
    if not words:
        return []
    typical_height = median(max(1, word[1][3]) for word in words)
    rows: list[list[OCRWord]] = []
    ordered = sorted(words, key=lambda word: (word[1][1] + word[1][3] / 2, word[1][0]))
    for word in ordered:
        _text, (_x, y, _width, height), _confidence, _line = word
        center_y = y + height / 2
        candidates: list[tuple[float, list[OCRWord]]] = []
        for row in rows:
            top = min(item[1][1] for item in row)
            bottom = max(item[1][1] + item[1][3] for item in row)
            row_height = max(1, bottom - top)
            overlap = max(0, min(y + height, bottom) - max(y, top)) / min(height, row_height)
            row_center = (top + bottom) / 2
            distance = abs(center_y - row_center)
            if overlap >= 0.5 or distance <= max(3, typical_height * 0.55):
                candidates.append((distance, row))
        if candidates:
            min(candidates, key=lambda candidate: candidate[0])[1].append(word)
        else:
            rows.append([word])
    return sorted(rows, key=lambda row: min(word[1][1] for word in row))


def _elements_from_ocr_words(words: list[OCRWord], capture: Capture) -> list[Element]:
    result: list[Element] = []
    for row in _group_ocr_words(words):
        word_boxes = [
            (word, rect)
            for word, rect, _confidence, _line in sorted(row, key=lambda item: item[1][0])
        ]
        for segment in _split_ocr_words(word_boxes):
            name = " ".join(word for word, _rect in segment).strip()
            if not name or not any(character.isalnum() for character in name):
                continue
            left = min(rect[0] for _word, rect in segment)
            top = min(rect[1] for _word, rect in segment)
            right = max(rect[0] + rect[2] for _word, rect in segment)
            bottom = max(rect[1] + rect[3] for _word, rect in segment)
            result.append(
                Element(
                    len(result),
                    "text",
                    name,
                    capture.full_rect_to_screen((left, top, right - left, bottom - top)),
                    "ocr",
                    tuple(
                        (word, capture.full_rect_to_screen(rect))
                        for word, rect in segment
                    ),
                )
            )
    return result


def _tile_bounds(image_height: int, tile_count: int = 4, overlap: int = 48) -> list[tuple[int, int]]:
    boundaries = [round(image_height * index / tile_count) for index in range(tile_count + 1)]
    return [
        (
            max(0, boundaries[index] - (overlap // 2 if index else 0)),
            min(
                image_height,
                boundaries[index + 1] + (overlap - overlap // 2 if index + 1 < tile_count else 0),
            ),
        )
        for index in range(tile_count)
    ]


def _windows_ocr_scale(
    source_width: int,
    bands: list[tuple[int, int]],
    engine,
    engine_type=None,
) -> float:
    max_dimension = 4096
    owners = (engine_type, type(engine), engine)
    for owner in owners:
        if owner is None:
            continue
        try:
            value = int(owner.max_image_dimension)
        except Exception:
            continue
        if value > 0:
            max_dimension = value
            break
    max_band_height = max((bottom - top for top, bottom in bands), default=1)
    if source_width * 2 <= max_dimension and max_band_height * 2 <= max_dimension:
        return 2.0
    if source_width <= max_dimension and max_band_height <= max_dimension:
        return 1.0
    return min(max_dimension / source_width, max_dimension / max_band_height)


def _map_windows_ocr_box(
    box: tuple[float, float, float, float],
    source_top: int,
    scale_x: float,
    scale_y: float,
) -> Rect:
    left, top, width, height = box
    return (
        round(left / scale_x),
        source_top + round(top / scale_y),
        max(1, round(width / scale_x)),
        max(1, round(height / scale_y)),
    )


def _windows_inverted_strips(
    source: Image.Image,
    bands: list[tuple[int, int]],
    *,
    strip_height: int = 48,
    limit: int = 6,
) -> list[tuple[int, int, int]]:
    candidates = []
    for band_index, (band_top, band_bottom) in enumerate(bands):
        for strip_top in range(band_top, band_bottom, strip_height):
            strip_bottom = min(band_bottom, strip_top + strip_height)
            strip = source.crop((0, strip_top, source.width, strip_bottom))
            luminance = ImageStat.Stat(strip.convert("L")).mean[0]
            saturation = ImageStat.Stat(strip.convert("HSV")).mean[1]
            if luminance < 140 or saturation > 16:
                candidates.append(
                    (max(255 - luminance, saturation), band_index, strip_top, strip_bottom)
                )
    selected = sorted(candidates, reverse=True)[:limit]
    return [(band_index, top, bottom) for _score, band_index, top, bottom in selected]


def _tesseract_inverted_regions(
    source: Image.Image,
    bands: list[tuple[int, int]],
    *,
    limit: int = 6,
) -> list[tuple[int, int, int, int]]:
    regions = []
    narrow_bands = []
    for band_top, band_bottom in bands:
        top = band_top
        while top < band_bottom:
            narrow_bands.append((top, min(band_bottom, top + 48)))
            top += 32
    for _band_index, top, bottom in _windows_inverted_strips(
        source, narrow_bands, limit=limit
    ):
        strip = source.crop((0, top, source.width, bottom))
        saturation = np.asarray(strip.convert("HSV"))[:, :, 1]
        active = np.count_nonzero(saturation > 96, axis=0) >= max(4, strip.height // 10)
        runs = []
        start = None
        for x, selected in enumerate(active):
            if selected and start is None:
                start = x
            elif not selected and start is not None:
                if x - start >= 30:
                    runs.append((start, x))
                start = None
        if start is not None and source.width - start >= 30:
            runs.append((start, source.width))
        if runs:
            regions.extend(
                (
                    max(0, left - 24),
                    max(0, top - 20),
                    min(source.width, right + 24),
                    min(source.height, bottom + 20),
                )
                for left, right in runs
            )
        elif ImageStat.Stat(strip.convert("L")).mean[0] < 140:
            regions.append((0, top, source.width, bottom))
    return list(dict.fromkeys(regions))


async def _run_windows_ocr_passes(
    passes: list[Callable[[], Awaitable[list[OCRWord]]]],
) -> list[list[OCRWord]]:
    results = []
    for run_pass in passes:
        results.append(await run_pass())
    return results


class UIAProvider:
    interactive_types = {
        "ButtonControl",
        "CheckBoxControl",
        "ComboBoxControl",
        "EditControl",
        "HyperlinkControl",
        "ListItemControl",
        "MenuItemControl",
        "RadioButtonControl",
        "SliderControl",
        "TabItemControl",
        "TreeItemControl",
    }

    def get_elements(self, capture: Capture) -> list[Element]:
        if os.name != "nt":
            return []
        try:
            import uiautomation as auto

            try:
                auto.SetGlobalSearchTimeout(0.05)
            except AttributeError:
                pass
            root = auto.GetForegroundControl()
            if root is None:
                return []
            deadline = time.monotonic() + 0.4
            monitor = capture.monitor
            bounds = (
                monitor.left,
                monitor.top,
                monitor.left + monitor.width,
                monitor.top + monitor.height,
            )
            found: list[Element] = []
            queue = deque([(root, 0)])
            visited = 0
            while queue and len(found) < 150 and visited < 500 and time.monotonic() < deadline:
                control, depth = queue.popleft()
                visited += 1
                try:
                    rect = control.BoundingRectangle
                    x, y = int(rect.left), int(rect.top)
                    width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
                    name = str(control.Name or "").strip()
                    role = str(control.ControlTypeName or "Control")
                    offscreen = bool(getattr(control, "IsOffscreen", False))
                    if not offscreen and _intersects((x, y, width, height), bounds):
                        if role in self.interactive_types or name:
                            found.append(Element(len(found), role.removesuffix("Control"), name, (x, y, width, height), "uia"))
                    if depth < 25 and time.monotonic() < deadline:
                        children = control.GetChildren()
                        queue.extend((child, depth + 1) for child in children[:300])
                except Exception:
                    logger.debug("Skipping inaccessible UI Automation control", exc_info=True)
            return found[:150]
        except Exception:
            logger.debug("UI Automation provider unavailable", exc_info=True)
            return []


class OCRProvider:
    def __init__(
        self,
        *,
        psm: int = 11,
        upscale: bool | None = None,
        backend: Literal["auto", "tesseract", "windows"] = "auto",
    ) -> None:
        if backend not in {"auto", "tesseract", "windows"}:
            raise ValueError("backend must be auto, tesseract, or windows")
        self.psm = psm
        self.upscale = upscale
        self.backend = backend

    def get_elements(self, capture: Capture) -> list[Element]:
        elements, _complete, _seconds = self.get_elements_detailed(capture)
        return elements

    def get_elements_detailed(
        self,
        capture: Capture,
        *,
        deadline: float | None = None,
        on_partial: Callable[[list[Element]], None] | None = None,
    ) -> tuple[list[Element], bool, float]:
        started = time.monotonic()
        try:
            backend = "windows" if self.backend == "auto" and os.name == "nt" else self.backend
            if backend == "auto":
                backend = "tesseract"
            if backend == "windows":
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                if remaining == 0:
                    return [], False, time.monotonic() - started
                partial: list[Element] = []
                partial_lock = threading.Lock()

                def publish(elements: list[Element]) -> None:
                    nonlocal partial
                    with partial_lock:
                        partial = elements
                    if on_partial is not None:
                        on_partial(elements)

                future = _WINDOWS_OCR_EXECUTOR.submit(
                    self._windows_ocr,
                    capture,
                    remaining,
                    publish,
                )
                try:
                    result = future.result(timeout=remaining)
                except TimeoutError:
                    future.cancel()
                    with partial_lock:
                        result = partial
                    return result, False, time.monotonic() - started
                return result, True, time.monotonic() - started
            import pytesseract

            language = _tesseract_languages()
            image = capture.full_image or capture.image
            can_upscale = (
                capture.monitor.width <= 1920
                and image.width == capture.monitor.width
                and image.height == capture.monitor.height
            )
            image_scale = 2 if self.upscale is True or (self.upscale is None and can_upscale) else 1
            tile_specs = _tile_bounds(image.height)
            header_height = min(image.height, max(160, round(image.height * 0.18)))
            compact_header_height = min(image.height, max(80, round(image.height * 0.09)))
            if deadline is not None and deadline <= time.monotonic():
                return [], False, time.monotonic() - started

            def recognize(
                tile_index: int,
                top: int,
                bottom: int,
                inverted: bool = False,
                left: int = 0,
                right: int | None = None,
            ) -> list[OCRWord]:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return []
                tile = image.crop((left, top, right or image.width, bottom))
                if inverted:
                    tile = ImageOps.invert(tile.convert("RGB"))
                recognition_scale = 1 if inverted else image_scale
                if recognition_scale != 1:
                    tile = tile.resize(
                        (tile.width * recognition_scale, tile.height * recognition_scale),
                        Image.Resampling.LANCZOS,
                    )
                kwargs = {
                    "output_type": pytesseract.Output.DICT,
                    "config": f"--psm {6 if inverted else self.psm} -c omp_thread_limit=1",
                    "lang": language,
                }
                if remaining is not None:
                    kwargs["timeout"] = max(0.05, remaining)
                data = pytesseract.image_to_data(tile, **kwargs)
                found: list[OCRWord] = []
                for index, raw_word in enumerate(data["text"]):
                    text = str(raw_word).strip()
                    try:
                        confidence = float(data["conf"][index])
                    except (TypeError, ValueError):
                        continue
                    if not text or confidence < 50 or not any(character.isalnum() for character in text):
                        continue
                    word_left = left + round(int(data["left"][index]) / recognition_scale)
                    local_top = round(int(data["top"][index]) / recognition_scale)
                    width = max(1, round(int(data["width"][index]) / recognition_scale))
                    height = max(1, round(int(data["height"][index]) / recognition_scale))
                    line = (
                        tile_index,
                        int(data["block_num"][index]),
                        int(data["par_num"][index]),
                        int(data["line_num"][index]),
                    )
                    found.append(
                        (text, (word_left, top + local_top, width, height), confidence, line)
                    )
                return found

            words: list[OCRWord] = []
            for tile_index, header_bottom in (
                (len(tile_specs), compact_header_height),
                (len(tile_specs) + 1, header_height),
            ):
                try:
                    words.extend(recognize(tile_index, 0, header_bottom))
                except Exception:
                    logger.debug("Tesseract header crop failed", exc_info=True)
                if on_partial is not None:
                    on_partial(_elements_from_ocr_words(_dedupe_ocr_words(words), capture))

            executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gerald-ocr")
            futures = {
                executor.submit(recognize, index, top, bottom)
                for index, (top, bottom) in enumerate(tile_specs)
            }
            pending = set(futures)
            tile_failed = False
            try:
                while pending:
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        break
                    completed, pending = wait(
                        pending,
                        timeout=remaining,
                        return_when=FIRST_COMPLETED,
                    )
                    if not completed:
                        break
                    for future in completed:
                        try:
                            words.extend(future.result())
                        except Exception:
                            tile_failed = True
                            logger.debug("Tesseract tile failed", exc_info=True)
                    current = _elements_from_ocr_words(_dedupe_ocr_words(words), capture)
                    if on_partial is not None:
                        on_partial(current)
                complete = not pending and not tile_failed
            finally:
                for future in pending:
                    future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
            result = _elements_from_ocr_words(_dedupe_ocr_words(words), capture)
            for strip_index, (left, top, right, bottom) in enumerate(
                _tesseract_inverted_regions(image, tile_specs, limit=6)
            ):
                if deadline is not None and deadline <= time.monotonic():
                    break
                try:
                    words.extend(
                        recognize(
                            len(tile_specs) + 2 + strip_index,
                            top,
                            bottom,
                            inverted=True,
                            left=left,
                            right=right,
                        )
                    )
                except Exception:
                    logger.debug("Tesseract inverted strip failed", exc_info=True)
                if on_partial is not None:
                    on_partial(_elements_from_ocr_words(_dedupe_ocr_words(words), capture))
            result = _elements_from_ocr_words(_dedupe_ocr_words(words), capture)
            return result, complete, time.monotonic() - started
        except Exception:
            logger.debug("OCR provider unavailable", exc_info=True)
            return [], True, time.monotonic() - started

    @staticmethod
    def _windows_ocr(
        capture: Capture,
        timeout: float | None = None,
        on_partial: Callable[[list[Element]], None] | None = None,
    ) -> list[Element]:
        async def recognize() -> list[Element]:
            try:
                from winrt.windows.graphics.imaging import BitmapDecoder
                from winrt.windows.media.ocr import OcrEngine
                from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
            except ImportError:
                from winsdk.windows.graphics.imaging import BitmapDecoder
                from winsdk.windows.media.ocr import OcrEngine
                from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

            import io

            source = capture.full_image or capture.image
            bands = _tile_bounds(source.height)
            engine = OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                return []
            scale = _windows_ocr_scale(source.width, bands, engine, OcrEngine)
            scaled_width = max(1, round(source.width * scale))
            scaled_height = max(1, round(source.height * scale))
            scale_x = scaled_width / source.width
            scale_y = scaled_height / source.height
            image = source.resize(
                (scaled_width, scaled_height),
                Image.Resampling.LANCZOS,
            ) if (scaled_width, scaled_height) != source.size else source
            words: list[OCRWord] = []

            async def recognize_pass(
                tile: Image.Image,
                source_top: int,
                band_index: int,
                inverted: bool,
            ) -> list[OCRWord]:
                processed = ImageOps.autocontrast(tile.convert("L"))
                if inverted:
                    processed = ImageOps.invert(processed)
                buffer = io.BytesIO()
                processed.save(buffer, format="PNG")
                stream = InMemoryRandomAccessStream()
                writer = DataWriter(stream)
                writer.write_bytes(buffer.getvalue())
                await writer.store_async()
                await writer.flush_async()
                writer.detach_stream()
                stream.seek(0)
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                result = await engine.recognize_async(bitmap)
                found: list[OCRWord] = []
                for line_index, line in enumerate(result.lines):
                    for word_index, word in enumerate(line.words):
                        text = str(word.text).strip()
                        if not text or not any(character.isalnum() for character in text):
                            continue
                        box = word.bounding_rect
                        rect = _map_windows_ocr_box(
                            (float(box.x), float(box.y), float(box.width), float(box.height)),
                            source_top,
                            scale_x,
                            scale_y,
                        )
                        confidence = float(getattr(word, "confidence", 0.5))
                        found.append(
                            (
                                text,
                                rect,
                                confidence,
                                (band_index, line_index, int(inverted), word_index),
                            )
                        )
                return found

            failure_logged = False

            def log_pass_failure() -> None:
                nonlocal failure_logged
                if not failure_logged:
                    logger.warning("Windows OCR pass failed", exc_info=True)
                    failure_logged = True

            for band_index, (source_top, source_bottom) in enumerate(bands):
                top = round(source_top * scale_y)
                bottom = round(source_bottom * scale_y)
                tile = image.crop((0, top, image.width, bottom))
                try:
                    results = await _run_windows_ocr_passes(
                        [lambda: recognize_pass(tile, source_top, band_index, False)]
                    )
                    words.extend(results[0])
                except Exception:
                    log_pass_failure()
                elements = _elements_from_ocr_words(_dedupe_ocr_words(words), capture)
                if on_partial is not None:
                    on_partial(elements)

            for band_index, source_top, source_bottom in _windows_inverted_strips(source, bands):
                top = round(source_top * scale_y)
                bottom = round(source_bottom * scale_y)
                tile = image.crop((0, top, image.width, bottom))
                try:
                    results = await _run_windows_ocr_passes(
                        [lambda: recognize_pass(tile, source_top, band_index, True)]
                    )
                    words.extend(results[0])
                except Exception:
                    log_pass_failure()
                elements = _elements_from_ocr_words(_dedupe_ocr_words(words), capture)
                if on_partial is not None:
                    on_partial(elements)
            return _elements_from_ocr_words(_dedupe_ocr_words(words), capture)

        async def recognize_with_timeout() -> list[Element]:
            return await recognize() if timeout is None else await asyncio.wait_for(recognize(), timeout=timeout)

        return asyncio.run(recognize_with_timeout())


def ocr_image_text(image: Image.Image) -> str:
    try:
        rgb = image.convert("RGB")
        capture = capture_from_image(
            rgb,
            MonitorRect(0, 0, rgb.width, rgb.height),
            max_width=max(1, rgb.width),
        )
        elements = OCRProvider().get_elements(capture)
        return "\n".join(element.name for element in sorted(elements, key=lambda item: (item.rect[1], item.rect[0])))
    except Exception:
        logger.debug("OCR image text extraction failed", exc_info=True)
        return ""


def collect_elements(
    capture: Capture,
    uia_provider: ElementProvider | None = None,
    ocr_provider: ElementProvider | None = None,
    *,
    budget: float | None = None,
) -> list[Element]:
    return collect_elements_detailed(
        capture,
        uia_provider,
        ocr_provider,
        budget=budget,
    ).elements


def collect_elements_detailed(
    capture: Capture,
    uia_provider: ElementProvider | None = None,
    ocr_provider: ElementProvider | None = None,
    *,
    budget: float | None = None,
    started_at: float | None = None,
    on_update: Callable[[list[Element]], None] | None = None,
) -> ElementCollection:
    collection_started = started_at if started_at is not None else time.monotonic()
    deadline = collection_started + budget if budget is not None else None
    try:
        uia = (uia_provider or UIAProvider()).get_elements(capture)
    except Exception:
        logger.warning("UIA element collection failed", exc_info=True)
        uia = []

    def merge(ocr: list[Element]) -> list[Element]:
        result = list(uia[:150])
        suppressing_roles = {
            "button",
            "splitbutton",
            "menuitem",
            "hyperlink",
            "tabitem",
            "checkbox",
            "radiobutton",
            "listitem",
            "treeitem",
            "headeritem",
            "text",
            "combobox",
        }

        def normalized_name(name: str) -> str:
            return " ".join(
                "".join(character if character.isalnum() else " " for character in name.casefold()).split()
            )

        for candidate in ocr:
            cx, cy, cw, ch = candidate.rect
            candidate_name = normalized_name(candidate.name)
            suppressed = bool(candidate_name) and any(
                element.role.casefold().rsplit(".", maxsplit=1)[-1].removesuffix("control")
                in suppressing_roles
                and element.rect[0] <= cx
                and element.rect[1] <= cy
                and element.rect[0] + element.rect[2] >= cx + cw
                and element.rect[1] + element.rect[3] >= cy + ch
                and element.rect[2] * element.rect[3] <= 6 * cw * ch
                and f" {candidate_name} " in f" {normalized_name(element.name)} "
                for element in uia[:150]
            )
            if not suppressed:
                result.append(candidate)
        final = []
        for index, element in enumerate(result[:300]):
            image_rect = capture.rect_to_image(element.rect)
            word_boxes = tuple(
                (word, capture.rect_to_image(rect))
                for word, rect in element.word_boxes
            )
            final.append(Element(index, element.role, element.name, image_rect, element.source, word_boxes))
        return final

    if on_update is not None:
        on_update(merge([]))
    provider = ocr_provider or OCRProvider()
    ocr_started = time.monotonic()
    try:
        if isinstance(provider, OCRProvider):
            ocr, complete, _provider_seconds = provider.get_elements_detailed(
                capture,
                deadline=deadline,
                on_partial=lambda partial: on_update(merge(partial)) if on_update is not None else None,
            )
        else:
            ocr = provider.get_elements(capture)
            complete = True
    except Exception:
        logger.warning("OCR element collection failed", exc_info=True)
        ocr = []
        complete = True
    ocr_seconds = time.monotonic() - ocr_started
    elements = merge(ocr)
    if on_update is not None:
        on_update(elements)
    if not complete and budget is not None:
        logger.warning(
            "OCR budget expired after %.3fs; returning %d partial elements",
            ocr_seconds,
            len(elements),
        )
    elif not complete:
        logger.warning("OCR returned incomplete tile results; returning %d partial elements", len(elements))
    return ElementCollection(elements, ocr_seconds, complete)


@lru_cache(maxsize=1)
def _tesseract_languages() -> str:
    try:
        import pytesseract

        available = set(pytesseract.get_languages(config="", timeout=0.2))
    except Exception:
        return "eng"
    preferred = [language for language in ("fra", "eng") if language in available]
    fallback = sorted(available - {"osd"})
    return "+".join(preferred) or (fallback[0] if fallback else "eng")


def active_window_context() -> tuple[str, str]:
    try:
        if os.name == "nt":
            import ctypes
            import psutil

            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            executable = psutil.Process(pid.value).name()
            return executable, title_buffer.value
    except Exception:
        logger.debug("Unable to read active window details", exc_info=True)
    try:
        executable = "unknown"
        title = ""
        if shutil.which("xdotool"):
            window_id = subprocess.run(
                ["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=0.2, check=True
            ).stdout.strip()
            title = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True,
                text=True,
                timeout=0.2,
                check=True,
            ).stdout.strip()
            pid = subprocess.run(
                ["xdotool", "getwindowpid", window_id],
                capture_output=True,
                text=True,
                timeout=0.2,
                check=True,
            ).stdout.strip()
            import psutil

            executable = psutil.Process(int(pid)).name()
        return executable, title
    except Exception:
        logger.debug("Unable to read active window details with xdotool", exc_info=True)
    return "unknown", ""


def serialize_context(
    elements: list[Element],
    image_width: int,
    image_height: int,
    max_chars: int = 6000,
    app_name: str | None = None,
    window_title: str | None = None,
) -> str:
    if app_name is None or window_title is None:
        detected_app, detected_title = active_window_context()
        app_name = detected_app if app_name is None else app_name
        window_title = detected_title if window_title is None else window_title
    header = (
        f"SCREEN CONTEXT\nActive app: {app_name}\n"
        f"Window title: {window_title[:120]}\n"
        f"Image size: {image_width}x{image_height}\nElements:"
    )
    header = header[:max_chars]
    lines = []
    used = len(header) + 1
    for element in elements:
        name = element.name.replace('"', "'")[:60]
        x, y, width, height = element.rect
        line = f'[{element.id}] {element.role} "{name}" ({x},{y},{width},{height})'
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return header + ("\n" + "\n".join(lines) if lines else "")
