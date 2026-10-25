from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QFontDatabase

_families: list[str] | None = None


def ensure_fonts() -> list[str]:
    global _families
    if _families is not None:
        return list(_families)
    package_fonts = Path(__file__).with_name("webui") / "fonts"
    source_fonts = Path(__file__).parents[2] / "web" / "src" / "assets" / "fonts"
    families = []
    for filename in ("GoogleSansFlex.ttf", "Abel-Regular.ttf"):
        path = next(
            (candidate / filename for candidate in (package_fonts, source_fonts) if (candidate / filename).is_file()),
            None,
        )
        if path is None:
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    _families = list(dict.fromkeys(families))
    return list(_families)
