from __future__ import annotations

from io import BytesIO
import math
import time

from PIL import Image
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from gerald.capture.screen import Capture, MonitorRect, capture_from_image
from gerald.overlay.window import _system_font_family, screen_mapping_for_qscreen
from gerald.tools.diagram import DiagramCommand
from gerald.tools.diagram_render import draw_diagram
from gerald.tools.plot import build_plot
from gerald.tools.plot_render import draw_plot
from gerald.tools.registry import (
    ArrowCommand,
    CircleCommand,
    ClearCommand,
    HighlightCommand,
    LinkCommand,
    NoteCommand,
    PointCommand,
    UnderlineCommand,
)

PAPER = QColor("#F7F6F3")
BOARD_MARK = QColor("#E8C547")


def group_strokes(strokes: list[list[tuple[float, float, float]]], distance: float = 24) -> list[tuple[float, float, float, float]]:
    boxes = []
    for stroke in strokes:
        if not stroke:
            continue
        xs = [point[0] for point in stroke]
        ys = [point[1] for point in stroke]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    groups: list[list[tuple[float, float, float, float]]] = []
    for box in boxes:
        matching = [
            group
            for group in groups
            if any(
                max(0, max(existing[0] - box[2], box[0] - existing[2]))
                ** 2
                + max(0, max(existing[1] - box[3], box[1] - existing[3]))
                ** 2
                <= distance**2
                for existing in group
            )
        ]
        if not matching:
            groups.append([box])
        else:
            merged = [box]
            for group in matching:
                merged.extend(group)
                groups.remove(group)
            groups.append(merged)
    return [
        (
            min(box[0] for box in group),
            min(box[1] for box in group),
            max(box[2] for box in group),
            max(box[3] for box in group),
        )
        for group in groups
    ]


class BoardWindow(QWidget):
    def __init__(self) -> None:
        from gerald.home.typography import ensure_fonts

        ensure_fonts()
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._dark = False
        self._tool = "pen"
        self.user_strokes: list[list[tuple[float, float, float]]] = []
        self._current: list[tuple[float, float, float]] | None = None
        self._gerald: list[dict] = []
        self._exercise_title = ""
        self._exercise_lines: list[str] = []
        self._capture: Capture | None = None
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setInterval(16)
        self._reveal_timer.timeout.connect(self._advance_reveals)
        self._toolbar = QFrame(self)
        self._toolbar.setStyleSheet(
            "QFrame { background: #161616; border-radius: 18px; }"
            "QPushButton { color: #F7F6F3; background: transparent; border: 0; "
            "padding: 7px 10px; font: 11px 'Google Sans Flex'; }"
            "QPushButton:hover { background: rgba(255,255,255,0.16); border-radius: 12px; }"
        )
        toolbar = QHBoxLayout(self._toolbar)
        toolbar.setContentsMargins(6, 4, 6, 4)
        toolbar.setSpacing(2)
        for name, callback in (
            ("Stylo", lambda: self.set_tool("pen")),
            ("Gomme", lambda: self.set_tool("eraser")),
            ("Annuler", self.undo),
            ("Effacer", self.clear_user_ink),
            ("Fermer", self.close),
        ):
            button = QPushButton(name, self._toolbar)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        self._position_toolbar()

    def set_exercise(self, title: str, lines: list[str]) -> None:
        self._exercise_title = title
        self._exercise_lines = list(lines)
        self.update()

    def open_on_screen(self, screen, dark: bool | None = None) -> None:
        if dark is None:
            from PyQt6.QtGui import QPalette
            from PyQt6.QtWidgets import QApplication

            dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        self._dark = dark
        self.setGeometry(screen.geometry())
        self._position_toolbar()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_toolbar()

    def _position_toolbar(self) -> None:
        if not hasattr(self, "_toolbar"):
            return
        self._toolbar.adjustSize()
        x = max(0, (self.width() - self._toolbar.width()) // 2)
        y = min(20, max(0, self.height() - self._toolbar.height()))
        self._toolbar.move(x, y)
        self._toolbar.show()

    def set_tool(self, tool: str) -> None:
        self._tool = tool

    def undo(self) -> None:
        if self.user_strokes:
            self.user_strokes.pop()
            self.update()

    def clear_user_ink(self) -> None:
        self.user_strokes.clear()
        self.update()

    def clear_gerald(self) -> None:
        self._gerald.clear()
        self.update()

    def add_commands(self, commands: list[object]) -> None:
        for command in commands:
            if isinstance(command, ClearCommand):
                self.clear_gerald()
            elif isinstance(command, DiagramCommand):
                scale = max(0.85, min(1.0, (self.width() - 48) / max(1, command.layout.width), (self.height() - 100) / max(1, command.layout.height)))
                if command.x is not None and command.y is not None:
                    x, y = self._image_to_local(command.x, command.y)
                else:
                    bottom = max(
                        [point[1] for stroke in self.user_strokes for point in stroke]
                        + [item.get("y", 0) + item.get("layout", command.layout).height * item.get("scale", 1)
                           for item in self._gerald if item.get("kind") == "diagram"]
                        + [item.get("y", 0) for item in self._gerald]
                        + [32]
                    )
                    x, y = 32.0, bottom + 24.0
                    if y + command.layout.height * scale > self.height() - 24:
                        x, y = max(24.0, self.width() - command.layout.width * scale - 24), 48.0
                panel_width = command.layout.width * scale
                panel_height = command.layout.height * scale
                x = min(max(0.0, self.width() - panel_width), max(0.0, x))
                y = min(max(0.0, self.height() - panel_height), max(0.0, y))
                self._gerald.append({
                    "kind": "diagram",
                    "layout": command.layout,
                    "x": x,
                    "y": y,
                    "scale": scale,
                    "created": time.monotonic(),
                })
                self._reveal_timer.start()
            else:
                self._gerald.append({"kind": "command", "command": command, "progress": 1.0})
        self.update()

    def add_write(self, text: str, x: float, y: float, size: float = 32) -> None:
        x, y = self._image_to_local(x, y)
        self._gerald.append(
            {
                "kind": "text",
                "text": text,
                "x": x,
                "y": y,
                "size": self._image_size_to_logical(size),
                "progress": 0.0,
            }
        )
        self._reveal_timer.start()
        self.update()

    def add_path(self, points: list[tuple[float, float]], closed: bool = False) -> None:
        points = [self._image_to_local(x, y) for x, y in points]
        self._gerald.append({"kind": "path", "points": points, "closed": closed, "progress": 0.0})
        self._reveal_timer.start()
        self.update()

    def add_math(self, latex: str, x: float, y: float, size: float = 32) -> None:
        from matplotlib.mathtext import math_to_image

        output = BytesIO()
        math_to_image(f"${latex}$", output, dpi=160, format="png", color=BOARD_MARK.name())
        image = QImage.fromData(output.getvalue(), "PNG")
        x, y = self._image_to_local(x, y)
        image = QPixmap.fromImage(image).scaledToHeight(
            max(1, round(self._image_size_to_logical(size))),
            Qt.TransformationMode.SmoothTransformation,
        )
        self._gerald.append({"kind": "image", "image": image, "x": x, "y": y, "size": size, "progress": 0.0})
        self._reveal_timer.start()
        self.update()

    def _image_to_local(self, x: float, y: float) -> tuple[float, float]:
        if self._capture is None:
            return x, y
        screen_x, screen_y = self._capture.img_to_screen(x, y)
        return self._screen_to_local(screen_x, screen_y)

    def _screen_to_local(self, screen_x: float, screen_y: float) -> tuple[float, float]:
        if self._capture is None:
            return screen_x, screen_y
        ratio = self.screen().devicePixelRatio() if self.screen() else 1.0
        return (
            (screen_x - self._capture.monitor.left) / ratio,
            (screen_y - self._capture.monitor.top) / ratio,
        )

    def _image_size_to_logical(self, size: float) -> float:
        ratio = self.screen().devicePixelRatio() if self.screen() else 1.0
        scale = self._capture.scale if self._capture is not None else 1.0
        return size / max(0.01, scale * ratio)

    def execute_tool(self, name: str, args: dict) -> str:
        import json

        try:
            if name in {"write", "write_math"}:
                text = args.get("text") if name == "write" else args.get("latex")
                if not isinstance(text, str) or not text:
                    raise ValueError("text/latex must be a non-empty string")
                x, y = args.get("x"), args.get("y")
                if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    raise ValueError("x and y must be numbers")
                size = args.get("size", 32)
                if not isinstance(size, (int, float)) or size <= 0:
                    raise ValueError("size must be a positive number")
                if name == "write":
                    self.add_write(text, x, y, size)
                else:
                    self.add_math(text, x, y, size)
            elif name == "plot":
                image_size = (
                    self._capture.image.size
                    if self._capture is not None
                    else (self.width(), self.height())
                )
                image_scale_x = image_size[0] / max(1, self.width())
                image_scale_y = image_size[1] / max(1, self.height())
                occupied = []
                for stroke in self.user_strokes:
                    if stroke:
                        xs = [point[0] * image_scale_x for point in stroke]
                        ys = [point[1] * image_scale_y for point in stroke]
                        occupied.append(
                            (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
                        )
                for item in self._gerald:
                    kind = item["kind"]
                    if kind == "diagram":
                        occupied.append(
                            (
                                item["x"] * image_scale_x,
                                item["y"] * image_scale_y,
                                item["layout"].width * item["scale"] * image_scale_x,
                                item["layout"].height * item["scale"] * image_scale_y,
                            )
                        )
                    elif kind == "plot":
                        occupied.append(item["plot"].box)
                    elif kind == "path" and item["points"]:
                        xs = [point[0] * image_scale_x for point in item["points"]]
                        ys = [point[1] * image_scale_y for point in item["points"]]
                        occupied.append(
                            (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
                        )
                    elif kind == "text":
                        occupied.append(
                            (
                                item["x"] * image_scale_x,
                                (item["y"] - item["size"]) * image_scale_y,
                                len(item["text"]) * item["size"] * 0.65 * image_scale_x,
                                item["size"] * image_scale_y,
                            )
                        )
                    elif kind == "image":
                        occupied.append(
                            (
                                item["x"] * image_scale_x,
                                (item["y"] - item["image"].height()) * image_scale_y,
                                item["image"].width() * image_scale_x,
                                item["image"].height() * image_scale_y,
                            )
                        )
                plot, result = build_plot(args, image_size, occupied)
                self._gerald.append(
                    {"kind": "plot", "plot": plot, "created": time.monotonic()}
                )
                self._reveal_timer.start()
                self.update()
                return json.dumps(result, ensure_ascii=False)
            elif name == "draw_path":
                points = args.get("points")
                if (
                    not isinstance(points, list)
                    or len(points) < 2
                    or any(not isinstance(point, list) or len(point) != 2 for point in points)
                ):
                    raise ValueError("points must contain at least two [x, y] pairs")
                self.add_path([(float(x), float(y)) for x, y in points], bool(args.get("closed", False)))
            elif name == "clear_gerald":
                self.clear_gerald()
            else:
                raise ValueError(f"unknown board tool: {name}")
        except Exception as error:
            return json.dumps({"ok": False, "error": str(error)})
        return json.dumps({"ok": True, "action": name})

    def _advance_reveals(self) -> None:
        active = False
        for item in self._gerald:
            if item.get("kind") == "diagram":
                if time.monotonic() - item["created"] < len(item["layout"].nodes) * 0.09 + 0.2:
                    active = True
                continue
            if item.get("kind") == "plot":
                if time.monotonic() - item["created"] < 0.6:
                    active = True
                continue
            if item.get("progress", 1) < 1:
                item["progress"] = min(1.0, item["progress"] + 0.04)
                active = True
        if not active:
            self._reveal_timer.stop()
        self.update()

    def capture(self) -> tuple[Capture, list[tuple[int, int, int, int]]]:
        image = self.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
        width, height = image.width(), image.height()
        raw = image.bits().asstring(image.sizeInBytes())
        pil = Image.frombytes("RGB", (width, height), raw, "raw", "RGB", image.bytesPerLine())
        screen = self.screen()
        mapping = screen_mapping_for_qscreen(screen) if screen else None
        if mapping is not None:
            monitor = MonitorRect(*mapping.physical)
            ratio = mapping.ratio
        else:
            ratio = screen.devicePixelRatio() if screen else 1.0
            geometry = screen.geometry() if screen else self.geometry()
            monitor = MonitorRect(
                round(geometry.x() * ratio),
                round(geometry.y() * ratio),
                width,
                height,
            )
        capture = capture_from_image(pil, monitor, max_width=width)
        groups = group_strokes(self.user_strokes, 24 / ratio)
        rects = [
            (
                monitor.left + round(left * ratio),
                monitor.top + round(top * ratio),
                max(1, round((right - left) * ratio)),
                max(1, round((bottom - top) * ratio)),
            )
            for left, top, right, bottom in groups
        ]
        self._capture = capture
        return capture, rects

    def _append_point(self, point: QPointF, pressure: float = 1.0) -> None:
        if self._tool == "eraser":
            radius = 18
            self.user_strokes = [
                stroke
                for stroke in self.user_strokes
                if not any(math.hypot(x - point.x(), y - point.y()) <= radius for x, y, _p in stroke)
            ]
            self.update()
        elif self._current is not None:
            self._current.append((point.x(), point.y(), max(0.15, pressure)))
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool == "eraser":
                self._append_point(event.position())
                event.accept()
                return
            self._current = [(event.position().x(), event.position().y(), 1.0)]
            self.user_strokes.append(self._current)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._append_point(event.position())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._current = None
        event.accept()

    def tabletEvent(self, event) -> None:
        if event.type() == event.Type.TabletPress:
            if self._tool == "eraser":
                self._append_point(event.position(), event.pressure())
            else:
                self._current = [(event.position().x(), event.position().y(), max(0.15, event.pressure()))]
                self.user_strokes.append(self._current)
        elif event.type() == event.Type.TabletMove:
            self._append_point(event.position(), event.pressure())
        elif event.type() == event.Type.TabletRelease:
            self._current = None
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        paper = QColor("#1C1C1E") if self._dark else PAPER
        ink = QColor("#F5F5F7") if self._dark else QColor("#262626")
        painter.fillRect(self.rect(), paper)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for stroke in self.user_strokes:
            for first, second in zip(stroke, stroke[1:]):
                pen = QPen(ink, 2.5 * (first[2] + second[2]) / 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(QPointF(first[0], first[1]), QPointF(second[0], second[1]))
        painter.setPen(QPen(BOARD_MARK, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for item in self._gerald:
            painter.save()
            if item["kind"] == "text":
                font = QFont("Google Sans Flex", max(8, int(item["size"])))
                painter.setFont(font)
                text = item["text"]
                painter.setClipRect(
                    QRectF(
                        item["x"],
                        0,
                        max(0, len(text) * item["size"] * item["progress"]),
                        self.height(),
                    )
                )
                painter.drawText(QPointF(item["x"], item["y"] + QFontMetricsF(font).ascent()), text)
            elif item["kind"] == "path":
                points = item["points"]
                if len(points) > 1:
                    path = QPainterPath(QPointF(*points[0]))
                    visible = max(2, math.ceil(len(points) * item["progress"]))
                    for point in points[1:visible]:
                        path.lineTo(*point)
                    if item["closed"] and item["progress"] >= 1:
                        path.closeSubpath()
                    painter.drawPath(path)
            elif item["kind"] == "image":
                image = item["image"]
                painter.setClipRect(
                    QRectF(
                        item["x"],
                        item["y"] - image.height(),
                        image.width() * item["progress"],
                        image.height(),
                    )
                )
                painter.drawPixmap(round(item["x"]), round(item["y"] - image.height()), image)
            elif item["kind"] == "diagram":
                draw_diagram(
                    painter,
                    item["layout"],
                    item["x"],
                    item["y"],
                    item["scale"],
                    time.monotonic() - item["created"],
                    _system_font_family(),
                )
            elif item["kind"] == "plot":
                plot = item["plot"]
                x, y = self._image_to_local(plot.box[0], plot.box[1])
                scale = self._image_size_to_logical(1)
                painter.save()
                painter.translate(x, y)
                painter.scale(scale, scale)
                draw_plot(
                    painter,
                    plot,
                    min(1.0, (time.monotonic() - item["created"]) / 0.6),
                    _system_font_family(),
                    ACCENT,
                )
                painter.restore()
            elif item["kind"] == "command":
                command = item["command"]
                painter.setPen(QPen(BOARD_MARK, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if isinstance(command, (CircleCommand, HighlightCommand, UnderlineCommand, NoteCommand)):
                    rect = command.rect
                    top_left = self._screen_to_local(rect.x, rect.y)
                    bottom_right = self._screen_to_local(rect.x + rect.w, rect.y + rect.h)
                    area = (top_left[0], top_left[1], bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])
                    if isinstance(command, CircleCommand):
                        painter.drawEllipse(QRectF(*area))
                    elif isinstance(command, HighlightCommand):
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(BOARD_MARK.red(), BOARD_MARK.green(), BOARD_MARK.blue(), 46))
                        painter.drawRoundedRect(QRectF(*area), 8, 8)
                    elif isinstance(command, UnderlineCommand):
                        painter.drawLine(QPointF(area[0], area[1] + area[3]), QPointF(area[0] + area[2], area[1] + area[3]))
                    else:
                        painter.setFont(QFont("Google Sans Flex", 13))
                        painter.drawText(QPointF(area[0], area[1]), command.text)
                elif isinstance(command, (ArrowCommand, LinkCommand)):
                    start = self._screen_to_local(*command.start)
                    end = self._screen_to_local(*command.end)
                    painter.drawLine(QPointF(*start), QPointF(*end))
                    if isinstance(command, ArrowCommand):
                        angle = math.atan2(end[1] - start[1], end[0] - start[0])
                        for delta in (-0.45, 0.45):
                            painter.drawLine(
                                QPointF(*end),
                                QPointF(end[0] - 12 * math.cos(angle + delta), end[1] - 12 * math.sin(angle + delta)),
                            )
                elif isinstance(command, PointCommand):
                    center = self._screen_to_local(*command.rect.center)
                    painter.setBrush(BOARD_MARK)
                    painter.drawEllipse(QPointF(*center), 5, 5)
            painter.restore()
        if self._exercise_title:
            self._paint_exercise(painter)
        painter.end()

    def _paint_exercise(self, painter: QPainter) -> None:
        width = min(420, max(280, self.width() - 32))
        label = "EXERCICE"
        title = self._exercise_title.strip()
        if title.lower().startswith("exercice"):
            label, separator, title = title.partition("—")
            label = label.strip().upper()
            title = title.strip() if separator else ""
        elif title:
            label = "ÉNONCÉ"
        text = "\n".join(part for part in [title, *self._exercise_lines] if part)
        font = QFont("Abel", 22)
        metrics = QFontMetricsF(font)
        text_rect = metrics.boundingRect(
            QRectF(0, 0, width - 40, self.height()),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        height = max(96, 58 + int(text_rect.height()))
        height = min(height, max(72, self.height() - 48))
        rect = QRectF(self.width() - width - 24, 24, width, height)
        painter.save()
        painter.setPen(QPen(QColor("#E1DFDB"), 1))
        painter.setBrush(QColor("#EEEEEE"))
        painter.drawRoundedRect(rect, 16, 16)
        badge = QRectF(rect.left() + 16, rect.top() + 15, 14, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#262626"))
        painter.drawRoundedRect(badge, 4, 4)
        painter.setPen(QPen(QColor("#F7F6F3"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(badge.left() + 4, badge.top() + 5), QPointF(badge.right() - 4, badge.top() + 5))
        painter.drawLine(QPointF(badge.left() + 4, badge.top() + 9), QPointF(badge.right() - 4, badge.top() + 9))
        painter.setFont(QFont("Abel", 11))
        painter.setPen(QColor("#6D6D6D"))
        painter.drawText(
            QRectF(rect.left() + 38, rect.top() + 12, rect.width() - 54, 20),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            label,
        )
        painter.setFont(font)
        painter.setPen(QColor("#262626"))
        painter.drawText(
            QRectF(rect.left() + 16, rect.top() + 38, rect.width() - 32, rect.height() - 50),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            text,
        )
        painter.restore()
