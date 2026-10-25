from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.board import BoardWindow


OUTPUT = Path("/home/ubuntu/previews/plot-board.png")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(1200, 800)
    args = {
        "functions": [{"expr": "x**2-5*x+6", "label": "f(x) = x² − 5x + 6"}],
        "x_min": -1,
        "x_max": 6,
        "x": 110,
        "y": 84,
        "w": 980,
        "h": 650,
        "points": [
            {"x": 2, "y": 0, "label": "Racine 2"},
            {"x": 3, "y": 0, "label": "Racine 3"},
            {"x": 2.5, "y": -0.25, "label": "Sommet (2,5 ; −0,25)"},
        ],
    }
    board.execute_tool("plot", args)
    board._gerald[-1]["created"] -= 1
    board.show()
    app.processEvents()
    image = QImage(board.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    board.render(painter)
    painter.end()
    if not image.save(str(OUTPUT)):
        raise RuntimeError(f"Could not save preview to {OUTPUT}")
    board.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
