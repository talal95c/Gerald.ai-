from __future__ import annotations

from datetime import datetime, timedelta

from PyQt6.QtCore import QEvent, QRect, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gerald.home.icons import icon
from gerald.home.style import (
    ACCENT,
    ACCENT_SOFT,
    GlassPanel,
    HOVER,
    INACTIVE,
    SECONDARY,
    TEXT,
)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg")
FILE_FILTER = (
    "Documents pris en charge (*.pdf *.docx *.txt *.md *.png *.jpg *.jpeg);;"
    "Tous les fichiers (*)"
)
MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def as_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone().replace(tzinfo=None)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported timestamp: {type(value).__name__}")


def relative_date(value, now=None) -> str:
    date = as_datetime(value)
    current = as_datetime(now) if now is not None else datetime.now()
    if date.tzinfo is not None:
        date = date.astimezone().replace(tzinfo=None)
    if current.tzinfo is not None:
        current = current.astimezone().replace(tzinfo=None)
    elapsed = current - date
    if elapsed < timedelta(minutes=1):
        return "à l'instant"
    if elapsed < timedelta(hours=1):
        return f"il y a {max(1, int(elapsed.total_seconds() // 60))} min"
    if elapsed < timedelta(days=1):
        return f"il y a {int(elapsed.total_seconds() // 3600)} h"
    days = (current.date() - date.date()).days
    if days == 1:
        return "hier"
    if days < 7:
        return f"il y a {days} j"
    result = f"{date.day} {MONTHS[date.month - 1]}"
    if date.year != current.year:
        result += f" {date.year}"
    return result


class Chip(QWidget):
    clicked = pyqtSignal()
    removed = pyqtSignal()

    def __init__(
        self,
        text: str,
        *,
        selected: bool = False,
        removable: bool = False,
        selectable: bool = True,
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._text = text
        self._selectable = selectable
        self._selected = selected
        self._removable = removable
        self._compact = compact
        self._height = 28 if compact else 32
        self.setObjectName("chipContainer")
        self.setProperty("selected", selected)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(10 if compact else 14, 0, 6 if removable else (10 if compact else 14), 0)
        row.setSpacing(6)
        self.button = QPushButton(text)
        self.button.setObjectName("chipText")
        self.button.setCursor(
            Qt.CursorShape.PointingHandCursor
            if selectable
            else Qt.CursorShape.ArrowCursor
        )
        self.button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.button.clicked.connect(self._clicked)
        row.addWidget(self.button)
        self.remove_button = None
        if removable:
            self.remove_button = QToolButton()
            self.remove_button.setIcon(icon("close"))
            self.remove_button.setIconSize(QSize(9, 9))
            self.remove_button.setFixedSize(14, 22)
            self.remove_button.setToolTip(f"Retirer {text}")
            self.remove_button.setAccessibleName(f"Retirer {text}")
            self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.remove_button.clicked.connect(self.removed.emit)
            row.addWidget(self.remove_button)
        self.setFixedHeight(self._height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"""
            QWidget#chipContainer {{
                background: {INACTIVE};
                border: 0;
                border-radius: {self._height // 2}px;
            }}
            QWidget#chipContainer:hover {{ background: {HOVER}; }}
            QWidget#chipContainer[selected="true"] {{
                background: {ACCENT};
            }}
            QPushButton#chipText {{
                color: {SECONDARY if compact else TEXT};
                background: transparent;
                border: 0;
                border-radius: 0;
                padding: 0;
                font-size: {12 if compact else 13}px;
                font-weight: 400;
            }}
            QWidget#chipContainer[selected="true"] QPushButton#chipText {{
                color: #FAFAFA;
            }}
            QToolButton {{
                color: {SECONDARY};
                background: transparent;
                border: 0;
                border-radius: 7px;
                padding: 0;
            }}
            QToolButton:hover {{ background: rgba(15, 15, 15, 0.10); }}
            """
        )
        self.button.setFixedHeight(self._height)
        self.button.adjustSize()
        self.adjustSize()

    def _clicked(self) -> None:
        if self._selectable:
            self.set_selected(not self._selected)
        self.clicked.emit()

    def click(self) -> None:
        self.button.click()

    def text(self) -> str:
        return self._text

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self.setProperty("selected", self._selected)
        self.button.setProperty("selected", self._selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)
        self.update()

    def is_selected(self) -> bool:
        return self._selected

    def enterEvent(self, event: QEvent) -> None:
        if self.remove_button is not None:
            self.remove_button.setIcon(icon("close", TEXT))
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if self.remove_button is not None:
            self.remove_button.setIcon(icon("close", SECONDARY))
        super().leaveEvent(event)


class FlowLayout(QLayout):
    def __init__(self, parent=None, *, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() + 1 and line_height:
                x = effective.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + bottom


class OverlayScrollBar(QScrollBar):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setProperty("active", False)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(850)
        self._hide_timer.timeout.connect(lambda: self._set_active(False))
        self.valueChanged.connect(self._reveal)

    def _set_active(self, active: bool) -> None:
        if self.property("active") == active:
            return
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _reveal(self, *_args) -> None:
        self._set_active(True)
        self._hide_timer.start()

    def enterEvent(self, event: QEvent) -> None:
        self._hide_timer.stop()
        self._set_active(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hide_timer.start()
        super().leaveEvent(event)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("primaryButton")
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("secondaryButton")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class TextButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("textButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class ChevronComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.arrow_button = QToolButton(self)
        self.arrow_button.setIcon(icon("chevron-down"))
        self.arrow_button.setIconSize(QSize(12, 12))
        self.arrow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_button.setToolTip("Afficher les matières")
        self.arrow_button.setStyleSheet(
            f"QToolButton {{ background: transparent; color: {SECONDARY}; "
            "border: 0; padding: 0; }"
            f"QToolButton:hover {{ background: {ACCENT_SOFT}; }}"
        )
        self.arrow_button.clicked.connect(self.showPopup)
        self.setMinimumHeight(40)
        self.setStyleSheet(
            "QComboBox { border-radius: 10px; padding: 8px 36px 8px 12px; }"
            "QComboBox::drop-down { width: 32px; border: 0; }"
            "QComboBox::down-arrow { image: none; }"
        )

    def resizeEvent(self, event) -> None:
        self.arrow_button.setGeometry(self.width() - 32, 0, 32, self.height())
        super().resizeEvent(event)


class DropZone(QWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None, *, compact: bool = False):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drag_over = False
        self._compact = compact
        self.setMinimumHeight(92 if compact else 132)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(7)
        layout.setContentsMargins(14, 14, 14, 14)
        self.title = QLabel("Dépose tes fichiers ici")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.subtitle = QLabel("ou clique pour choisir · PDF, Word, texte, images")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setProperty("secondary", True)
        self.subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        if compact:
            self.setMinimumHeight(82)

    def choose_files(self) -> list[str]:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self.window(), "Ajouter des documents", "", FILE_FILTER
        )
        if files:
            self.files_dropped.emit(files)
        return files

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.choose_files()
            event.accept()
            return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self._drag_over = True
            self.update()
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event: QEvent) -> None:
        self._drag_over = False
        self.update()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        self._drag_over = False
        self.update()
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._drag_over:
            fill = QColor(10, 132, 255, 26)
            stroke = QColor(ACCENT)
        else:
            fill = QColor("#FFFFFF")
            stroke = QColor("#C7C7CC")
        painter.setBrush(fill)
        pen = QPen(stroke, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)


class Card(GlassPanel):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, *, clickable: bool = False):
        super().__init__(parent)
        self.setObjectName("homeCard")
        self.setProperty("clickable", clickable)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor
        )
        self._clickable = clickable
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 15, 16, 15)
        self.layout.setSpacing(7)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, QWidget):
                child.installEventFilter(self)
        return super().event(event)

    def eventFilter(self, watched, event) -> bool:
        if (
            self._clickable
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.clicked.emit()
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class Avatar(QFrame):
    def __init__(self, name: str, size: int = 32, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setObjectName("avatar")
        self.setStyleSheet(
            "QFrame#avatar { background: rgba(10,132,255,0.10); border-radius: "
            f"{size // 2}px; }}"
        )
        label = QLabel((name.strip() or "?")[0].upper(), self)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setGeometry(self.rect())
        label.setStyleSheet(f"color: {ACCENT}; font-weight: 600; background: transparent;")


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        self.full_text = ""
        super().__init__(parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        self.full_text = text
        self.setToolTip(text)
        self._update_elision()

    def _update_elision(self) -> None:
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(
                self.full_text,
                Qt.TextElideMode.ElideRight,
                max(0, self.width()),
            )
        )

    def resizeEvent(self, event) -> None:
        self._update_elision()
        super().resizeEvent(event)


def elided_label(text: str, width: int = 0, parent: QWidget | None = None) -> QLabel:
    label = ElidedLabel(text, parent)
    if width:
        label.setMaximumWidth(width)
    return label
