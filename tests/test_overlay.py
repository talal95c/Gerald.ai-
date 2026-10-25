import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.overlay.window import OverlayWindow
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import ArrowCommand, CircleCommand, NoteCommand


def test_overlay_renders_circle_and_arrow_with_transparent_surroundings():
    app = QApplication.instance() or QApplication([])
    overlay = OverlayWindow()
    overlay.setGeometry(0, 0, 640, 400)
    overlay.add_commands(
        [
            CircleCommand(ScreenRect(100, 100, 80, 60)),
            ArrowCommand((210, 100), (310, 100)),
            NoteCommand(ScreenRect(400, 150, 40, 20), "micro"),
        ]
    )
    for mark in overlay._marks:
        mark.created -= 1
    overlay.set_status("speaking", output_level=0.7)
    overlay._status_changed -= 1
    overlay.set_caption("Clique sur le micro pour dicter une recherche.")
    image = QImage(640, 400, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    overlay.render(painter)
    painter.end()
    assert image.pixelColor(140, 100).alpha() > 0
    assert image.pixelColor(260, 106).alpha() > 0
    assert image.pixelColor(410, 128).alpha() > 0
    assert image.pixelColor(320, 330).alpha() > 0
    assert image.pixelColor(600, 200).alpha() == 0
    overlay.close()
    app.processEvents()
