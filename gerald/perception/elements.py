from __future__ import annotations

import asyncio
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import shutil
from statistics import median
import subprocess
import time
from typing import Callable, Literal, Protocol

from PIL import Image

from gerald.capture.screen import Capture

logger = logging.getLogger(__name__)

ElementSource = Literal["uia", "ocr"]
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
    for word in sorted(words, key=lambda item: item[2], reverse=True):
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
            stack: list[tuple[object, int]] = [(root, 0)]
            visited = 0
            while stack and len(found) < 150 and visited < 500 and time.monotonic() < deadline:
                control, depth = stack.pop()
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
                        stack.extend((child, depth + 1) for child in children[:300])
                except Exception:
                    logger.debug("Skipping inaccessible UI Automation control", exc_info=True)
            return found[:150]
        except Exception:
            logger.debug("UI Automation provider unavailable", exc_info=True)
            return []


class OCRProvider:
    def __init__(self, *, psm: int = 11, upscale: bool | None = None) -> None:
        self.psm = psm
        self.upscale = upscale

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
            if os.name == "nt":
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                if remaining == 0:
                    return [], False, time.monotonic() - started
                try:
                    result = self._windows_ocr(capture, timeout=remaining)
                except TimeoutError:
                    return [], False, time.monotonic() - started
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

            def recognize(tile_index: int, top: int, bottom: int) -> list[OCRWord]:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return []
                tile = image.crop((0, top, image.width, bottom))
                if image_scale != 1:
                    tile = tile.resize(
                        (tile.width * image_scale, tile.height * image_scale),
                        Image.Resampling.LANCZOS,
                    )
                kwargs = {
                    "output_type": pytesseract.Output.DICT,
                    "config": f"--psm {self.psm} -c omp_thread_limit=1",
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
                    left = round(int(data["left"][index]) / image_scale)
                    local_top = round(int(data["top"][index]) / image_scale)
                    width = max(1, round(int(data["width"][index]) / image_scale))
                    height = max(1, round(int(data["height"][index]) / image_scale))
                    line = (
                        tile_index,
                        int(data["block_num"][index]),
                        int(data["par_num"][index]),
                        int(data["line_num"][index]),
                    )
                    found.append(
                        (text, (left, top + local_top, width, height), confidence, line)
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
            return result, complete, time.monotonic() - started
        except Exception:
            logger.debug("OCR provider unavailable", exc_info=True)
            return [], True, time.monotonic() - started

    @staticmethod
    def _windows_ocr(capture: Capture, timeout: float | None = None) -> list[Element]:
        async def recognize() -> list[Element]:
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

            png = capture.full_image or capture.image
            import io

            buffer = io.BytesIO()
            png.save(buffer, format="PNG")
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(buffer.getvalue())
            await writer.store_async()
            await writer.flush_async()
            writer.detach_stream()
            stream.seek(0)
            decoder = await BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()
            engine = OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                return []
            result = await engine.recognize_async(bitmap)
            output = []
            for line in result.lines:
                words = [
                    (
                        str(word.text),
                        (
                            int(word.bounding_rect.x),
                            int(word.bounding_rect.y),
                            int(word.bounding_rect.width),
                            int(word.bounding_rect.height),
                        ),
                    )
                    for word in line.words
                ]
                for segment in _split_ocr_words(words):
                    left = min(rect[0] for _word, rect in segment)
                    top = min(rect[1] for _word, rect in segment)
                    right = max(rect[0] + rect[2] for _word, rect in segment)
                    bottom = max(rect[1] + rect[3] for _word, rect in segment)
                    output.append(
                        Element(
                            len(output),
                            "text",
                            " ".join(word for word, _rect in segment),
                            capture.full_rect_to_screen((left, top, right - left, bottom - top)),
                            "ocr",
                            tuple(
                                (word, capture.full_rect_to_screen(rect))
                                for word, rect in segment
                            ),
                        )
                    )
            return output

        async def recognize_with_timeout() -> list[Element]:
            if timeout is None:
                return await recognize()
            return await asyncio.wait_for(recognize(), timeout=timeout)

        return asyncio.run(recognize_with_timeout())


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
        for candidate in ocr:
            cx, cy, cw, ch = candidate.rect
            image_area = max(1, cw * ch)
            overlaps = any(
                max(0, min(cx + cw, ex + ew) - max(cx, ex))
                * max(0, min(cy + ch, ey + eh) - max(cy, ey))
                / image_area
                > 0.5
                for element in result
                for ex, ey, ew, eh in [element.rect]
            )
            if not overlaps:
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
