from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from gerald.home.mascots import DEFAULT_MASCOT, MASCOTS_BY_ID


def agents_path() -> Path:
    home = Path(os.environ.get("GERALD_HOME") or Path.home() / ".gerald")
    return home / "home_agents.json"


def load_mascot() -> str:
    try:
        data = json.loads(agents_path().read_text(encoding="utf-8"))
        mascot = data.get("mascot") if isinstance(data, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return DEFAULT_MASCOT
    return (
        mascot
        if isinstance(mascot, str) and mascot in MASCOTS_BY_ID
        else DEFAULT_MASCOT
    )


def save_mascot(mascot_id: str) -> None:
    if mascot_id not in MASCOTS_BY_ID:
        raise ValueError(f"Unknown mascot: {mascot_id}")
    path = agents_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary:
            json.dump({"mascot": mascot_id}, temporary, ensure_ascii=False)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
