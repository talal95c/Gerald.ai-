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
