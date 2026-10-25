from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

_FONT_FILES = (
    "Inter-Regular.otf",
    "Inter-Medium.otf",
    "Inter-SemiBold.otf",
    "Inter-Bold.otf",
)
_loaded_fonts: dict[str, int] = {}
_font_families: list[str] = []


def ensure_fonts() -> list[str]:
    if QApplication.instance() is None:
        return []

    font_dir = Path(__file__).parent
    for filename in _FONT_FILES:
        if filename in _loaded_fonts:
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_dir / filename))
        if font_id < 0:
            continue
        _loaded_fonts[filename] = font_id
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in _font_families:
                _font_families.append(family)

    return list(_font_families)
