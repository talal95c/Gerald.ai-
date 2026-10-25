from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during source-only use
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    voice: str
    hotkey: str
    max_image_width: int


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv(Path.cwd() / ".env", override=False)
    return Settings(
        api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        model=os.getenv("GERALD_MODEL", "gpt-realtime-2").strip(),
        voice=os.getenv("GERALD_VOICE", "marin").strip(),
        hotkey=os.getenv("GERALD_HOTKEY", "ctrl+shift").strip(),
        max_image_width=max(320, int(os.getenv("GERALD_MAX_IMAGE_W", "1280"))),
    )


def set_physical_dpi_awareness() -> None:
    """Ask Windows for physical-pixel coordinates before Qt or mss starts."""
    if os.name != "nt":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
