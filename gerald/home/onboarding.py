from __future__ import annotations

from PyQt6.QtCore import QTimer, QSize, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)

from gerald.home.events import events
from gerald.home.agents import load_mascot, save_mascot
from gerald.home.icons import icon
from gerald.home.pages import field
from gerald.home.mascots import (
    MASCOTS,
    MascotTile,
    MascotWidget,
)
from gerald.home.style import (
    ACCENT,
    apply_tracking,
    GlassBackdrop,
    SECONDARY,
    SEPARATOR,
    TEXT,
    fade_in,
    font_family,
    reduced_motion,
    stylesheet,
)
from gerald.home.widgets import (
    ChevronComboBox,
    Chip,
    DropZone,
    ElidedLabel,
    FlowLayout,
    PrimaryButton,
    TextButton,
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


class OnboardingWindow(GlassBackdrop):
    finished = pyqtSignal()

    def __init__(self, store, indexer, settings, on_library_changed, parent=None):
        super().__init__(parent)
        self.store = store
        self.indexer = indexer
        self.settings = settings
        self.on_library_changed = on_library_changed
        self._home_closed = False
        self.name = ""
        self.mascot_id = load_mascot()
        self._mascot_selected = False
        self.level: str | None = None
        self.subjects: list[str] = []
        self.queued_files: list[tuple[str, str]] = []
        self.current_step = 0
        self.setObjectName("geraldOnboarding")
        self.setWindowTitle("Gerald")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setFont(QFont(font_family()))
        self.setStyleSheet(stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(0)
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(0)
        self.back_button = TextButton("Retour")
        self.back_button.setFixedSize(64, 28)
        self.back_button.setEnabled(False)
        self.back_button_effect = QGraphicsOpacityEffect(self.back_button)
        self.back_button_effect.setOpacity(0)
        self.back_button.setGraphicsEffect(self.back_button_effect)
        self.back_button.clicked.connect(self.previous_step)
        progress_row.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignLeft)
        progress_row.addStretch(1)
        self.progress = QWidget()
        progress_layout = QHBoxLayout(self.progress)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(7)
        self.progress_dots: list[QFrame] = []
        for _index in range(5):
            dot = QFrame()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(f"QFrame {{ background: {SEPARATOR}; border-radius: 3px; }}")
            self.progress_dots.append(dot)
            progress_layout.addWidget(dot)
        progress_row.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignCenter)
        progress_row.addStretch(1)
        self.progress_spacer = QWidget()
        self.progress_spacer.setFixedWidth(self.back_button.width())
        self.progress_spacer.setFixedHeight(self.back_button.height())
        self.mascot_header = MascotWidget(self.mascot_id, 28, self.progress_spacer)
        self.mascot_header.move(18, 0)
        self.mascot_header.hide()
        progress_row.addWidget(self.progress_spacer)
        self.header = QWidget()
        self.header.setFixedHeight(36)
        self.header.setLayout(progress_row)
        root.addWidget(self.header)
        root.addStretch(1)

        self.stack = QStackedWidget()
        self.stack.setFixedWidth(620)
        self.stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.stack.addWidget(self._build_name_step())
        self.stack.addWidget(self._build_mascot_step())
        self.stack.addWidget(self._build_level_step())
        self.stack.addWidget(self._build_subjects_step())
        self.stack.addWidget(self._build_documents_step())
        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(self.stack)
        center.addStretch(1)
        root.addLayout(center)
        root.addStretch(1)
        self._set_step(0)

    def _step_layout(self, question: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel(question)
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 28px; font-weight: 600; color: {TEXT};")
        apply_tracking(title, -0.5)
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        title.setFixedHeight(title.sizeHint().height())
        description = QLabel(subtitle)
        description.setWordWrap(True)
        description.setProperty("secondary", True)
        description.setStyleSheet("font-size: 14px;")
        description.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        description.setFixedHeight(description.sizeHint().height())
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(description)
        layout.addSpacing(24)
        return page, layout

    def _build_name_step(self) -> QWidget:
        page, layout = self._step_layout(
            "Comment tu t'appelles ?",
            "Gerald s'en servira pour te parler.",
        )
        self.name_input = QLineEdit()
        self.name_input.setObjectName("nameInput")
        self.name_input.setPlaceholderText("Ton prénom")
        self.name_input.setFixedHeight(40)
        self.name_input.textChanged.connect(self._update_name_button)
        self.name_input.returnPressed.connect(self.next_step)
        self.name_continue = PrimaryButton("Continuer")
        self.name_continue.setMinimumWidth(140)
        self.name_continue.setEnabled(False)
        self.name_continue.clicked.connect(self.next_step)
        layout.addWidget(self.name_input)
        layout.addSpacing(16)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.name_continue)
        layout.addLayout(actions)
        return page

    def _build_mascot_step(self) -> QWidget:
        page, layout = self._step_layout(
            "Choisis ton prof",
            "Il t’accompagnera dans Gerald. Tu pourras le changer dans Réglages.",
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.mascot_tiles: dict[str, MascotTile] = {}
        for index, mascot in enumerate(MASCOTS):
            tile = MascotTile(
                mascot.id,
                selected=mascot.id == self.mascot_id,
                motion_offset=index * 360,
            )
            tile.chosen.connect(self._select_mascot)
            self.mascot_tiles[mascot.id] = tile
            row.addWidget(tile)
        layout.addLayout(row)
        layout.addSpacing(16)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.mascot_continue = PrimaryButton("Continuer")
        self.mascot_continue.setMinimumWidth(140)
        self.mascot_continue.clicked.connect(self.next_step)
        actions.addWidget(self.mascot_continue)
        layout.addLayout(actions)
        return page

    def _build_level_step(self) -> QWidget:
        page, layout = self._step_layout(
            "Ton niveau",
            "Facultatif — pour adapter ses explications.",
        )
        chips_holder = QWidget()
        chips_holder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        chips = FlowLayout(chips_holder, spacing=8)
        self.level_chips: dict[str, Chip] = {}
        for level in LEVELS:
            chip = Chip(level, selectable=False)
            chip.clicked.connect(lambda chosen=level: self._select_level(chosen))
            self.level_chips[level] = chip
            chips.addWidget(chip)
        chips_holder.setFixedHeight(chips.heightForWidth(620))
        layout.addWidget(chips_holder)
        layout.addSpacing(16)
        actions = QHBoxLayout()
        self.level_continue = PrimaryButton("Continuer")
        self.level_continue.setMinimumWidth(140)
        self.level_continue.clicked.connect(self.next_step)
        self.level_skip = TextButton("Passer")
        self.level_skip.clicked.connect(self._skip_level)
        actions.addStretch(1)
        actions.addWidget(self.level_skip)
        actions.addSpacing(16)
        actions.addWidget(self.level_continue)
        layout.addLayout(actions)
        return page

    def _build_subjects_step(self) -> QWidget:
        page, layout = self._step_layout(
            "Tes matières",
            "Une matière = un cours. Tu pourras en ajouter plus tard.",
        )
        self.subject_input = QLineEdit()
        self.subject_input.setObjectName("subjectInput")
        self.subject_input.setPlaceholderText("Ajouter une matière")
        self.subject_input.setFixedHeight(40)
        self.subject_input.returnPressed.connect(self._add_typed_subject)
        layout.addWidget(self.subject_input)
        self.subject_chips_holder = QWidget()
        self.subject_chips_holder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.subject_chips_layout = FlowLayout(self.subject_chips_holder, spacing=8)
        self.subject_chip_widgets: dict[str, Chip] = {}
        layout.addSpacing(12)
        layout.addWidget(self.subject_chips_holder)
        suggestions_label = QLabel("Suggestions")
        suggestions_label.setProperty("secondary", True)
        suggestions_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        suggestions_label.setFixedHeight(suggestions_label.sizeHint().height())
        layout.addSpacing(12)
        layout.addWidget(suggestions_label)
        self.suggestions_holder = QWidget()
        self.suggestions_holder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.suggestions_layout = FlowLayout(self.suggestions_holder, spacing=8)
        self.suggestion_buttons: dict[str, Chip] = {}
        layout.addSpacing(8)
        layout.addWidget(self.suggestions_holder)
        layout.addSpacing(16)
        actions = QHBoxLayout()
        self.subject_continue = PrimaryButton("Continuer")
        self.subject_continue.setMinimumWidth(140)
        self.subject_continue.setEnabled(False)
        self.subject_continue.clicked.connect(self.next_step)
        self.subject_skip = TextButton("Passer")
        self.subject_skip.clicked.connect(self._skip_subjects)
        actions.addStretch(1)
        actions.addWidget(self.subject_skip)
        actions.addSpacing(16)
        actions.addWidget(self.subject_continue)
        layout.addLayout(actions)
        self._refresh_subject_chips()
        return page

    def _build_documents_step(self) -> QWidget:
        page, layout = self._step_layout(
            "Dépose tes premiers cours",
            "Facultatif. Tu pourras en ajouter à tout moment.",
        )
        self.subject_combo_row = QWidget()
        combo_layout = QHBoxLayout(self.subject_combo_row)
        combo_layout.setContentsMargins(0, 0, 0, 0)
        combo_layout.setSpacing(9)
        self.subject_combo_label = QLabel("Pour :")
        self.subject_combo = ChevronComboBox()
        self.subject_combo.setObjectName("documentSubject")
        combo_layout.addWidget(self.subject_combo_label)
        combo_layout.addWidget(self.subject_combo, 1)
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self.queue_files)
        self.queue_holder = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_holder)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(0)
        self.queue_count = QLabel()
        self.queue_count.setProperty("secondary", True)
        self.actions_holder = QWidget()
        actions = QHBoxLayout(self.actions_holder)
        actions.setContentsMargins(0, 0, 0, 0)
        self.finish_button = PrimaryButton("Terminer")
        self.finish_button.setMinimumWidth(140)
        self.finish_button.clicked.connect(self.finish)
        self.later_button = TextButton("Plus tard")
        self.later_button.clicked.connect(self.finish)
        actions.addStretch(1)
        actions.addWidget(self.later_button)
        actions.addSpacing(16)
        actions.addWidget(self.finish_button)
        layout.addWidget(self.subject_combo_row)
        layout.addSpacing(12)
        layout.addWidget(self.drop_zone)
        layout.addSpacing(12)
        layout.addWidget(self.queue_count)
        layout.addSpacing(4)
        layout.addWidget(self.queue_holder)
        layout.addSpacing(16)
        layout.addWidget(self.actions_holder)
        self._refresh_queue()
        return page

    def _update_name_button(self, text: str) -> None:
        self.name_continue.setEnabled(bool(text.strip()))

    def _select_mascot(self, mascot_id: str) -> None:
        self.mascot_id = mascot_id
        self._mascot_selected = True
        for option_id, tile in self.mascot_tiles.items():
            tile.set_selected(option_id == mascot_id)
        self.mascot_header.set_mascot(mascot_id)
        self.mascot_header.setVisible(self.current_step >= 1)

    def _select_level(self, level: str) -> None:
        self.level = None if self.level == level else level
        for name, chip in self.level_chips.items():
            chip.set_selected(name == self.level)

    def _skip_level(self) -> None:
        self.level = None
        for chip in self.level_chips.values():
            chip.set_selected(False)
        self.next_step()

    def _add_typed_subject(self) -> None:
        self.add_subject(self.subject_input.text())
        self.subject_input.clear()

    def add_subject(self, subject: str) -> bool:
        value = subject.strip()
        if not value or any(existing.casefold() == value.casefold() for existing in self.subjects):
            return False
        self.subjects.append(value)
        self._refresh_subject_chips()
        return True

    def _remove_subject(self, subject: str) -> None:
        self.subjects = [value for value in self.subjects if value != subject]
        self._refresh_subject_chips()

    def _refresh_subject_chips(self) -> None:
        while self.subject_chips_layout.count():
            item = self.subject_chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.subject_chip_widgets = {}
        for subject in self.subjects:
            chip = Chip(subject, removable=True, selectable=False)
            chip.removed.connect(lambda value=subject: self._remove_subject(value))
            self.subject_chip_widgets[subject] = chip
            self.subject_chips_layout.addWidget(chip)
        while self.suggestions_layout.count():
            item = self.suggestions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.suggestion_buttons = {}
        for suggestion in SUGGESTIONS:
            if any(item.casefold() == suggestion.casefold() for item in self.subjects):
                continue
            chip = Chip(suggestion, selectable=False, compact=True)
            chip.clicked.connect(lambda value=suggestion: self.add_subject(value))
            self.suggestion_buttons[suggestion] = chip
            self.suggestions_layout.addWidget(chip)
        flow_width = self.stack.width() if hasattr(self, "stack") else 620
        self.subject_chips_holder.setFixedHeight(
            self.subject_chips_layout.heightForWidth(flow_width)
        )
        self.suggestions_holder.setFixedHeight(
            self.suggestions_layout.heightForWidth(flow_width)
        )
        self.subject_continue.setEnabled(bool(self.subjects))
        self._adjust_stack_height_if_current()

    def _skip_subjects(self) -> None:
        self.subjects.clear()
        self._refresh_subject_chips()
        self.next_step()

    def _refresh_queue(self) -> None:
        selected_subject = self.subject_combo.currentText()
        signals_blocked = self.subject_combo.blockSignals(True)
        self.subject_combo.clear()
        self.subject_combo.addItems(self.subjects)
        selected_index = self.subject_combo.findText(selected_subject)
        if selected_index >= 0:
            self.subject_combo.setCurrentIndex(selected_index)
        self.subject_combo.blockSignals(signals_blocked)
        has_subjects = bool(self.subjects)
        self.subject_combo_row.setVisible(has_subjects)
        self.subject_combo.setVisible(has_subjects)
        self.drop_zone.setVisible(has_subjects)
        self.queue_holder.setVisible(has_subjects)
        self.queue_count.setVisible(has_subjects and bool(self.queued_files))
        self.actions_holder.setVisible(True)
        while self.queue_layout.count():
            item = self.queue_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        if has_subjects:
            for index, (path, subject) in enumerate(self.queued_files):
                row = QFrame()
                row.setFixedHeight(36)
                row.setStyleSheet(
                    f"QFrame#queuedFileRow {{ border: 0; border-bottom: 1px solid {SEPARATOR}; }}"
                )
                row.setObjectName("queuedFileRow")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                filename = ElidedLabel(path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
                filename.setToolTip(path)
                filename.setStyleSheet(f"color: {TEXT};")
                meta = QLabel(subject)
                meta.setProperty("secondary", True)
                remove = QToolButton()
                remove.setIcon(icon("close"))
                remove.setIconSize(QSize(10, 10))
                remove.setAccessibleName("Retirer le fichier")
                remove.setToolTip("Retirer le fichier")
                remove.setFixedSize(24, 24)
                remove.setCursor(Qt.CursorShape.PointingHandCursor)
                remove.setStyleSheet(
                    f"QToolButton {{ color: {SECONDARY}; background: transparent; "
                    "border: 0; border-radius: 6px; padding: 0; }"
                    "QToolButton:hover { background: #EBEBF0; }"
                )
                remove.clicked.connect(lambda _checked=False, item_index=index: self.remove_file(item_index))
                row_layout.addWidget(filename, 1)
                row_layout.addWidget(meta)
                row_layout.addWidget(remove)
                self.queue_layout.addWidget(row)
            if self.queued_files:
                self.queue_count.setText(
                    f"{len(self.queued_files)} fichier"
                    f"{'s' if len(self.queued_files) != 1 else ''} prêt"
                    f"{'s' if len(self.queued_files) != 1 else ''}"
                )
        self._adjust_stack_height_if_current()

    def queue_files(self, paths: list[str]) -> None:
        subject = self.subject_combo.currentText()
        if not subject:
            return
        self.queued_files.extend((str(path), subject) for path in paths)
        self._refresh_queue()

    def remove_file(self, index: int) -> None:
        if 0 <= index < len(self.queued_files):
            self.queued_files.pop(index)
            self._refresh_queue()

    def next_step(self) -> None:
        if self.current_step == 0:
            self.name = self.name_input.text().strip()
            if not self.name:
                return
        if self.current_step < 4:
            self.current_step += 1
            self._set_step(self.current_step)

    def previous_step(self) -> None:
        if self.current_step > 0:
            self.current_step -= 1
            self._set_step(self.current_step)

    def _set_step(self, index: int) -> None:
        self.current_step = index
        self.stack.setCurrentIndex(index)
        self.back_button.setEnabled(index > 0)
        self.back_button_effect.setOpacity(1 if index > 0 else 0)
        self.mascot_header.setVisible(index >= 1)
        self._update_progress()
        if index == 4:
            self._refresh_queue()
        self._adjust_stack_height()
        fade_in(self.stack.currentWidget())

    def _update_progress(self) -> None:
        for index, dot in enumerate(self.progress_dots):
            active = index == self.current_step
            target_width = 22 if active else 6
            if reduced_motion():
                dot.setFixedSize(target_width, 6)
            else:
                animation = QVariantAnimation(dot)
                animation.setDuration(180)
                animation.setStartValue(dot.width())
                animation.setEndValue(target_width)
                animation.valueChanged.connect(
                    lambda width, current=dot: current.setFixedSize(int(width), 6)
                )
                dot._progress_animation = animation
                animation.start()
            dot.setStyleSheet(
                f"QFrame {{ background: {ACCENT if active else SEPARATOR}; "
                "border-radius: 3px; }"
            )

    def _adjust_stack_height(self) -> None:
        page = self.stack.currentWidget()
        if page is None:
            return
        page.layout().activate()
        self.stack.setFixedHeight(max(1, page.sizeHint().height()))

    def _adjust_stack_height_if_current(self) -> None:
        if hasattr(self, "stack") and self.stack.currentIndex() in (3, 4):
            QTimer.singleShot(0, self._adjust_stack_height)

    def finish(self) -> None:
        self.name = self.name_input.text().strip() or self.name
        if self._mascot_selected:
            save_mascot(self.mascot_id)
        self.store.save_profile(self.name, self.level, list(self.subjects))
        courses_by_subject = {
            str(field(course, "subject", "")).casefold(): course
            for course in self.store.list_courses()
        }
        for subject in self.subjects:
            if subject.casefold() not in courses_by_subject:
                course = self.store.create_course(subject, subject)
                courses_by_subject[subject.casefold()] = course
        for path, subject in self.queued_files:
            course = courses_by_subject.get(subject.casefold())
            if course is not None:
                self.indexer.add_document(
                    field(course, "id"),
                    path,
                    on_done=events.on_done,
                )
        self.on_library_changed()
        self.finished.emit()

    def closeEvent(self, event) -> None:
        self._home_closed = True
        super().closeEvent(event)
