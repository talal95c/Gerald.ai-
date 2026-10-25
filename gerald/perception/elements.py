from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from gerald.capture.screen import Capture

logger = logging.getLogger(__name__)

ElementSource = Literal["uia", "ocr"]
Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class Element:
    id: int
    role: str
    name: str
    rect: Rect
    source: ElementSource


class ElementProvider(Protocol):
    def get_elements(self, capture: Capture) -> list[Element]: ...


def _intersects(rect: Rect, monitor: tuple[int, int, int, int]) -> bool:
    x, y, width, height = rect
    left, top, right, bottom = monitor
    return width > 0 and height > 0 and x < right and x + width > left and y < bottom and y + height > top


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
    def get_elements(self, capture: Capture) -> list[Element]:
        try:
            if os.name == "nt":
                return self._windows_ocr(capture)
            import pytesseract

            lines = pytesseract.image_to_data(
                capture.image, output_type=pytesseract.Output.DICT, config="--psm 6"
            )
            grouped: dict[tuple[int, int, int], list[tuple[str, tuple[int, int, int, int]]]] = {}
            for index, word in enumerate(lines["text"]):
                text = str(word).strip()
                if not text or float(lines["conf"][index]) < 0:
                    continue
                key = (
                    int(lines["block_num"][index]),
                    int(lines["par_num"][index]),
                    int(lines["line_num"][index]),
                )
                rect = (
                    int(lines["left"][index]),
                    int(lines["top"][index]),
                    int(lines["width"][index]),
                    int(lines["height"][index]),
                )
                grouped.setdefault(key, []).append((text, rect))
            result = []
            for index, words in enumerate(grouped.values()):
                left = min(rect[0] for _word, rect in words)
                top = min(rect[1] for _word, rect in words)
                right = max(rect[0] + rect[2] for _word, rect in words)
                bottom = max(rect[1] + rect[3] for _word, rect in words)
                screen_left, screen_top = capture.img_to_screen(left, top)
                result.append(
                    Element(
                        index,
                        "Text",
                        " ".join(word for word, _rect in words),
                        (
                            round(screen_left),
                            round(screen_top),
                            round((right - left) / capture.scale),
                            round((bottom - top) / capture.scale),
                        ),
                        "ocr",
                    )
                )
            return result
        except Exception:
            logger.debug("OCR provider unavailable", exc_info=True)
            return []

    @staticmethod
    def _windows_ocr(capture: Capture) -> list[Element]:
        async def recognize() -> list[Element]:
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

            png = capture.image
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
            for index, line in enumerate(result.lines):
                words = list(line.words)
                if not words:
                    continue
                left = min(word.bounding_rect.x for word in words)
                top = min(word.bounding_rect.y for word in words)
                right = max(word.bounding_rect.x + word.bounding_rect.width for word in words)
                bottom = max(word.bounding_rect.y + word.bounding_rect.height for word in words)
                x, y = capture.img_to_screen(left, top)
                output.append(
                    Element(
                        index,
                        "Text",
                        str(line.text),
                        (round(x), round(y), round((right - left) / capture.scale), round((bottom - top) / capture.scale)),
                        "ocr",
                    )
                )
            return output

        return asyncio.run(recognize())


def collect_elements(
    capture: Capture,
    uia_provider: ElementProvider | None = None,
    ocr_provider: ElementProvider | None = None,
) -> list[Element]:
    try:
        uia = (uia_provider or UIAProvider()).get_elements(capture)
    except Exception:
        logger.warning("UIA element collection failed", exc_info=True)
        uia = []
    try:
        ocr = (ocr_provider or OCRProvider()).get_elements(capture)
    except Exception:
        logger.warning("OCR element collection failed", exc_info=True)
        ocr = []

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
        final.append(Element(index, element.role, element.name, image_rect, element.source))
    return final


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
