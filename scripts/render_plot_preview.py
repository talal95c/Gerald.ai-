from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gerald.board import BoardWindow


OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "board-plot.png"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(1200, 800)
    board.set_exercise("Exercice 1", ["Résous x² − 5x + 6 = 0"])
    board.user_strokes = [[(42, 530, 1.0), (72, 498, 0.8), (106, 528, 0.7)]]
    board._capture = SimpleNamespace(
        image=SimpleNamespace(size=(2400, 1600)),
        monitor=SimpleNamespace(left=0, top=0),
        scale=1.0,
        img_to_screen=lambda x, y: (x, y),
    )
    args = {
        "functions": [{"expr": "x**2-5*x+6", "label": "f(x) = x² − 5x + 6"}],
        "x_min": -1,
        "x_max": 6,
        "x": 380,
        "y": 264,
        "w": 1800,
        "h": 1280,
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
    image = board.grab().toImage()
    if not image.save(str(OUTPUT)):
        raise RuntimeError(f"Could not save preview to {OUTPUT}")
    board.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
