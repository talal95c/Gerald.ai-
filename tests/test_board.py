import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from gerald.board import BoardWindow, group_strokes
from gerald.tools.diagram import DiagramCommand, layout_diagram


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


def test_board_diagram_honors_position_and_remains_in_gerald_ink():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    layout = layout_diagram(
        title="Cycle de l'eau",
        layout="tree",
        nodes=[{"id": "a", "text": "Évaporation"}, {"id": "b", "text": "Condensation"}],
        edges=[{"from": "a", "to": "b"}],
    )
    command = DiagramCommand(layout, x=50, y=60)

    board.add_commands([command])
    assert board._gerald[0]["kind"] == "diagram"
    assert (board._gerald[0]["x"], board._gerald[0]["y"]) == (50, 60)
    assert board._reveal_timer.isActive()
    board.show()
    app.processEvents()
    capture, _rects = board.capture()
    assert capture.image.size == (800, 600)
    assert board._gerald[0]["layout"] is layout
    board.close()
    app.processEvents()


def test_board_diagram_never_scales_below_point_eighty_five():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(260, 180)
    layout = layout_diagram(
        title="Grand diagram",
        layout="flow",
        nodes=[
            {"id": str(index), "text": "A very wide label"}
            for index in range(8)
        ],
    )

    board.add_commands([DiagramCommand(layout)])

    assert board._gerald[0]["scale"] == 0.85
    assert board._gerald[0]["x"] >= 0
    assert board._gerald[0]["y"] >= 0
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
        "Stylo",
        "Gomme",
        "Annuler",
        "Effacer",
        "Fermer",
    ]
    board.close()
    app.processEvents()


def test_exercise_card_is_visible_and_unchanged_by_board_actions():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(900, 700)
    board.set_exercise("Exercice 1", ["Résous dans ℝ : x² − 5x + 6 = 0"])
    board.show()
    app.processEvents()

    image = board.grab().toImage()
    assert image.pixelColor(470, 70) == QColor("#EEEEEE")
    capture, rects = board.capture()
    assert capture.image.getpixel((470, 70)) == (238, 238, 238)
    text_pixels = capture.image.crop((472, 62, 870, 120)).convert("RGB")
    assert any(
        text_pixels.getpixel((x, y)) != (238, 238, 238)
        for y in range(text_pixels.height)
        for x in range(text_pixels.width)
    )
    assert rects == []
    assert board._exercise_title == "Exercice 1"
    assert board._exercise_lines == ["Résous dans ℝ : x² − 5x + 6 = 0"]

    board.user_strokes = [[(1, 2, 1.0)], [(3, 4, 1.0)]]
    board.undo()
    assert len(board.user_strokes) == 1
    board.clear_user_ink()
    board.clear_gerald()
    assert board._exercise_title == "Exercice 1"
    assert board._exercise_lines == ["Résous dans ℝ : x² − 5x + 6 = 0"]

    board.close()
    app.processEvents()


def test_ctrl_z_event_undoes_exactly_one_stroke():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    first = [(1, 2, 1.0), (3, 4, 1.0)]
    second = [(5, 6, 1.0), (7, 8, 1.0)]
    board.user_strokes = [first, second]

    QTest.keyClick(board, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)

    assert board.user_strokes == [first]
    board.close()
    app.processEvents()


def test_open_on_screen_raises_activates_and_focuses_board(monkeypatch):
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    screen = SimpleNamespace(geometry=lambda: QRect(0, 0, 320, 240))
    calls = []
    for method in ("show", "raise_", "activateWindow", "setFocus"):
        monkeypatch.setattr(board, method, lambda name=method: calls.append(name))

    board.open_on_screen(screen, dark=False)

    assert calls == ["show", "raise_", "activateWindow", "setFocus"]
    board.close()
    app.processEvents()


def test_tablet_eraser_press_uses_eraser_path_without_creating_stroke(monkeypatch):
    from PyQt6.QtCore import QPointF

    class EventType:
        TabletPress = 1

    class Event:
        Type = EventType

        def __init__(self):
            self.accepted = False

        def type(self):
            return self.Type.TabletPress

        def position(self):
            return QPointF(30, 40)

        def pressure(self):
            return 0.7

        def accept(self):
            self.accepted = True

    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.set_tool("eraser")
    board.user_strokes = [[(1, 2, 1.0), (3, 4, 1.0)]]
    calls = []
    monkeypatch.setattr(board, "_append_point", lambda point, pressure: calls.append((point, pressure)))
    event = Event()

    board.tabletEvent(event)

    assert calls == [(QPointF(30, 40), 0.7)]
    assert board._current is None
    assert len(board.user_strokes) == 1
    assert event.accepted
    board.close()
    app.processEvents()


def test_board_capture_uses_native_rect_for_mixed_dpi_secondary(monkeypatch):
    from types import SimpleNamespace

    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPixmap
    from gerald.overlay import window as overlay_window
    from gerald.capture.screen import MonitorRect

    app = QApplication.instance() or QApplication([])
    logical_screens = [
        ("DISPLAY1", (0, 0, 1920, 1080), 2.0),
        ("DISPLAY2", (1920, 0, 1920, 1080), 1.0),
    ]
    native_monitors = [
        ("DISPLAY1", (0, 0, 3840, 2160)),
        ("DISPLAY2", (3840, 0, 1920, 1080)),
    ]
    mappings = overlay_window._build_screen_mappings(logical_screens, native_monitors)
    monkeypatch.setattr(overlay_window, "_screen_mappings", lambda: mappings)
    screen = SimpleNamespace(geometry=lambda: QRect(1920, 0, 1920, 1080))

    board = BoardWindow()
    board.screen = lambda: screen
    pixmap = QPixmap(1920, 1080)
    pixmap.fill(Qt.GlobalColor.white)
    board.grab = lambda: pixmap

    capture, _rects = board.capture()

    assert capture.monitor == MonitorRect(3840, 0, 1920, 1080)
    board.close()
    app.processEvents()
