from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class MonitorRect:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class Capture:
    monitor: MonitorRect
    scale: float
    image: Image.Image
    data_url: str

    @property
    def image_width(self) -> int:
        return self.image.width

    @property
    def image_height(self) -> int:
        return self.image.height

    def img_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.monitor.left + x / self.scale,
            self.monitor.top + y / self.scale,
        )

    def screen_to_img(self, x: float, y: float) -> tuple[float, float]:
        return (
            (x - self.monitor.left) * self.scale,
            (y - self.monitor.top) * self.scale,
        )

    def rect_to_image(self, rect: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        x, y, width, height = rect
        image_x, image_y = self.screen_to_img(x, y)
        return (
            round(image_x),
            round(image_y),
            round(width * self.scale),
            round(height * self.scale),
        )


def capture_from_image(
    image: Image.Image,
    monitor: MonitorRect,
    max_width: int = 1280,
) -> Capture:
    source = image.convert("RGB")
    scale = min(1.0, max_width / source.width)
    if scale < 1.0:
        size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
        source = source.resize(size, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    source.save(output, format="JPEG", quality=80, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return Capture(monitor, scale, source, f"data:image/jpeg;base64,{encoded}")


def capture_screen(max_width: int = 1280) -> Capture:
    import mss
    from pynput.mouse import Controller

    with mss.mss() as screen:
        monitors = screen.monitors[1:]
        if not monitors:
            raise RuntimeError("No screen monitors are available")
        try:
            cursor_x, cursor_y = Controller().position
            selected = next(
                (
                    monitor
                    for monitor in monitors
                    if monitor["left"] <= cursor_x < monitor["left"] + monitor["width"]
                    and monitor["top"] <= cursor_y < monitor["top"] + monitor["height"]
                ),
                monitors[0],
            )
        except Exception:
            selected = monitors[0]
        shot = screen.grab(selected)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        rect = MonitorRect(
            int(selected["left"]),
            int(selected["top"]),
            int(selected["width"]),
            int(selected["height"]),
        )
    return capture_from_image(image, rect, max_width)
