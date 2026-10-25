import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from gerald.board import BoardWindow, group_strokes


def test_nearby_strokes_are_grouped():
    strokes = [
        [(10, 10, 1.0), (20, 14, 1.0)],
        [(38, 12, 1.0), (44, 14, 1.0)],
        [(100, 10, 1.0), (110, 14, 1.0)],
    ]

    assert group_strokes(strokes) == [(10, 10, 44, 14), (100, 10, 110, 14)]


def test_board_capture_preserves_one_to_one_image_mapping():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.setGeometry(0, 0, 200, 120)
    board.show()
    app.processEvents()

    capture, rects = board.capture()

    assert capture.scale == 1
    assert capture.image.size == (200, 120)
    assert capture.screen_to_img(25, 30) == (25, 30)
    assert rects == []
    board.close()
    app.processEvents()


def test_board_write_math_and_path_commands():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()

    assert json.loads(board.execute_tool("write", {"text": "x = 4", "x": 20, "y": 40}))["ok"]
    assert json.loads(board.execute_tool("write_math", {"latex": r"x^2 + 1", "x": 20, "y": 80}))["ok"]
    assert json.loads(
        board.execute_tool("draw_path", {"points": [[20, 100], [50, 120], [80, 100]]})
    )["ok"]
    assert [item["kind"] for item in board._gerald] == ["text", "image", "path"]
    assert board._reveal_timer.isActive()
    board.close()
    app.processEvents()


def test_clear_gerald_preserves_user_ink():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.user_strokes = [[(1, 2, 1.0), (3, 4, 1.0)]]
    board.add_write("hello", 10, 20)

    result = json.loads(board.execute_tool("clear_gerald", {}))

    assert result["ok"]
    assert board._gerald == []
    assert len(board.user_strokes) == 1
    board.close()
    app.processEvents()


def test_escape_closes_board():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.show()
    app.processEvents()

    QTest.keyClick(board, Qt.Key.Key_Escape)
    app.processEvents()

    assert not board.isVisible()
    board.close()


def test_toolbar_is_visible_and_centered_at_top():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(640, 480)
    board.show()
    app.processEvents()

    toolbar = board._toolbar
    assert toolbar.isVisible()
    assert toolbar.y() == 20
    assert toolbar.x() == (board.width() - toolbar.width()) // 2
    assert [button.text() for button in toolbar.findChildren(QPushButton)] == [
        "Pen",
        "Eraser",
        "Undo",
        "Clear",
        "Close",
    ]
    board.close()
    app.processEvents()
