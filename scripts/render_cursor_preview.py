from __future__ import annotations

import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from gerald.board import BoardWindow  # noqa: E402
from gerald.capture.screen import MonitorRect, capture_from_image  # noqa: E402
from gerald.overlay.window import OverlayWindow, _ScreenMapping  # noqa: E402
from gerald.perception.grounding import ScreenRect  # noqa: E402
from gerald.tools.diagram import DiagramCommand, layout_diagram  # noqa: E402
from gerald.tools.registry import CircleCommand  # noqa: E402


SOURCE = ROOT / "evals" / "results" / "20261025-112620-214488" / "hn-login.png"
if not SOURCE.exists():
    SOURCE = Path("/home/ubuntu/repos/Gerald.ai-") / "evals" / "results" / "20261025-112620-214488" / "hn-login.png"
OUTPUT = Path("/home/ubuntu/previews")


def _source_image() -> tuple[Image.Image, QImage]:
    source = Image.open(SOURCE).convert("RGB")
    width, height = source.size
    image = QImage(source.tobytes(), width, height, width * 3, QImage.Format.Format_RGB888).copy()
    return source, image


def _make_overlay(app: QApplication, source: Image.Image) -> OverlayWindow:
    width, height = source.size
    overlay = OverlayWindow(cursor_enabled=True)
    overlay.setGeometry(0, 0, width, height)
    overlay._screen_mappings = lambda: [
        _ScreenMapping((0, 0, width, height), (0, 0, width, height), 1.0)
    ]
    image_capture = capture_from_image(
        source,
        MonitorRect(0, 0, width, height),
        max_width=width,
    )
    overlay.set_capture(image_capture)
    overlay.show()
    app.processEvents()
    return overlay


def _render_overlay(app: QApplication, source_image: QImage, overlay: OverlayWindow, output: Path) -> None:
    app.processEvents()
    if overlay._bubble is not None:
        overlay._bubble._opacity_effect.setOpacity(1.0)
        overlay._bubble._rise.stop()
    image = QImage(source_image.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.drawImage(0, 0, source_image)
    overlay.render(painter)
    if overlay._bubble is not None:
        bubble = overlay._bubble
        painter.save()
        painter.translate(bubble.x(), bubble.y())
        bubble.render(painter)
        painter.restore()
    painter.end()
    if not image.save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    overlay.close()
    app.processEvents()


def _photosynthesis() -> DiagramCommand:
    layout = layout_diagram(
        title="Photosynthèse",
        layout="flow",
        nodes=[
            {"id": "light", "text": "Lumière"},
            {"id": "chlorophyll", "text": "Chlorophylle"},
            {"id": "glucose", "text": "Glucose"},
            {"id": "oxygen", "text": "Oxygène"},
            {"id": "energy", "text": "Énergie"},
        ],
        edges=[
            {"from": "light", "to": "chlorophyll"},
            {"from": "chlorophyll", "to": "glucose"},
            {"from": "chlorophyll", "to": "oxygen", "label": "libère"},
            {"from": "glucose", "to": "energy"},
        ],
    )
    return DiagramCommand(layout)


def _render_floating_diagram(app: QApplication, source: Image.Image, source_image: QImage) -> None:
    overlay = _make_overlay(app, source)
    overlay.set_mouse_position(90, 90, physical=False)
    overlay._cursor_position = QPointF(108, 104)
    overlay.add_commands([_photosynthesis()])
    overlay._diagrams[0]["x"] = 920
    overlay._diagrams[0]["y"] = 520
    overlay._diagrams[0]["created"] -= 2
    _render_overlay(app, source_image, overlay, OUTPUT / "photosynthesis-floating-diagram.png")


def _render_board_tree(app: QApplication, output: Path) -> None:
    board = BoardWindow()
    board.resize(1440, 900)
    layout = layout_diagram(
        title="La cellule végétale",
        layout="tree",
        nodes=[
            {"id": "cell", "text": "Cellule"},
            {"id": "nucleus", "text": "Noyau"},
            {"id": "membrane", "text": "Membrane"},
            {"id": "cytoplasm", "text": "Cytoplasme"},
            {"id": "dna", "text": "ADN"},
        ],
        edges=[
            {"from": "cell", "to": "nucleus"},
            {"from": "cell", "to": "membrane"},
            {"from": "cell", "to": "cytoplasm"},
            {"from": "nucleus", "to": "dna"},
        ],
    )
    board.add_commands([DiagramCommand(layout, x=560, y=140)])
    board._gerald[0]["created"] -= 3
    board.show()
    app.processEvents()
    image = QImage(1440, 900, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    board.render(painter)
    painter.end()
    if not image.save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    board.close()
    app.processEvents()


def render() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Preview source screenshot not found: {SOURCE}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source, source_image = _source_image()
    app = QApplication.instance() or QApplication([])

    overlay = _make_overlay(app, source)
    overlay.set_mouse_position(450, 340, physical=False)
    overlay._cursor_position = QPointF(468, 354)
    _render_overlay(app, source_image, overlay, OUTPUT / "cursor-next-to-mouse.png")

    overlay = _make_overlay(app, source)
    circle = CircleCommand(ScreenRect(140, 710, 380, 24))
    overlay.add_commands([circle])
    target = overlay._cursor_target_for(circle)
    overlay._cursor_position = QPointF(target)
    overlay._cursor_flight = None
    overlay._cursor_hold_until = time.monotonic() + 12
    overlay._marks[0].created -= 1
    overlay.show_bubble("Astuce : Ctrl+F pour chercher dans la page")
    _render_overlay(app, source_image, overlay, OUTPUT / "cursor-target-tip.png")

    overlay = _make_overlay(app, source)
    overlay.set_mouse_position(660, 520, physical=False)
    overlay._cursor_position = QPointF(678, 534)
    overlay.show_bubble("Je t'explique « Hacker News » ?", ["Oui", "Non"], ttl=10)
    _render_overlay(app, source_image, overlay, OUTPUT / "proactive-oui-non.png")

    _render_floating_diagram(app, source, source_image)
    _render_board_tree(app, OUTPUT / "tree-diagram-board.png")


if __name__ == "__main__":
    render()
