import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
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
    assert toolbar.height() == 56
    assert toolbar.y() == 20
    assert toolbar.x() == (board.width() - toolbar.width()) // 2
    buttons = toolbar.findChildren(QPushButton)
    assert all(button.height() >= 44 for button in buttons)
    assert [button.text() for button in buttons] == [
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


def test_tablet_stroke_retains_pen_pressure():
    from PyQt6.QtCore import QPointF

    class Event:
        class Type:
            TabletPress = 1
            TabletMove = 2

        def __init__(self, event_type, position, pressure):
            self._type = event_type
            self._position = position
            self._pressure = pressure

        def type(self):
            return self._type

        def position(self):
            return self._position

        def pressure(self):
            return self._pressure

        def accept(self):
            pass

    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.tabletEvent(Event(Event.Type.TabletPress, QPointF(30, 40), 0.7))
    board.tabletEvent(Event(Event.Type.TabletMove, QPointF(35, 45), 0.4))

    assert board.user_strokes == [[(30.0, 40.0, 0.7), (35.0, 45.0, 0.4)]]
    board.close()
    app.processEvents()


def _add_plot_for_window_test(board):
    args = {
        "functions": [{"expr": "x**2-5*x+6", "label": "f(x)"}],
        "x_min": -1,
        "x_max": 6,
        "x": 100,
        "y": 100,
        "w": 420,
        "h": 300,
    }
    assert json.loads(board.execute_tool("plot", args))["ok"]
    return board._gerald[-1]


def test_plot_window_title_bar_moves_box_without_ink_or_restarting_reveal():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    item = _add_plot_for_window_test(board)
    item["created"] -= 1
    created = item["created"]
    board.show()
    app.processEvents()

    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=QPoint(150, 114))
    QTest.mouseMove(board, QPoint(180, 134))
    app.processEvents()
    assert board.cursor().shape() == Qt.CursorShape.SizeAllCursor
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(180, 134))
    app.processEvents()

    assert item["plot"].box == (130.0, 120.0, 420.0, 300.0)
    assert item["created"] == created
    assert board.user_strokes == []
    board.close()
    app.processEvents()


def test_plot_window_grip_resizes_and_respects_minimum_and_board_bounds():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    item = _add_plot_for_window_test(board)
    board.show()
    app.processEvents()

    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=QPoint(506, 386))
    QTest.mouseMove(board, QPoint(120, 120))
    app.processEvents()
    assert board.cursor().shape() == Qt.CursorShape.SizeFDiagCursor
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(120, 120))
    app.processEvents()

    x, y, width, height = item["plot"].box
    assert width == 260
    assert height == 180
    assert x >= 0 and y >= 0
    assert x + width <= 800
    assert y + height <= 600
    assert board.user_strokes == []
    board.close()
    app.processEvents()


def test_plot_window_close_button_removes_plot():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    _add_plot_for_window_test(board)
    board.show()
    app.processEvents()

    QTest.mouseClick(
        board,
        Qt.MouseButton.LeftButton,
        pos=QPoint(506, 114),
    )
    app.processEvents()

    assert board._gerald == []
    assert board.user_strokes == []
    board.close()
    app.processEvents()


def test_plot_window_chrome_intercepts_mouse_strokes_but_body_accepts_them():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    _add_plot_for_window_test(board)
    board.show()
    app.processEvents()

    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=QPoint(150, 114))
    QTest.mouseMove(board, QPoint(170, 124))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(170, 124))
    app.processEvents()
    assert board.user_strokes == []

    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=QPoint(220, 220))
    QTest.mouseMove(board, QPoint(240, 240))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=QPoint(240, 240))
    app.processEvents()

    assert len(board.user_strokes) == 1
    assert len(board.user_strokes[0]) >= 1
    board.close()
    app.processEvents()


def test_plot_window_tablet_chrome_intercepts_pen_and_body_keeps_pressure():
    class Event:
        class Type:
            TabletPress = 1
            TabletMove = 2
            TabletRelease = 3

        def __init__(self, event_type, x, y, pressure=0.7):
            self._type = event_type
            self._position = QPointF(x, y)
            self._pressure = pressure

        def type(self):
            return self._type

        def position(self):
            return self._position

        def pressure(self):
            return self._pressure

        def accept(self):
            pass

    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    item = _add_plot_for_window_test(board)

    board.tabletEvent(Event(Event.Type.TabletPress, 150, 114))
    board.tabletEvent(Event(Event.Type.TabletMove, 170, 124))
    board.tabletEvent(Event(Event.Type.TabletRelease, 170, 124))

    assert item["plot"].box == (120.0, 110.0, 420.0, 300.0)
    assert board.user_strokes == []

    board.tabletEvent(Event(Event.Type.TabletPress, 220, 220, 0.8))
    board.tabletEvent(Event(Event.Type.TabletMove, 230, 230, 0.4))
    board.tabletEvent(Event(Event.Type.TabletRelease, 230, 230, 0.4))

    assert len(board.user_strokes) == 1
    assert board.user_strokes[0] == [(220.0, 220.0, 0.8), (230.0, 230.0, 0.4)]
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
