from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from PIL import Image

logger = logging.getLogger(__name__)

def has_file_association(suffix: str) -> bool:
    if os.name != "nt":
        return True
    from ctypes import wintypes

    query = ctypes.WinDLL("shlwapi").AssocQueryStringW
    query.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    query.restype = ctypes.c_long
    buffer = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(buffer))
    result = query(0x400, 2, suffix, None, buffer, ctypes.byref(size))
    return result == 0 and bool(buffer.value)


def save_recap(
    markdown: str,
    home: Path | None = None,
    *,
    open_file: bool = True,
    board_image: Image.Image | None = None,
) -> Path:
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("markdown must be a non-empty string")
    lessons = (home or Path.home()) / "Gerald" / "lessons"
    lessons.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now():%Y-%m-%d_%H-%M}"
    suffix = 1
    while True:
        path = lessons / f"{stem}{'' if suffix == 1 else f'-{suffix}'}.md"
        try:
            with path.open("x", encoding="utf-8") as recap_file:
                recap_file.write(markdown.strip() + "\n")
            break
        except FileExistsError:
            suffix += 1
    if open_file:
        if os.name == "nt":
            def open_notepad() -> None:
                subprocess.Popen(
                    ["notepad.exe", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            opened = False
            if has_file_association(path.suffix):
                try:
                    os.startfile(str(path))  # type: ignore[attr-defined]
                    opened = True
                except OSError:
                    pass
            if not opened:
                try:
                    open_notepad()
                except OSError:
                    logger.warning("Could not open lesson recap %s", path, exc_info=True)
        else:
            try:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen(
                    [opener, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError:
                logger.warning("Could not open lesson recap %s", path, exc_info=True)
    if board_image is not None:
        suffix = 1
        while True:
            image_path = lessons / f"board{'' if suffix == 1 else f'-{suffix}'}.png"
            try:
                with image_path.open("xb") as image_file:
                    board_image.save(image_file, format="PNG")
                break
            except FileExistsError:
                suffix += 1
    return path
