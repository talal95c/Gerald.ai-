from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QCursor, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.overlay.window import OverlayWindow


ROOT = Path(__file__).resolve().parents[1]
SIZE = QSize(1000, 450)
FPS = 30
VIDEO_SECONDS = 8
WORK = Path.home() / "work"
FRAME_DIR = WORK / ".gerald-overlay-frames"


def _backdrop() -> QImage:
    image = QImage(SIZE, QImage.Format.Format_RGB32)
    image.fill(QColor("#FAFAFA"))
    return image


def _render_frame(base: QImage, overlay: OverlayWindow) -> QImage:
    frame = base.copy()
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    overlay.render(painter)
    painter.end()
    return frame


def _create_previews(app: QApplication, base: QImage) -> None:
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, SIZE.width(), SIZE.height())
    overlay._dark_for_physical = lambda _x, _y: False
    QCursor.setPos(260, 200)
    captions = {
        "listening": "Je t’écoute. Dis-moi ce que tu cherches.",
        "thinking": "Je parcours tes documents…",
        "speaking": "Voici ce que j’ai trouvé dans tes cours.",
    }
    for status, caption in captions.items():
        overlay.set_status(status)
        overlay.set_caption(caption)
        overlay._status_changed = time.monotonic() - 0.5
        overlay._morph_started = time.monotonic() - 0.5
        overlay._update_cursor_companion(time.monotonic())
        app.processEvents()
        output = ROOT / "docs" / f"overlay-{status}.png"
        if not _render_frame(base, overlay).save(str(output)):
            raise RuntimeError(f"Could not save {output}")
    overlay.close()
    app.processEvents()


def _create_video(app: QApplication, base: QImage) -> None:
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, SIZE.width(), SIZE.height())
    overlay._dark_for_physical = lambda _x, _y: False
    QCursor.setPos(520, 230)
    overlay.show()
    segments = (
        ("listening", "Je t’écoute.", 1.8),
        ("thinking", "Je parcours tes documents…", 2.4),
        ("speaking", "Voici ce que j’ai trouvé.", 2.4),
        ("listening", "Je t’écoute.", 1.4),
    )
    states = [(status, caption, length) for status, caption, length in segments]
    current = None
    frame_index = 0
    started = time.monotonic()
    next_change = started
    end_time = started + VIDEO_SECONDS
    segment_index = 0

    while frame_index < FPS * VIDEO_SECONDS:
        now = time.monotonic()
        if now >= next_change and segment_index < len(states):
            status, caption, length = states[segment_index]
            current = status
            overlay.set_status(status)
            overlay.set_caption(caption)
            segment_index += 1
            next_change = now + length
        app.processEvents()
        pixmap = overlay.grab()
        frame = base.copy()
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        path = FRAME_DIR / f"frame-{frame_index:04d}.png"
        if not frame.save(str(path)):
            raise RuntimeError(f"Could not save {path}")
        frame_index += 1
        deadline = started + frame_index / FPS
        time.sleep(max(0, deadline - time.monotonic()))
        if time.monotonic() > end_time and current is not None:
            break

    overlay.close()
    app.processEvents()
    output = WORK / "overlay-morph.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(FRAME_DIR / "frame-%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
    )


def main() -> None:
    app = QApplication.instance() or QApplication([])
    base = _backdrop()
    _create_previews(app, base)
    _create_video(app, base)
    print("Created docs/overlay-{listening,thinking,speaking}.png")
    print(f"Created {WORK / 'overlay-morph.mp4'}")


if __name__ == "__main__":
    main()
