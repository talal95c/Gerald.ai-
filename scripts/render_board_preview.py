from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.board import BoardWindow
from gerald.perception.grounding import ScreenRect
from gerald.tools.registry import ArrowCommand, CircleCommand


def main() -> int:
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(1600, 900)

    def glyph(strokes: list[list[tuple[float, float]]]) -> None:
        board.user_strokes.extend(
            [[(x, y, 1.0) for x, y in stroke] for stroke in strokes]
        )

    x, y = 220, 300
    glyph([[(x, y), (x + 20, y - 14), (x + 42, y - 12), (x + 48, y), (x + 38, y + 12), (x + 4, y + 42), (x + 48, y + 42)]])
    glyph([[(x + 66, y), (x + 104, y + 40)], [(x + 104, y), (x + 66, y + 40)]])
    glyph([[(x + 130, y + 20), (x + 170, y + 20)], [(x + 150, y), (x + 150, y + 40)]])
    glyph([[(x + 194, y), (x + 224, y - 12), (x + 238, y), (x + 222, y + 17), (x + 240, y + 25), (x + 226, y + 42), (x + 194, y + 36)]])
    glyph([[(x + 266, y + 8), (x + 306, y + 8)], [(x + 266, y + 30), (x + 306, y + 30)]])
    glyph([[(x + 328, y - 6), (x + 352, y - 18), (x + 352, y + 42)]])
    glyph([[(x + 386, y - 6), (x + 410, y - 18), (x + 410, y + 42)]])

    board.add_write("2x = 8", 300, 480, 54)
    board.add_write("x = 4", 300, 590, 54)
    board.add_commands(
        [
            CircleCommand(ScreenRect(x + 184, y - 28, 64, 88)),
            ArrowCommand((650, 340), (520, 470)),
        ]
    )
    for _ in range(30):
        board._advance_reveals()
    app.processEvents()

    image = QImage(board.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    board.render(painter)
    painter.end()
    output = Path(__file__).parents[1] / "docs" / "board-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    board.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
