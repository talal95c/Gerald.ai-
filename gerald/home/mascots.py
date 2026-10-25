from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from gerald.home.style import reduced_motion


@dataclass(frozen=True)
class Mascot:
    id: str
    name: str
    color: str


MASCOTS = (
    Mascot("gerald", "Gerald", "#111111"),
    Mascot("alba", "Alba", "#FF765D"),
    Mascot("milo", "Milo", "#23A998"),
    Mascot("zoe", "Zoé", "#8C70E8"),
    Mascot("noe", "Noé", "#4B78E6"),
)
MASCOTS_BY_ID = {mascot.id: mascot for mascot in MASCOTS}
DEFAULT_MASCOT = "gerald"


def mascot_name(mascot_id: str) -> str:
    return MASCOTS_BY_ID.get(mascot_id, MASCOTS_BY_ID[DEFAULT_MASCOT]).name


def _shape_path(mascot_id: str) -> QPainterPath:
    path = QPainterPath()
    if mascot_id == "alba":
        path.moveTo(18, 42)
        path.cubicTo(9, 31, 13, 16, 24, 12)
        path.cubicTo(33, 9, 39, 20, 43, 29)
        path.cubicTo(49, 26, 54, 26, 60, 29)
        path.cubicTo(65, 19, 72, 9, 81, 13)
        path.cubicTo(92, 18, 94, 33, 84, 44)
        path.cubicTo(93, 61, 80, 83, 62, 88)
        path.cubicTo(42, 94, 19, 82, 15, 64)
        path.cubicTo(13, 55, 14, 48, 18, 42)
        path.closeSubpath()
    elif mascot_id == "milo":
        path.moveTo(50, 15)
        path.cubicTo(70, 15, 82, 32, 80, 54)
        path.cubicTo(78, 76, 66, 89, 49, 89)
        path.cubicTo(31, 89, 20, 75, 20, 55)
        path.cubicTo(20, 34, 31, 16, 50, 15)
        path.closeSubpath()
    elif mascot_id == "zoe":
        path.moveTo(50, 13)
        path.cubicTo(72, 13, 88, 31, 86, 54)
        path.cubicTo(85, 76, 69, 89, 48, 87)
        path.cubicTo(29, 86, 13, 72, 14, 53)
        path.cubicTo(14, 32, 28, 13, 50, 13)
        path.closeSubpath()
    elif mascot_id == "noe":
        path.moveTo(31, 17)
        path.cubicTo(41, 11, 58, 11, 69, 17)
        path.cubicTo(82, 23, 87, 38, 86, 55)
        path.cubicTo(85, 76, 72, 88, 52, 88)
        path.cubicTo(32, 88, 17, 76, 15, 58)
        path.cubicTo(12, 40, 17, 24, 31, 17)
        path.closeSubpath()
    else:
        path.moveTo(50, 13)
        path.cubicTo(69, 10, 84, 24, 87, 42)
        path.cubicTo(90, 62, 79, 80, 61, 86)
        path.cubicTo(42, 94, 20, 82, 14, 65)
        path.cubicTo(6, 45, 18, 22, 37, 16)
        path.cubicTo(42, 14, 46, 13, 50, 13)
        path.closeSubpath()
    return path


def paint_mascot(painter: QPainter, mascot_id: str, rect) -> None:
    mascot = MASCOTS_BY_ID.get(mascot_id, MASCOTS_BY_ID[DEFAULT_MASCOT])
    bounds = rect
    side = min(bounds.width(), bounds.height())
    if side <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(bounds.center())
    painter.scale(side / 100, side / 100)
    painter.translate(-50, -50)

    shape = _shape_path(mascot.id)
    shadow = QPainterPath(shape)
    shadow.translate(0, 3)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(15, 15, 15, 20))
    painter.drawPath(shadow)
    painter.setBrush(QColor(mascot.color))
    painter.drawPath(shape)

    if mascot.id == "gerald":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#F7F7F7"), 2.5))
        painter.drawRoundedRect(27, 40, 19, 15, 5, 5)
        painter.drawRoundedRect(54, 40, 19, 15, 5, 5)
        painter.drawLine(46, 47, 54, 47)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F7F7F7"))
        painter.drawEllipse(35, 45, 4, 4)
        painter.drawEllipse(62, 45, 4, 4)
        painter.setPen(QPen(QColor("#F7F7F7"), 2))
        painter.drawArc(40, 58, 20, 10, 205 * 16, 130 * 16)
    elif mascot.id == "alba":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFF4EF"))
        painter.drawEllipse(34, 47, 5, 6)
        painter.drawEllipse(61, 47, 5, 6)
        painter.setPen(QPen(QColor("#9A4033"), 2))
        painter.drawArc(42, 57, 17, 10, 205 * 16, 130 * 16)
        painter.setPen(QPen(QColor("#FFF4EF"), 2.5))
        painter.drawLine(75, 27, 82, 34)
        painter.drawLine(82, 27, 75, 34)
    elif mascot.id == "milo":
        leaf = QPainterPath()
        leaf.moveTo(49, 20)
        leaf.cubicTo(51, 6, 66, 7, 71, 12)
        leaf.cubicTo(68, 22, 57, 26, 49, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#B6F0D8"))
        painter.drawPath(leaf)
        painter.setPen(QPen(QColor("#F5FFFC"), 2))
        painter.drawLine(37, 49, 37, 54)
        painter.drawLine(63, 49, 63, 54)
        painter.setPen(QPen(QColor("#143D37"), 2))
        painter.drawArc(43, 60, 15, 9, 205 * 16, 130 * 16)
    elif mascot.id == "zoe":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#F7F2FF"))
        painter.drawEllipse(34, 47, 5, 6)
        painter.drawEllipse(61, 47, 5, 6)
        painter.setPen(QPen(QColor("#3F2F73"), 2))
        painter.drawArc(42, 58, 16, 9, 205 * 16, 130 * 16)
    else:
        beret = QPainterPath()
        beret.moveTo(25, 29)
        beret.cubicTo(38, 14, 62, 12, 76, 25)
        beret.cubicTo(66, 30, 43, 34, 25, 29)
        beret.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#233E80"))
        painter.drawPath(beret)
        painter.drawEllipse(68, 22, 9, 6)
        painter.setBrush(QColor("#F4F7FF"))
        painter.drawEllipse(35, 49, 5, 6)
        painter.drawEllipse(61, 49, 5, 6)
        painter.setPen(QPen(QColor("#203968"), 2))
        painter.drawArc(42, 60, 16, 9, 205 * 16, 130 * 16)
    painter.restore()


class MascotWidget(QWidget):
    def __init__(
        self,
        mascot_id: str = DEFAULT_MASCOT,
        size: int = 72,
        parent: QWidget | None = None,
        *,
        animate: bool = False,
        motion_offset: int = 0,
    ):
        super().__init__(parent)
        self._mascot_id = (
            mascot_id if mascot_id in MASCOTS_BY_ID else DEFAULT_MASCOT
        )
        self._lift = 0.0
        self._hover_lift = 0.0
        self._lift_animation = None
        self.setFixedSize(size, size)
        self.setAccessibleName(mascot_name(self._mascot_id))
        if animate and not reduced_motion():
            animation = QPropertyAnimation(self, b"lift", self)
            animation.setDuration(2400)
            animation.setStartValue(0.0)
            animation.setKeyValueAt(0.5, 2.2)
            animation.setEndValue(0.0)
            animation.setLoopCount(-1)
            animation.setEasingCurve(QEasingCurve.Type.InOutSine)
            animation.start()
            animation.setCurrentTime(motion_offset % 2400)
            self._lift_animation = animation

    @property
    def mascot_id(self) -> str:
        return self._mascot_id

    @pyqtProperty(float)
    def lift(self) -> float:
        return self._lift

    @lift.setter
    def lift(self, value: float) -> None:
        self._lift = value
        self.update()

    @pyqtProperty(float)
    def hoverLift(self) -> float:
        return self._hover_lift

    @hoverLift.setter
    def hoverLift(self, value: float) -> None:
        self._hover_lift = value
        self.update()

    def set_mascot(self, mascot_id: str) -> None:
        if mascot_id not in MASCOTS_BY_ID:
            mascot_id = DEFAULT_MASCOT
        self._mascot_id = mascot_id
        self.setAccessibleName(mascot_name(mascot_id))
        self.update()

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        rect.translate(0, -self._lift - self._hover_lift)
        paint_mascot(painter, self._mascot_id, rect)


class MascotTile(QPushButton):
    chosen = pyqtSignal(str)

    def __init__(
        self,
        mascot_id: str = DEFAULT_MASCOT,
        *,
        selected: bool = False,
        tile_width: int = 96,
        mascot_size: int = 68,
        motion_offset: int = 0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._mascot_id = (
            mascot_id if mascot_id in MASCOTS_BY_ID else DEFAULT_MASCOT
        )
        self.setObjectName("mascotTile")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Choisir {mascot_name(self._mascot_id)}")
        self.setFixedSize(tile_width, 116)
        self.setProperty("selected", selected)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 8, 5, 8)
        layout.setSpacing(3)
        self.mascot = MascotWidget(
            self._mascot_id,
            mascot_size,
            animate=True,
            motion_offset=motion_offset,
        )
        layout.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignCenter)
        self.name = QLabel(mascot_name(self._mascot_id))
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name)
        self.setStyleSheet(
            """
            QPushButton#mascotTile {
                color: #0F0F0F;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 22px;
                padding: 0;
            }
            QPushButton#mascotTile:hover {
                background: rgba(255, 255, 255, 0.42);
            }
            QPushButton#mascotTile[selected="true"] {
                background: rgba(255, 255, 255, 0.78);
                border-color: rgba(255, 255, 255, 0.92);
            }
            """
        )
        self.set_selected(selected)
        self.clicked.connect(lambda: self.chosen.emit(self._mascot_id))

    def _animate_hover(self, value: float) -> None:
        if reduced_motion():
            self.mascot.hoverLift = value
            return
        animation = QPropertyAnimation(self.mascot, b"hoverLift", self)
        animation.setDuration(160)
        animation.setStartValue(self.mascot.hoverLift)
        animation.setEndValue(value)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        self._hover_animation = animation

    def enterEvent(self, event: QEvent) -> None:
        self._animate_hover(4.0)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    @property
    def mascot_id(self) -> str:
        return self._mascot_id

    def set_selected(self, selected: bool) -> None:
        self.setChecked(selected)
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
