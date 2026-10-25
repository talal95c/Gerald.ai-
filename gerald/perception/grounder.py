from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
import io
import json
import logging
import math
import os
import re
import urllib.request
from typing import Protocol

from PIL import Image

logger = logging.getLogger(__name__)
MOONDREAM_REVISION = "2025-06-21"
MAX_PIXELS = 16384 * 28 * 28
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gerald-grounder")
_instances: dict[tuple[str, str, str], Grounder] = {}


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


def configured_grounder(backend: str | None = None) -> Grounder | None:
    backend = (backend or os.getenv("GERALD_GROUNDER", "none")).casefold()
    if backend in {"", "none"}:
        return None
    model = os.getenv("GERALD_GROUNDER_MODEL", "bytedance/ui-tars-1.5-7b")
    coord_mode = os.getenv("GERALD_GROUNDER_COORD_MODE", "")
    key = backend, model, coord_mode
    if key in _instances:
        return _instances[key]
    if backend == "openrouter":
        if not coord_mode:
            coord_mode = "norm1000" if model == "qwen/qwen3.5-27b" else "abs_resized"
        instance: Grounder = OpenRouterGrounder(model, coord_mode)
    elif backend == "moondream":
        instance = MoondreamLocalGrounder()
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
