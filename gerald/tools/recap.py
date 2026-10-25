from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

logger = logging.getLogger(__name__)


def save_recap(markdown: str, home: Path | None = None, *, open_file: bool = True) -> Path:
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("markdown must be a non-empty string")
    lessons = (home or Path.home()) / "Gerald" / "lessons"
    lessons.mkdir(parents=True, exist_ok=True)
    path = lessons / f"{datetime.now():%Y-%m-%d_%H-%M}.md"
    path.write_text(markdown.strip() + "\n", encoding="utf-8")
    if open_file:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen(
                    [opener, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError:
            logger.warning("Could not open lesson recap %s", path, exc_info=True)
    return path
