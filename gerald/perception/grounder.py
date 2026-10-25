from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
import io
import json
import logging
import math
import os
from pathlib import Path
import re
import urllib.request
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)
MOONDREAM_REVISION = "2025-06-21"
MOONDREAM_ENDPOINT = "https://api.moondream.ai/v1"
MAX_PIXELS = 16384 * 28 * 28
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gerald-grounder")
_instances: dict[tuple[str, ...], Grounder] = {}
_runtime_backend: str | None = None


class Grounder(Protocol):
    def locate(self, image: Image.Image, description: str) -> tuple[float, float] | None: ...


def smart_resize(
    height: int,
    width: int,
    factor: int = 28,
    min_pixels: int = 3136,
    max_pixels: int = MAX_PIXELS,
) -> tuple[int, int]:
    if height <= 0 or width <= 0 or factor <= 0:
        raise ValueError("image dimensions and factor must be positive")
    if max(height, width) / min(height, width) > 200:
        raise ValueError("image aspect ratio must be no greater than 200")
    resized_height = max(factor, round(height / factor) * factor)
    resized_width = max(factor, round(width / factor) * factor)
    pixels = resized_height * resized_width
    if pixels > max_pixels:
        beta = math.sqrt(height * width / max_pixels)
        resized_height = max(factor, math.floor(height / beta / factor) * factor)
        resized_width = max(factor, math.floor(width / beta / factor) * factor)
    elif pixels < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        resized_height = max(factor, math.ceil(height * beta / factor) * factor)
        resized_width = max(factor, math.ceil(width * beta / factor) * factor)
    return resized_height, resized_width


def _parse_point(text: str) -> tuple[float, float] | None:
    patterns = (
        r"start_box\s*=\s*['\"]?\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)",
        r"<point>\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*</point>",
        r"[\[(]\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*[\])]",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


@dataclass
class OpenRouterGrounder:
    model: str = "bytedance/ui-tars-1.5-7b"
    coord_mode: str = "abs_resized"
    timeout: float = 4.0
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"

    def locate(self, image: Image.Image, description: str) -> tuple[float, float] | None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        if self.coord_mode not in {"abs_resized", "norm1000"}:
            raise ValueError("coord_mode must be abs_resized or norm1000")
        original = image.convert("RGB")
        resized_height, resized_width = smart_resize(original.height, original.width)
        resized = original.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        resized.save(output, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
        prompt = (
            "Output only the coordinate of one point in your answer. "
            f"What element matches the following task: {description}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read())
        content = result["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = " ".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str):
            return None
        point = _parse_point(content)
        if point is None:
            return None
        x, y = point
        if self.coord_mode == "norm1000":
            x = x * resized_width / 1000
            y = y * resized_height / 1000
        return (
            x * original.width / resized_width,
            y * original.height / resized_height,
        )


class MoondreamLocalGrounder:
    def __init__(self, revision: str = MOONDREAM_REVISION) -> None:
        self.revision = revision
        self._model = None

    def _load_model(self):
        if self._model is None:
            import torch
            from transformers import AutoModelForCausalLM

            self._model = AutoModelForCausalLM.from_pretrained(
                "vikhyatk/moondream2",
                revision=self.revision,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            ).to("cpu")
            self._model.eval()
        return self._model

    def locate(self, image: Image.Image, description: str) -> tuple[float, float] | None:
        result = self._load_model().point(image.convert("RGB"), description)
        points = result.get("points", [])
        if not points:
            return None
        point = points[0]
        if isinstance(point, dict):
            x, y = point.get("x"), point.get("y")
        else:
            x, y = point[0], point[1]
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        return float(x) * image.width, float(y) * image.height


@dataclass
class MoondreamCloudGrounder:
    api_key: str
    model: str = "moondream3.1-9B-A2B"
    timeout: float = 4.0
    endpoint: str = MOONDREAM_ENDPOINT

    def locate(self, image: Image.Image, description: str) -> tuple[float, float] | None:
        original = image.convert("RGB")
        resized = original
        if original.width > 1568:
            height = max(1, round(original.height * 1568 / original.width))
            resized = original.resize((1568, height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        resized.save(output, format="JPEG", quality=90)
        data_url = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
        payload = {
            "model": self.model,
            "image_url": data_url,
            "object": description,
        }
        request = urllib.request.Request(
            f"{self.endpoint.rstrip('/')}/point",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Moondream-Auth": self.api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status != 200:
                raise RuntimeError(f"Moondream Cloud returned HTTP {status}")
            result = json.loads(response.read())
        points = result.get("points", []) if isinstance(result, dict) else []
        if not points:
            return None
        point = points[0]
        if not isinstance(point, dict):
            return None
        x, y = point.get("x"), point.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return None
        if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        return float(x) * image.width, float(y) * image.height


def _grounder_settings_path() -> Path:
    return Path.home() / ".gerald" / "grounder.json"


def load_moondream_cloud_settings(path: str | Path | None = None) -> dict[str, str]:
    saved: dict[str, str] = {}
    try:
        settings_path = Path(path) if path is not None else _grounder_settings_path()
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            saved = loaded
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read Moondream Cloud settings")
    endpoint = os.getenv("MOONDREAM_ENDPOINT", "").strip() or str(saved.get("endpoint", "")).strip()
    api_key = os.getenv("MOONDREAM_API_KEY", "").strip() or str(saved.get("api_key", "")).strip()
    return {
        "endpoint": endpoint.rstrip("/") or MOONDREAM_ENDPOINT,
        "api_key": api_key,
    }


def save_moondream_cloud_settings(
    endpoint: str,
    api_key: str,
    path: str | Path | None = None,
) -> Path:
    target = Path(path) if path is not None else _grounder_settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(
        {"endpoint": endpoint.strip().rstrip("/") or MOONDREAM_ENDPOINT, "api_key": api_key},
        ensure_ascii=False,
    )
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(data)
    try:
        os.chmod(target, 0o600)
    except (OSError, NotImplementedError):
        pass
    return target


def set_runtime_grounder_backend(backend: str | None) -> None:
    global _runtime_backend
    _runtime_backend = backend


def configured_grounder(backend: str | None = None) -> Grounder | None:
    backend = (backend or _runtime_backend or os.getenv("GERALD_GROUNDER", "none")).casefold()
    if backend in {"", "none"}:
        return None
    default_model = "moondream3.1-9B-A2B" if backend == "moondream-cloud" else "bytedance/ui-tars-1.5-7b"
    model = os.getenv("GERALD_GROUNDER_MODEL", default_model)
    coord_mode = os.getenv("GERALD_GROUNDER_COORD_MODE", "")
    cloud_settings = load_moondream_cloud_settings() if backend == "moondream-cloud" else None
    api_key = cloud_settings["api_key"] if cloud_settings is not None else ""
    if backend == "moondream-cloud" and not api_key:
        logger.warning("MOONDREAM_API_KEY is not set; Moondream Cloud grounding is disabled")
        return None
    endpoint = cloud_settings["endpoint"] if cloud_settings is not None else ""
    try:
        timeout = float(os.getenv("GERALD_GROUNDER_TIMEOUT", "4.0"))
    except ValueError:
        timeout = 4.0
    key = backend, model, coord_mode, api_key, endpoint, str(timeout)
    if key in _instances:
        return _instances[key]
    if backend == "openrouter":
        if not coord_mode:
            coord_mode = "norm1000" if model == "qwen/qwen3.5-27b" else "abs_resized"
        instance: Grounder = OpenRouterGrounder(model, coord_mode)
    elif backend == "moondream":
        instance = MoondreamLocalGrounder()
    elif backend == "moondream-cloud":
        instance = MoondreamCloudGrounder(api_key, model, timeout=timeout, endpoint=endpoint)
    else:
        logger.warning("Unknown GERALD_GROUNDER backend: %s", backend)
        return None
    _instances[key] = instance
    return instance


def locate_with_timeout(
    grounder: Grounder,
    image: Image.Image,
    description: str,
    timeout: float = 4.0,
) -> tuple[float, float] | None:
    future = _executor.submit(grounder.locate, image, description)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        future.cancel()
        logger.warning("Visual grounder timed out after %.1f seconds", timeout)
    except Exception:
        logger.debug("Visual grounder failed", exc_info=True)
    return None
