from __future__ import annotations

import os
from pathlib import Path
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.overlay.window import OverlayWindow, _ScreenMapping, _confirmation_position
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import (
    ArrowCommand,
    CircleCommand,
    HighlightCommand,
    NoteCommand,
    PointCommand,
)

ROOT = Path(__file__).parents[1]
SOURCE = Path("/home/ubuntu/shot.png")
OUTPUT = ROOT / "docs" / "confirm-preview.png"


def render() -> None:
    source = Image.open(SOURCE).convert("RGB")
    width, height = source.size
    capture = capture_from_image(source, MonitorRect(0, 0, width, height), max_width=width)
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    dpr = width / 1600
    logical_width, logical_height = round(width / dpr), round(height / dpr)
    overlay.setGeometry(0, 0, logical_width, logical_height)
    overlay._screen_mappings = lambda: [
        _ScreenMapping((0, 0, width, height), (0, 0, logical_width, logical_height), dpr)
    ]
    overlay.set_capture(capture)

    sx, sy = width / 1600, height / 1200

    def rect(x: float, y: float, w: float, h: float) -> ScreenRect:
        return ScreenRect(round(x * sx), round(y * sy), round(w * sx), round(h * sy))

    mic = (round(1086 * sx), round(366 * sy))
    add_shortcut = (round(838 * sx), round(446 * sy))
    overlay.add_commands(
        [
            CircleCommand(rect(mic[0] / sx - 19, mic[1] / sy - 19, 38, 38)),
            ArrowCommand(mic, add_shortcut),
            HighlightCommand(rect(790, 415, 96, 110)),
            NoteCommand(rect(804, 500, 60, 20), "Raccourci"),
            PointCommand(rect(mic[0] / sx - 5, mic[1] / sy - 5, 10, 10)),
        ]
    )
    for mark in overlay._marks:
        mark.created -= 1

    screen = QImage(width, height, QImage.Format.Format_ARGB32)
    screen.fill(0)
    painter = QPainter(screen)
    source_image = QImage(source.tobytes(), width, height, width * 3, QImage.Format.Format_RGB888).copy()
    painter.drawImage(0, 0, source_image)
    painter.save()
    painter.scale(dpr, dpr)
    overlay.render(painter)
    painter.restore()
    target_rect = (mic[0] - round(18 * sx), mic[1] - round(18 * sy), round(36 * sx), round(36 * sy))
    overlay.show_confirmation(
        "Gerald veut cliquer ici",
        target_rect,
        threading.Event(),
        {"approved": False},
    )
    app.processEvents()
    pill = overlay._confirmation
    if pill is None:
        raise RuntimeError("Confirmation pill was not created")
    target_logical = tuple(round(value / dpr) for value in target_rect)
    pill.move(
        *_confirmation_position(
            target_logical,
            (0, 0, logical_width, logical_height),
            (pill.width(), pill.height()),
        )
    )
    app.processEvents()
    painter.save()
    painter.scale(dpr, dpr)
    pill_image = QImage(pill.size(), QImage.Format.Format_ARGB32)
    pill_image.fill(0)
    pill_painter = QPainter(pill_image)
    pill.render(pill_painter)
    pill_painter.end()
    painter.drawImage(pill.x(), pill.y(), pill_image)
    painter.restore()
    painter.end()
    screen.save(str(OUTPUT))
    overlay.close()
    pill.close()
    app.processEvents()


if __name__ == "__main__":
    render()
