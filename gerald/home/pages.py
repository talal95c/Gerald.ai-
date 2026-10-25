from __future__ import annotations

from datetime import datetime
import threading

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFontMetrics, QKeyEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gerald.home.icons import icon
from gerald.home.mascots import MASCOTS, MascotTile, MascotWidget, mascot_name
from gerald.home.style import (
    ACCENT,
    ACCENT_PRESSED,
    GlassPanel,
    HOVER,
    INACTIVE,
    DANGER,
    SECONDARY,
    SIGNAL,
    SEPARATOR,
    SURFACE,
    TEXT,
    apply_tracking,
    fade_in,
)
from gerald.home.widgets import (
    Card,
    Chip,
    DropZone,
    ElidedLabel,
    FILE_FILTER,
    FlowLayout,
    OverlayScrollBar,
    PrimaryButton,
    SecondaryButton,
    TextButton,
    relative_date,
)

LEVELS = ("Collège", "Lycée", "Licence", "Master", "Doctorat", "Autre")
SUGGESTIONS = (
    "Maths",
    "Physique-Chimie",
    "SVT",
    "Histoire-Géo",
    "Français",
    "Anglais",
    "Philosophie",
    "Informatique",
    "Économie",
)
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def centered_scroll(page: QWidget, *, margins=(48, 32, 48, 32)):
    root = QVBoxLayout(page)
    root.setContentsMargins(*margins)
    root.setSpacing(0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBar(OverlayScrollBar(scroll))
    wrapper = QWidget()
    wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    wrapper_layout = QHBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(0, 0, 0, 0)
    content = QWidget()
    content.setMaximumWidth(760)
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 20)
    layout.setSpacing(0)
    wrapper_layout.addWidget(content, 1)
    scroll.setWidget(wrapper)
    root.addWidget(scroll)
    return layout


def secondary_label(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("secondary", True)
    label.setWordWrap(True)
    return label


def _course_name(host, course_id: int | None) -> str:
    if course_id is None:
        return "Tous les cours"
    course = next(
        (item for item in host.store.list_courses() if field(item, "id") == course_id),
        None,
    )
    return field(course, "title", "Cours supprimé") if course is not None else "Cours supprimé"


def _date_line(value: datetime | None = None) -> str:
    date = value or datetime.now()
    return f"{WEEKDAYS[date.weekday()].capitalize()} {date.day} {MONTHS[date.month - 1]}"


def _document_count_label(count: int) -> str:
    if count == 0:
        return "Aucun document"
    if count == 1:
        return "1 document"
    return f"{count} documents"


class HomePage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.recent_rows: list[Card] = []
        self.course_cards: dict[int, Card] = {}
        self._layout = centered_scroll(self, margins=(48, 24, 48, 24))
        self.greeting = QLabel()
        self.greeting.setStyleSheet("font-size: 26px; font-weight: 600;")
        apply_tracking(self.greeting, -0.6)
        self.date_label = secondary_label("")
        self._layout.addWidget(self.greeting)
        self._layout.addSpacing(4)
        self._layout.addWidget(self.date_label)
        self._layout.addSpacing(8)
        self.hotkey_card = QFrame()
        self.hotkey_card.setObjectName("profPanel")
        self.hotkey_card.setStyleSheet(
            "QFrame#profPanel { background: #0F0F0F; border-radius: 24px; }"
        )
        self.hotkey_card.setMinimumHeight(88)
        self.prof_panel_layout = QVBoxLayout(self.hotkey_card)
        self.prof_panel_layout.setContentsMargins(18, 6, 18, 6)
        self.prof_panel_layout.setSpacing(2)
        identity = QHBoxLayout()
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(16)
        self.prof_mascot = MascotWidget(
            self.host.mascot_id,
            56,
            animate=True,
        )
        identity.addWidget(self.prof_mascot)
        prof_copy = QVBoxLayout()
        prof_copy.setContentsMargins(0, 0, 0, 0)
        prof_copy.setSpacing(5)
        prof_eyebrow = QLabel("TON PROF")
        prof_eyebrow.setStyleSheet(
            "color: rgba(250,250,250,0.56); font-size: 10px; font-weight: 600;"
        )
        apply_tracking(prof_eyebrow, 1.1)
        prof_copy.addWidget(prof_eyebrow)
        self.prof_status = QLabel()
        self.prof_status.setStyleSheet(
            "color: #FAFAFA; font-size: 21px; font-weight: 600;"
        )
        prof_copy.addWidget(self.prof_status)
        identity.addLayout(prof_copy, 1)
        self.prof_panel_layout.addLayout(identity)
        self.hotkey_row = QHBoxLayout()
        self.hotkey_row.setContentsMargins(0, 0, 0, 0)
        self.hotkey_row.setSpacing(5)
        self.prof_panel_layout.addLayout(self.hotkey_row)
        self._layout.addWidget(self.hotkey_card)
        self.set_mascot(self.host.mascot_id)
        self._layout.addSpacing(4)
        self.ask_button = QPushButton("Poser une question sur tous mes cours")
        self.ask_button.setObjectName("askEntry")
        self.ask_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ask_button.setMinimumHeight(44)
        self.ask_button.setStyleSheet(
            f"QPushButton#askEntry {{ color: {SECONDARY}; background: rgba(255,255,255,0.78); "
            f"border: 1px solid {SEPARATOR}; border-radius: 12px; text-align: left; "
            "padding: 0 16px; }"
            f"QPushButton#askEntry:hover {{ border-color: rgba(15,15,15,0.20); color: {TEXT}; }}"
            f"QPushButton#askEntry:pressed {{ background: {INACTIVE}; }}"
        )
        self.ask_button.clicked.connect(lambda: self.host.open_chat(course_id=None))
        self._layout.addWidget(self.ask_button)
        self._layout.addSpacing(8)
        self._section_header(self._layout, "Discussions récentes")
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setContentsMargins(0, 4, 0, 0)
        self.recent_layout.setSpacing(4)
        self._layout.addLayout(self.recent_layout)
        self._layout.addSpacing(4)
        course_header = QHBoxLayout()
        self._section_header(course_header, "Mes cours")
        course_header.addStretch(1)
        self._layout.addLayout(course_header)
        self.course_grid = QGridLayout()
        self.course_grid.setContentsMargins(0, 0, 0, 0)
        self.course_grid.setHorizontalSpacing(12)
        self.course_grid.setVerticalSpacing(6)
        self._layout.addLayout(self.course_grid)
        self._layout.addStretch(1)
        self.refresh()

    @staticmethod
    def _section_header(layout, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(label)

    def _refresh_hotkey(self) -> None:
        clear_layout(self.hotkey_row)
        normalized = str(getattr(self.host.settings, "hotkey", "ctrl+shift") or "ctrl+shift")
        parts = [part.strip() for part in normalized.split("+") if part.strip()]
        readable = {
            "ctrl": "Ctrl",
            "control": "Ctrl",
            "shift": "Shift",
            "alt": "Alt",
            "cmd": "Cmd",
            "win": "Win",
            "meta": "Cmd",
        }
        caps = []
        for key in parts:
            label = readable.get(key.casefold(), key.capitalize())
            cap = QLabel(label)
            cap.setObjectName("keycap")
            cap.setStyleSheet(
                "QLabel#keycap { color: #FAFAFA; background: rgba(255,255,255,0.12); "
                "border: 1px solid rgba(255,255,255,0.16); border-radius: 8px; "
                "padding: 3px 7px; font-size: 11px; font-weight: 600; }"
            )
            self.hotkey_row.addWidget(cap)
            caps.append(label)
        sentence = QLabel(
            "Maintiens " + "+".join(caps) + " pour demander à Gerald sur ton écran"
        )
        sentence.setWordWrap(True)
        sentence.setStyleSheet("color: rgba(250,250,250,0.72); font-size: 11px;")
        self.hotkey_row.addSpacing(7)
        self.hotkey_row.addWidget(sentence, 1)

    def set_mascot(self, mascot_id: str) -> None:
        self.prof_mascot.set_mascot(mascot_id)
        self.prof_status.setText(
            f'<span style="color: {SIGNAL}">●</span> {mascot_name(mascot_id)} est prêt'
        )

    def refresh(self) -> None:
        profile = self.host.store.get_profile()
        name = field(profile, "name", "") if profile is not None else ""
        self.greeting.setText(f"Bonjour {name}".strip())
        self.date_label.setText(_date_line())
        self._refresh_hotkey()
        clear_layout(self.recent_layout)
        self.recent_rows = []
        conversations = self.host.store.recent_conversations(limit=5)
        if not conversations:
            self.recent_layout.addWidget(
                secondary_label("Tes discussions apparaîtront ici.")
            )
        else:
            for conversation in conversations:
                card = Card(clickable=True)
                conversation_id = field(conversation, "id")
                course_id = field(conversation, "course_id")
                source = field(conversation, "source", "chat")
                card.setProperty("conversationId", conversation_id)
                card.layout.setContentsMargins(16, 7, 16, 7)
                card.layout.setSpacing(4)
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                text_column = QVBoxLayout()
                text_column.setSpacing(2)
                title = ElidedLabel(field(conversation, "title", "Nouvelle discussion"))
                title.setStyleSheet("font-weight: 500;")
                course = (
                    "Agent"
                    if source == "agent"
                    else _course_name(self.host, course_id)
                )
                meta = secondary_label(
                    f"{course} · {relative_date(field(conversation, 'updated_at'))}"
                )
                meta.setStyleSheet("font-size: 11px;")
                text_column.addWidget(title)
                text_column.addWidget(meta)
                row.addLayout(text_column, 1)
                card.layout.addLayout(row)
                card.clicked.connect(
                    lambda conversation_id=conversation_id,
                    course_id=course_id,
                    source=source: self.host.open_chat(
                        conversation_id=conversation_id,
                        course_id=course_id,
                        read_only=source == "agent",
                    )
                )
                self.recent_layout.addWidget(card)
                self.recent_rows.append(card)
        clear_layout(self.course_grid)
        self.course_cards = {}
        courses = self.host.store.list_courses()
        for index, course in enumerate(courses):
            course_id = field(course, "id")
            title_text = field(course, "title", "")
            card = Card(clickable=True)
            title = ElidedLabel(title_text)
            title.setStyleSheet("font-size: 15px; font-weight: 600;")
            subject_text = field(course, "subject", "")
            eyebrow_row = QHBoxLayout()
            eyebrow_row.setContentsMargins(0, 0, 0, 0)
            eyebrow_row.setSpacing(8)
            badge = QFrame()
            badge.setFixedSize(24, 24)
            badge.setStyleSheet(
                "QFrame { background: #0F0F0F; border-radius: 12px; }"
            )
            badge_layout = QHBoxLayout(badge)
            badge_layout.setContentsMargins(0, 0, 0, 0)
            badge_icon = QLabel()
            badge_icon.setPixmap(icon("book", "#FAFAFA").pixmap(QSize(13, 13)))
            badge_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_layout.addWidget(badge_icon)
            eyebrow = secondary_label((subject_text or "Matière à définir").upper())
            eyebrow.setStyleSheet("font-size: 10px; font-weight: 600;")
            apply_tracking(eyebrow, 0.8)
            eyebrow_row.addWidget(badge)
            eyebrow_row.addWidget(eyebrow, 1)
            count = _document_count_label(
                len(self.host.store.list_documents(course_id))
            )
            count_label = secondary_label(count)
            count_label.setStyleSheet("font-size: 11px;")
            card.layout.addLayout(eyebrow_row)
            card.layout.addSpacing(2)
            card.layout.addWidget(title)
            card.layout.addStretch(1)
            card.layout.addWidget(count_label)
            card.setMinimumHeight(82)
            card.clicked.connect(
                lambda course_id=course_id: self.host.open_course(course_id)
            )
            self.course_grid.addWidget(card, index // 3, index % 3)
            self.course_cards[course_id] = card
        self.new_course_card = Card(clickable=True)
        self.new_course_card.setMinimumHeight(82)
        plus = QLabel()
        plus.setPixmap(icon("plus", "#FAFAFA").pixmap(QSize(18, 18)))
        plus.setFixedSize(28, 28)
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setStyleSheet("background: #0F0F0F; border-radius: 14px;")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel("Nouveau cours")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setProperty("secondary", True)
        self.new_course_card.layout.addStretch(1)
        self.new_course_card.layout.addWidget(plus)
        self.new_course_card.layout.addWidget(label)
        self.new_course_card.layout.addStretch(1)
        self.new_course_card.clicked.connect(self.host.create_course)
        new_index = len(courses)
        self.course_grid.addWidget(self.new_course_card, new_index // 3, new_index % 3)


class DocumentRow(QFrame):
    def __init__(self, page: CoursePage, document):
        super().__init__(page)
        self.page = page
        self.document = document
        self.setObjectName("documentRow")
        self.setStyleSheet(
            "QFrame#documentRow { background: transparent; border: 0; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.document_icon = QLabel()
        self.document_icon.setPixmap(icon("document").pixmap(QSize(16, 16)))
        top.addWidget(self.document_icon)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        filename = field(document, "filename", "")
        self.filename = ElidedLabel(filename)
        self.filename.setStyleSheet("font-weight: 500;")
        self.filename.setToolTip(filename)
        text_column.addWidget(self.filename)
        self.error_message = secondary_label("")
        self.error_message.setStyleSheet("font-size: 11px;")
        self.error_message.setVisible(False)
        text_column.addWidget(self.error_message)
        top.addLayout(text_column, 1)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.status_label)
        self.delete_button = QToolButton()
        self.delete_button.setIcon(icon("trash"))
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setToolTip("Supprimer le document")
        self.delete_button.setAccessibleName("Supprimer le document")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setVisible(False)
        self.delete_button.clicked.connect(
            lambda: self.page.delete_document(field(self.document, "id"))
        )
        top.addWidget(self.delete_button)
        root.addLayout(top)
        self._pulse_on = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(520)
        self._pulse_timer.timeout.connect(self._pulse)
        self.set_document(document)

    def set_document(self, document) -> None:
        self.document = document
        filename = field(document, "filename", "")
        self.filename.setText(filename)
        self.filename.setToolTip(filename)
        self._pulse_timer.stop()
        status = field(document, "status", "")
        if status == "indexing":
            self.status_label.setText("● Indexation…")
            self.status_label.setStyleSheet("color: #9999A3; font-size: 11px;")
            self._pulse_timer.start()
        elif status == "error":
            self.status_label.setText("● Erreur")
            self.status_label.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
            self.error_message.setText(
                field(document, "error") or "Une erreur est survenue."
            )
            self.error_message.setVisible(True)
        else:
            self.status_label.setText(
                f"● Prêt · {field(document, 'n_chunks', 0)} passages"
            )
            self.status_label.setStyleSheet("color: #2BEE19; font-size: 11px;")
            self.error_message.setVisible(False)

    def _pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        color = "#9999A3" if self._pulse_on else "#D0D0D6"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def enterEvent(self, event: QEvent) -> None:
        self.delete_button.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.delete_button.setVisible(False)
        super().leaveEvent(event)


class CoursePage(QWidget):
    def __init__(self, host, course):
        super().__init__(host)
        self.host = host
        self.course = course
        self.document_rows: dict[int, DocumentRow] = {}
        self._layout = centered_scroll(self)
        self.title_input = QLineEdit()
        self.title_input.setObjectName("courseTitle")
        self.title_input.setStyleSheet(
            f"QLineEdit#courseTitle {{ font-size: 26px; font-weight: 600; "
            f"border: 1px solid transparent; border-radius: 10px; "
            "background: transparent; padding: 0; }"
            f"QLineEdit#courseTitle:hover {{ border-color: {SEPARATOR}; }}"
            f"QLineEdit#courseTitle:focus {{ border: 2px solid rgba(10,132,255,0.28); "
            "background: white; }"
        )
        self.title_input.setTextMargins(0, 0, 0, 0)
        self.title_input.editingFinished.connect(self.save_title)
        self._layout.addWidget(self.title_input)
        self.subject_label = secondary_label("")
        self._layout.addSpacing(3)
        self._layout.addWidget(self.subject_label)
        self._layout.addSpacing(24)
        self._section_title(self._layout, "Notes")
        self.notes_input = QPlainTextEdit()
        self.notes_input.setObjectName("courseNotes")
        self.notes_input.setPlaceholderText("Écris tes notes ici…")
        self.notes_input.setMinimumHeight(120)
        self.notes_input.setMaximumHeight(600)
        self.notes_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.notes_input.textChanged.connect(self._schedule_notes_save)
        self._layout.addWidget(self.notes_input)
        self.notes_saved_label = secondary_label("")
        self.notes_saved_label.setStyleSheet("font-size: 11px;")
        self._layout.addWidget(self.notes_saved_label, 0, Qt.AlignmentFlag.AlignRight)
        self.notes_timer = QTimer(self)
        self.notes_timer.setSingleShot(True)
        self.notes_timer.setInterval(600)
        self.notes_timer.timeout.connect(self.save_notes)
        self._layout.addSpacing(24)
        self._section_title(self._layout, "Documents")
        self.drop_zone = DropZone(compact=True)
        self.drop_zone.files_dropped.connect(self.add_files)
        self._layout.addWidget(self.drop_zone)
        self.add_documents_button = SecondaryButton("Ajouter des documents")
        self.add_documents_button.setIcon(icon("plus"))
        self.add_documents_button.setIconSize(QSize(15, 15))
        self.add_documents_button.clicked.connect(self.choose_files)
        self._layout.addSpacing(8)
        self._layout.addWidget(self.add_documents_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.documents_card = GlassPanel(radius=16, surface_alpha=220)
        self.documents_card_layout = QVBoxLayout(self.documents_card)
        self.documents_card_layout.setContentsMargins(0, 0, 0, 0)
        self.documents_card_layout.setSpacing(0)
        self.documents_card.setVisible(False)
        self.documents_layout = self.documents_card_layout
        self._layout.addWidget(self.documents_card)
        self._layout.addSpacing(24)
        self.ask_button = PrimaryButton("Poser une question")
        self.ask_button.clicked.connect(
            lambda: self.host.open_chat(course_id=field(self.course, "id"))
        )
        self._layout.addWidget(self.ask_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._layout.addSpacing(16)
        self.delete_course_button = TextButton("Supprimer le cours")
        self.delete_course_button.setStyleSheet(f"color: {DANGER};")
        self.delete_course_button.clicked.connect(self.confirm_delete)
        self._layout.addWidget(self.delete_course_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._delete_timer = QTimer(self)
        self._delete_timer.setSingleShot(True)
        self._delete_timer.setInterval(4000)
        self._delete_timer.timeout.connect(self._reset_delete_button)
        self.refresh()

    @staticmethod
    def _section_title(layout, text: str) -> None:
        label = QLabel(text)
        label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(label)
        layout.addSpacing(10)

    def refresh(self) -> None:
        course_id = field(self.course, "id")
        course = next(
            (
                item
                for item in self.host.store.list_courses()
                if field(item, "id") == course_id
            ),
            self.course,
        )
        self.course = course
        self.title_input.setText(field(course, "title", ""))
        self.subject_label.setText(field(course, "subject") or "Matière à définir")
        self.notes_input.blockSignals(True)
        self.notes_input.setPlainText(field(course, "notes") or "")
        self.notes_input.blockSignals(False)
        self._resize_notes_to_content()
        self.refresh_documents()

    def save_title(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            self.title_input.setText(field(self.course, "title", ""))
            return
        course_id = field(self.course, "id")
        if title == field(self.course, "title", ""):
            return
        self.host.store.update_course(course_id, title=title)
        self.course = next(
            (
                item
                for item in self.host.store.list_courses()
                if field(item, "id") == course_id
            ),
            self.course,
        )
        self.title_input.setText(field(self.course, "title", ""))
        self.host.sidebar.refresh_courses()
        self.host.home_page.refresh()
        self.host._notify_library_changed()

    def _schedule_notes_save(self) -> None:
        self._resize_notes_to_content()
        self.notes_saved_label.clear()
        self.notes_timer.start()

    def _resize_notes_to_content(self) -> None:
        document_height = self.notes_input.document().documentLayout().documentSize().height()
        height = max(120, min(600, int(document_height + 24)))
        self.notes_input.setFixedHeight(height)

    def save_notes(self) -> None:
        notes = self.notes_input.toPlainText()
        course_id = field(self.course, "id")
        self.host.store.update_course(course_id, notes=notes)
        self.course = next(
            (
                item
                for item in self.host.store.list_courses()
                if field(item, "id") == course_id
            ),
            self.course,
        )
        self.notes_saved_label.setText("Enregistré")
        fade_in(self.notes_saved_label, 180)

    def choose_files(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self, "Ajouter des documents", "", FILE_FILTER
        )
        if paths:
            self.add_files(paths)

    def add_files(self, paths: list[str]) -> None:
        if not paths:
            return
        course_id = field(self.course, "id")
        for path in paths:
            self.host.indexer.add_document(
                course_id,
                path,
                on_done=self.host._document_callback,
            )
        self.refresh_documents()
        self.host.home_page.refresh()
        self.host._notify_library_changed()

    def refresh_documents(self) -> None:
        clear_layout(self.documents_layout)
        self.document_rows = {}
        documents = self.host.store.list_documents(field(self.course, "id"))
        self.documents_card.setVisible(bool(documents))
        for index, document in enumerate(documents):
            if index:
                separator = QFrame()
                separator.setFixedHeight(1)
                separator.setStyleSheet(f"background: {SEPARATOR};")
                self.documents_layout.addWidget(separator)
            row = DocumentRow(self, document)
            self.documents_layout.addWidget(row)
            self.document_rows[field(document, "id")] = row

    def delete_document(self, document_id: int) -> None:
        self.host.store.delete_document(document_id)
        self.refresh_documents()
        self.host.home_page.refresh()
        self.host._notify_library_changed()

    def confirm_delete(self) -> None:
        if self.delete_course_button.text() != "Confirmer la suppression":
            self.delete_course_button.setText("Confirmer la suppression")
            self._delete_timer.start()
            return
        self._delete_timer.stop()
        course_id = field(self.course, "id")
        self.host.store.delete_course(course_id)
        self.host._course_pages.pop(course_id, None)
        self.host._pages_by_key.pop(("course", course_id), None)
        self.host.sidebar.refresh_courses()
        self.host._notify_library_changed()
        self.host.open_home()

    def _reset_delete_button(self) -> None:
        self.delete_course_button.setText("Supprimer le cours")


class DiscussionsPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self._layout = centered_scroll(self)
        self.title = QLabel("Discussions")
        self.title.setStyleSheet("font-size: 26px; font-weight: 600;")
        self._layout.addWidget(self.title)
        self._layout.addSpacing(20)
        self.filters = QWidget()
        filters_layout = QHBoxLayout(self.filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(3)
        self.filter_buttons: dict[str, QPushButton] = {}
        for key, label in (("all", "Toutes"), ("course", "Cours"), ("agent", "Agent")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("discussionFilter")
            button.setFixedHeight(34)
            button.setStyleSheet(
                f"QPushButton#discussionFilter {{ color: {SECONDARY}; border: 0; "
                "border-radius: 17px; padding: 0 13px; }"
                f"QPushButton#discussionFilter:checked {{ color: {TEXT}; background: #E8E8ED; "
                "font-weight: 600; }"
            )
            button.clicked.connect(lambda _checked=False, filter_key=key: self.set_filter(filter_key))
            self.filter_buttons[key] = button
            filters_layout.addWidget(button)
        filters_layout.addStretch(1)
        self._layout.addWidget(self.filters)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 14, 0, 0)
        self.rows_layout.setSpacing(8)
        self._layout.addLayout(self.rows_layout)
        self._layout.addStretch(1)
        self.filter = "all"
        self.rows: list[Card] = []
        self.set_filter("all")

    def set_filter(self, filter_key: str) -> None:
        self.filter = filter_key
        for key, button in self.filter_buttons.items():
            button.setChecked(key == filter_key)
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.rows_layout)
        self.rows = []
        source = {"course": "chat", "agent": "agent"}.get(self.filter)
        conversations = self.host.store.recent_conversations(limit=100, source=source)
        if not conversations:
            messages = {
                "all": "Tes discussions apparaîtront ici.",
                "course": "Aucune discussion de cours pour le moment.",
                "agent": "Aucune conversation avec l'agent pour le moment.",
            }
            self.rows_layout.addWidget(secondary_label(messages[self.filter]))
            return
        for conversation in conversations:
            card = Card(clickable=True)
            card.setMinimumHeight(64)
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            conversation_id = field(conversation, "id")
            course_id = field(conversation, "course_id")
            conversation_source = field(conversation, "source", "chat")
            title = ElidedLabel(
                field(conversation, "title", "Nouvelle discussion")
            )
            title.setStyleSheet("font-weight: 500;")
            label = "Agent" if conversation_source == "agent" else "Discussion"
            course = _course_name(self.host, course_id)
            meta = secondary_label(
                f"{course} · {label} · "
                f"{relative_date(field(conversation, 'updated_at'))}"
            )
            meta.setStyleSheet("font-size: 11px;")
            card.layout.addWidget(title)
            card.layout.addWidget(meta)
            card.clicked.connect(
                lambda conversation_id=conversation_id,
                course_id=course_id,
                conversation_source=conversation_source: self.host.open_chat(
                    conversation_id=conversation_id,
                    course_id=course_id,
                    read_only=conversation_source == "agent",
                )
            )
            self.rows_layout.addWidget(card)
            self.rows.append(card)


class SettingsPage(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.profile = host.store.get_profile()
        self.level: str | None = None
        self.subjects: list[str] = []
        self._layout = centered_scroll(self)
        title = QLabel("Réglages")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        apply_tracking(title, -0.6)
        self._layout.addWidget(title)
        self._layout.addSpacing(26)
        mascot_label = QLabel("Ton prof")
        mascot_label.setStyleSheet("font-weight: 600;")
        self._layout.addWidget(mascot_label)
        mascot_holder = QWidget()
        self.mascot_layout = FlowLayout(mascot_holder, spacing=8)
        self.mascot_tiles: dict[str, MascotTile] = {}
        for index, mascot in enumerate(MASCOTS):
            tile = MascotTile(
                mascot.id,
                selected=mascot.id == host.mascot_id,
                tile_width=92,
                mascot_size=56,
                motion_offset=index * 360,
            )
            tile.chosen.connect(self._select_mascot)
            self.mascot_tiles[mascot.id] = tile
            self.mascot_layout.addWidget(tile)
        self._layout.addWidget(mascot_holder)
        self._layout.addSpacing(24)
        name_label = QLabel("Ton prénom")
        name_label.setStyleSheet("font-weight: 600;")
        self._layout.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setObjectName("settingsName")
        self.name_input.setFixedHeight(40)
        self._layout.addSpacing(8)
        self._layout.addWidget(self.name_input)
        self._layout.addSpacing(23)
        level_label = QLabel("Ton niveau")
        level_label.setStyleSheet("font-weight: 600;")
        self._layout.addWidget(level_label)
        self.level_holder = QWidget()
        self.level_layout = FlowLayout(self.level_holder, spacing=8)
        self.level_chips: dict[str, Chip] = {}
        for level in LEVELS:
            chip = Chip(level, selectable=False)
            chip.clicked.connect(lambda chosen=level: self.select_level(chosen))
            self.level_chips[level] = chip
            self.level_layout.addWidget(chip)
        self._layout.addWidget(self.level_holder)
        self._layout.addSpacing(23)
        subjects_label = QLabel("Tes matières")
        subjects_label.setStyleSheet("font-weight: 600;")
        self._layout.addWidget(subjects_label)
        self.subject_input = QLineEdit()
        self.subject_input.setObjectName("settingsSubject")
        self.subject_input.setPlaceholderText("Ajouter une matière")
        self.subject_input.setFixedHeight(40)
        self.subject_input.returnPressed.connect(self._add_typed_subject)
        self._layout.addSpacing(8)
        self._layout.addWidget(self.subject_input)
        self.subject_holder = QWidget()
        self.subject_layout = FlowLayout(self.subject_holder, spacing=8)
        self.subject_chips: dict[str, Chip] = {}
        self._layout.addWidget(self.subject_holder)
        self._layout.addSpacing(22)
        self.shortcut_label = secondary_label("")
        self._layout.addWidget(self.shortcut_label)
        self._layout.addSpacing(20)
        self.save_button = PrimaryButton("Enregistrer")
        self.save_button.clicked.connect(self.save)
        self.saved_label = secondary_label("")
        self.saved_label.setStyleSheet("font-size: 11px;")
        saved_row = QHBoxLayout()
        saved_row.addWidget(self.save_button)
        saved_row.addWidget(self.saved_label, 1)
        self._layout.addLayout(saved_row)
        self._layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        self.profile = self.host.store.get_profile()
        if self.profile is None:
            return
        self.refresh_mascot()
        self.name_input.setText(field(self.profile, "name", ""))
        self.level = field(self.profile, "level")
        for level, chip in self.level_chips.items():
            chip.set_selected(level == self.level)
        self.subjects = list(field(self.profile, "subjects", []))
        self._refresh_subjects()
        hotkey = str(getattr(self.host.settings, "hotkey", "ctrl+shift") or "ctrl+shift")
        self.shortcut_label.setText(
            f"Raccourci : {hotkey.title()}"
        )

    def refresh_mascot(self) -> None:
        for mascot_id, tile in self.mascot_tiles.items():
            tile.set_selected(mascot_id == self.host.mascot_id)

    def _select_mascot(self, mascot_id: str) -> None:
        self.host.set_mascot(mascot_id)

    def select_level(self, level: str) -> None:
        self.level = None if self.level == level else level
        for name, chip in self.level_chips.items():
            chip.set_selected(name == self.level)

    def add_subject(self, subject: str) -> bool:
        value = subject.strip()
        if not value or any(item.casefold() == value.casefold() for item in self.subjects):
            return False
        self.subjects.append(value)
        self._refresh_subjects()
        return True

    def _add_typed_subject(self) -> None:
        self.add_subject(self.subject_input.text())
        self.subject_input.clear()

    def _remove_subject(self, subject: str) -> None:
        self.subjects = [item for item in self.subjects if item != subject]
        self._refresh_subjects()

    def _refresh_subjects(self) -> None:
        clear_layout(self.subject_layout)
        self.subject_chips = {}
        for subject in self.subjects:
            chip = Chip(subject, removable=True, selectable=False)
            chip.removed.connect(lambda value=subject: self._remove_subject(value))
            self.subject_chips[subject] = chip
            self.subject_layout.addWidget(chip)

    def save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            return
        self.host.store.save_profile(name, self.level, list(self.subjects))
        existing = {
            str(field(course, "subject", "")).casefold()
            for course in self.host.store.list_courses()
        }
        for subject in self.subjects:
            if subject.casefold() not in existing:
                self.host.store.create_course(subject, subject)
        self.host.sidebar.refresh_profile()
        self.host.sidebar.refresh_courses()
        self.host.home_page.refresh()
        self.host._notify_library_changed()
        self.saved_label.setText("Enregistré")
        fade_in(self.saved_label, 180)


class ChatInput(QPlainTextEdit):
    send_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("chatInput")
        self.setPlaceholderText("Pose ta question…")
        self.setTabChangesFocus(True)
        self.setMinimumHeight(36)
        self.setMaximumHeight(112)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.textChanged.connect(self._resize_for_content)
        self._resize_for_content()

    def _resize_for_content(self) -> None:
        lines = min(5, max(1, self.document().blockCount()))
        document_height = self.document().documentLayout().documentSize().height()
        self.setFixedHeight(
            min(
                112,
                max(
                    36,
                    int(
                        max(
                            document_height,
                            lines * self.fontMetrics().lineSpacing(),
                        )
                        + 12
                    ),
                ),
            )
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.insertPlainText("\n")
                event.accept()
                return
            event.accept()
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatPage(QWidget):
    result_ready = pyqtSignal(object)

    def __init__(
        self,
        host,
        *,
        conversation_id: int | None,
        course_id: int | None,
        read_only: bool,
        back_key,
    ):
        super().__init__(host)
        self.host = host
        self.conversation_id = conversation_id
        self.course_id = course_id
        self.read_only = read_only
        self.back_key = back_key
        self._threads: list[threading.Thread] = []
        self._last_question = ""
        self._busy = False
        self._conversation = self._find_conversation(conversation_id)
        if self._conversation is not None:
            self.course_id = field(self._conversation, "course_id")
            self.read_only = (
                self.read_only or field(self._conversation, "source") == "agent"
            )
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 25, 48, 22)
        root.setSpacing(12)
        header = QHBoxLayout()
        self.back_button = TextButton("‹ Retour")
        self.back_button.clicked.connect(lambda: self.host.navigate_to_key(self.back_key))
        header.addWidget(self.back_button)
        header.addSpacing(12)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 18px; font-weight: 600;")
        header.addWidget(self.title, 1)
        root.addLayout(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBar(OverlayScrollBar(self.scroll))
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 9, 0, 12)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch(1)
        self.scroll.setWidget(self.messages_widget)
        root.addWidget(self.scroll, 1)
        self.bubble_labels: list[QLabel] = []
        self.message_bubbles: list[QFrame] = []
        self._message_bubble_specs: list[tuple[QFrame, QLabel, str]] = []
        self.source_chips: list[QPushButton] = []
        self.busy_row = QWidget()
        busy_layout = QHBoxLayout(self.busy_row)
        busy_layout.setContentsMargins(0, 0, 0, 0)
        self.busy_mascot = MascotWidget(
            host.mascot_id,
            28,
            animate=True,
        )
        self.busy_label = secondary_label(
            f"{mascot_name(host.mascot_id)} réfléchit…"
        )
        self.busy_dots = QLabel("·")
        self.busy_dots.setProperty("secondary", True)
        busy_layout.addWidget(self.busy_mascot)
        busy_layout.addWidget(self.busy_label)
        busy_layout.addWidget(self.busy_dots)
        busy_layout.addStretch(1)
        self.busy_row.setVisible(False)
        root.addWidget(self.busy_row)
        self._busy_stage = 0
        self.busy_timer = QTimer(self)
        self.busy_timer.setInterval(320)
        self.busy_timer.timeout.connect(self._animate_busy)
        self.error_row = QWidget()
        error_layout = QHBoxLayout(self.error_row)
        error_layout.setContentsMargins(10, 7, 10, 7)
        error_layout.setSpacing(9)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f"color: {DANGER};")
        self.retry_button = TextButton("Réessayer")
        self.retry_button.clicked.connect(self.retry)
        error_layout.addWidget(self.error_label, 1)
        error_layout.addWidget(self.retry_button)
        self.error_row.setStyleSheet(
            "background: rgba(255,59,48,0.08); border-radius: 8px;"
        )
        self.error_row.setVisible(False)
        root.addWidget(self.error_row)
        self.footer = QWidget()
        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(7)
        self.api_key_note = secondary_label(
            "Ajoute ta clé OpenAI (OPENAI_API_KEY dans .env) pour poser des questions."
        )
        self.api_key_note.setStyleSheet("font-size: 11px;")
        self.api_key_note.setVisible(False)
        footer_layout.addWidget(self.api_key_note)
        self.composer = QFrame()
        self.composer.setObjectName("chatComposer")
        self.composer.setStyleSheet(
            f"QFrame#chatComposer {{ background: {SURFACE}; border: 1px solid {SEPARATOR}; "
            "border-radius: 22px; }"
        )
        input_row = QHBoxLayout(self.composer)
        input_row.setContentsMargins(4, 4, 4, 4)
        input_row.setSpacing(4)
        self.input = ChatInput(self.composer)
        self.input.setStyleSheet(
            "QPlainTextEdit#chatInput { background: transparent; border: 0; "
            "border-radius: 16px; padding: 7px 8px; }"
        )
        self.input.send_requested.connect(self.send)
        self.input.textChanged.connect(self._update_send_enabled)
        input_row.addWidget(self.input, 1)
        self.send_button = QToolButton()
        self.send_button.setObjectName("sendButton")
        self.send_button.setIcon(icon("send", "#FFFFFF"))
        self.send_button.setIconSize(QSize(16, 16))
        self.send_button.setFixedSize(36, 36)
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setToolTip("Envoyer")
        self.send_button.setAccessibleName("Envoyer")
        self.send_button.setStyleSheet(
            f"QToolButton#sendButton {{ color: white; background: {ACCENT}; "
            "border: 0; border-radius: 18px; }"
            f"QToolButton#sendButton:hover {{ background: {ACCENT_PRESSED}; }}"
        )
        self.send_button.clicked.connect(self.send)
        input_row.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.composer.setMinimumHeight(44)
        self.composer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        footer_layout.addWidget(self.composer)
        self.read_only_footer = secondary_label("Conversation avec l'agent — lecture seule")
        self.read_only_footer.setStyleSheet("font-size: 11px;")
        self.read_only_footer.setVisible(False)
        root.addWidget(self.footer)
        root.addWidget(self.read_only_footer)
        self.result_ready.connect(self._handle_result)
        self._set_title()
        self.refresh_messages()
        if self.read_only:
            self.footer.setVisible(False)
            self.read_only_footer.setVisible(True)
        else:
            api_key = getattr(self.host.settings, "api_key", "")
            self.api_key_note.setVisible(not bool(api_key))
            self._update_send_enabled()

    def _find_conversation(self, conversation_id: int | None):
        if conversation_id is None:
            return None
        return next(
            (
                conversation
                for conversation in self.host.store.recent_conversations(limit=500)
                if field(conversation, "id") == conversation_id
            ),
            None,
        )

    def _set_title(self) -> None:
        if self._conversation is not None:
            title = field(self._conversation, "title", "")
        else:
            title = _course_name(self.host, self.course_id)
        self.title.setText(title)

    def refresh_messages(self) -> None:
        clear_layout(self.messages_layout)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bubble_labels = []
        self.message_bubbles = []
        self._message_bubble_specs = []
        self.source_chips = []
        if self.conversation_id is not None:
            for message in self.host.store.get_messages(self.conversation_id):
                self._append_message(
                    field(message, "role", "assistant"),
                    field(message, "text", ""),
                    field(message, "sources", []),
                )
        self.messages_layout.addStretch(1)
        self._scroll_to_bottom()

    def _append_message(self, role: str, text: str, sources=None) -> None:
        is_user = role == "user"
        message_column = QVBoxLayout()
        message_column.setSpacing(6)
        bubble = QFrame()
        bubble.setObjectName("userBubble" if is_user else "assistantBubble")
        bubble_radius = 18
        bubble.setProperty("bubbleRadius", bubble_radius)
        border = "0" if is_user else f"1px solid {SEPARATOR}"
        bubble.setStyleSheet(
            f"QFrame#{bubble.objectName()} {{ background: "
            f"{ACCENT if is_user else 'rgba(255,255,255,0.76)'}; "
            f"border: {border}; "
            f"border-radius: {bubble_radius}px; }}"
        )
        bubble.setMinimumHeight(40)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 10, 16, 10)
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        text_label.setTextFormat(
            Qt.TextFormat.PlainText if is_user else Qt.TextFormat.MarkdownText
        )
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.bubble_labels.append(text_label)
        self.message_bubbles.append(bubble)
        self._message_bubble_specs.append((bubble, text_label, text))
        if is_user:
            text_label.setStyleSheet("color: white; background: transparent;")
        bubble_layout.addWidget(text_label)
        self._size_message_bubble(bubble, text_label, text)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if is_user:
            row.addStretch(1)
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        else:
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch(1)
        message_column.addLayout(row)
        if not is_user and sources:
            chips = QHBoxLayout()
            chips.setSpacing(6)
            seen = set()
            for source in sources:
                document = field(source, "document", "")
                filename = field(document, "filename", document)
                if not isinstance(filename, str):
                    filename = field(filename, "name", str(filename))
                page = field(source, "page")
                label = filename + (f" · p. {page}" if page is not None else "")
                if label in seen:
                    continue
                seen.add(label)
                chip = QPushButton(label)
                chip.setObjectName("sourceChip")
                chip.setIcon(icon("document"))
                chip.setIconSize(QSize(12, 12))
                hit_text = str(field(source, "text", ""))
                chip.setToolTip(hit_text[:200])
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setStyleSheet(
                    f"QPushButton#sourceChip {{ color: {SECONDARY}; background: {SURFACE}; "
                    "border: 0; border-radius: 12px; "
                    "font-size: 11px; padding: 5px 11px; }"
                    f"QPushButton#sourceChip:hover {{ background: {HOVER}; color: {TEXT}; }}"
                )
                self.source_chips.append(chip)
                chips.addWidget(chip, 0, Qt.AlignmentFlag.AlignLeft)
            chips.addStretch(1)
            message_column.addLayout(chips)
        self.messages_layout.addLayout(message_column)

    def _maximum_bubble_width(self) -> int:
        available_width = self.scroll.viewport().width()
        if available_width <= 0:
            available_width = self.host.pages.width()
            margins = self.layout().contentsMargins()
            available_width -= margins.left() + margins.right()
        if available_width <= 0:
            available_width = max(1, self.host.width() - 372)
        return max(1, int(available_width * 0.70))

    def _size_message_bubble(
        self,
        bubble: QFrame,
        text_label: QLabel,
        text: str,
    ) -> None:
        maximum_width = self._maximum_bubble_width()
        bubble.setMaximumWidth(maximum_width)
        margins = bubble.layout().contentsMargins()
        border_width = 2 if bubble.objectName() == "assistantBubble" else 0
        maximum_text_width = max(
            1,
            maximum_width - margins.left() - margins.right() - border_width,
        )
        bounds = QFontMetrics(text_label.font()).boundingRect(
            QRect(0, 0, maximum_text_width, 10000),
            Qt.TextFlag.TextWordWrap,
            text,
        )
        text_width = min(maximum_text_width, max(1, bounds.width()))
        bubble_width = min(
            maximum_width,
            text_width + margins.left() + margins.right() + border_width,
        )
        bubble.setFixedWidth(bubble_width)
        text_label.setFixedWidth(
            max(1, bubble_width - margins.left() - margins.right() - border_width)
        )
        text_label.updateGeometry()

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_message_bubble_specs"):
            for bubble, label, text in self._message_bubble_specs:
                self._size_message_bubble(bubble, label, text)

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            ),
        )

    def _update_send_enabled(self) -> None:
        enabled = bool(self.input.toPlainText().strip()) and not self._busy
        self.send_button.setEnabled(enabled)
        self.send_button.setIcon(icon("send", "#FAFAFA"))

    def send(self) -> None:
        self._submit(self.input.toPlainText().strip(), append_user=True)

    def _submit(self, question: str, *, append_user: bool) -> None:
        if not question or self._busy or self.read_only:
            return
        if not getattr(self.host.settings, "api_key", ""):
            self.api_key_note.setVisible(True)
            return
        if append_user:
            self._last_question = question
            self._append_message("user", question)
        self.input.clear()
        self._scroll_to_bottom()
        self.error_row.setVisible(False)
        self._set_busy(True)
        ask_fn = self.host.ask_fn or _default_ask
        store = self.host.store
        embedder = self.host.embedder
        conversation_id = self.conversation_id
        course_id = self.course_id
        api_key = self.host.settings.api_key
        model = getattr(self.host.settings, "model", None)

        def run() -> None:
            try:
                result = ask_fn(
                    store,
                    embedder,
                    question,
                    conversation_id,
                    course_id,
                    api_key,
                    model=model,
                )
                payload = (True, result, "")
            except Exception as error:
                payload = (False, None, str(error))
            self.result_ready.emit(payload)

        worker = threading.Thread(target=run, daemon=True)
        self._threads.append(worker)
        worker.start()

    def retry(self) -> None:
        if self._last_question:
            self._submit(self._last_question, append_user=False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.input.setDisabled(busy)
        self.busy_row.setVisible(busy)
        if busy:
            self.busy_timer.start()
        else:
            self.busy_timer.stop()
        self._update_send_enabled()

    def _animate_busy(self) -> None:
        self._busy_stage = (self._busy_stage + 1) % 3
        self.busy_dots.setText("·" * (self._busy_stage + 1))

    def set_mascot(self, mascot_id: str) -> None:
        self.busy_mascot.set_mascot(mascot_id)
        self.busy_label.setText(f"{mascot_name(mascot_id)} réfléchit…")

    @pyqtSlot(object)
    def _handle_result(self, payload) -> None:
        success, result, error_message = payload
        self._set_busy(False)
        if not success:
            short_message = error_message.strip()[:180] or "Erreur inconnue."
            self.error_label.setText(f"Gerald n'a pas pu répondre : {short_message}")
            self.error_row.setVisible(True)
            self._scroll_to_bottom()
            return
        conversation_id, answer = result
        self.conversation_id = conversation_id
        self._conversation = self._find_conversation(conversation_id)
        self._set_title()
        answer_text = field(answer, "text", "")
        sources = field(answer, "sources", [])
        self._append_message("assistant", answer_text, sources)
        self.host.discussions_page.refresh()
        self._scroll_to_bottom()

    def closeEvent(self, event: QEvent) -> None:
        self.busy_timer.stop()
        super().closeEvent(event)


def _default_ask(*args, **kwargs):
    from gerald.library import ask

    return ask(*args, **kwargs)
