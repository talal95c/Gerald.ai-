from __future__ import annotations

from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gerald.home.events import events
from gerald.home.agents import load_mascot, save_mascot
from gerald.home.icons import icon
from gerald.home.mascots import DEFAULT_MASCOT, MASCOTS_BY_ID
from gerald.home.pages import (
    ChatPage,
    CoursePage,
    DiscussionsPage,
    HomePage,
    SettingsPage,
    field,
)
from gerald.home.style import (
    ACCENT,
    GlassBackdrop,
    GlassPanel,
    HOVER,
    SECONDARY,
    fade_in,
    font_family,
    stylesheet,
)
from gerald.home.widgets import Avatar


class Sidebar(GlassPanel):
    def __init__(self, host: HomeWindow):
        super().__init__(host)
        self.host = host
        self.setObjectName("geraldSidebar")
        self.setFixedWidth(240)
        self.setStyleSheet(
            "QPushButton#sidebarButton { text-align: left; border: 0; border-radius: 12px; "
            "padding: 4px 9px; min-height: 28px; background: transparent; }"
            f"QPushButton#sidebarButton:hover {{ background: {HOVER}; }}"
            f"QPushButton#sidebarButton[selected=\"true\"] {{ color: #FAFAFA; "
            f"background: {ACCENT}; font-weight: 600; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 18, 16, 14)
        root.setSpacing(5)
        profile_row = QHBoxLayout()
        self.profile_row = profile_row
        profile_row.setSpacing(10)
        self.avatar = Avatar("", 32)
        profile_row.addWidget(self.avatar)
        profile_labels = QVBoxLayout()
        profile_labels.setSpacing(2)
        self.profile_name = QLabel()
        self.profile_name.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.profile_level = QLabel()
        self.profile_level.setProperty("secondary", True)
        self.profile_level.setStyleSheet("font-size: 11px;")
        profile_labels.addWidget(self.profile_name)
        profile_labels.addWidget(self.profile_level)
        profile_row.addLayout(profile_labels, 1)
        root.addLayout(profile_row)
        root.addSpacing(21)

        self.nav_buttons: dict[str, QPushButton] = {}
        self._add_nav(root, "home", "Accueil", "home", self.host.open_home)
        self._add_nav(
            root,
            "discussions",
            "Discussions",
            "chat",
            self.host.open_discussions,
        )
        root.addSpacing(18)
        self.section_label = QLabel("Cours")
        self.section_label.setProperty("secondary", True)
        self.section_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; padding-left: 9px; padding-bottom: 3px;"
        )
        root.addWidget(self.section_label)
        self.course_layout = QVBoxLayout()
        self.course_layout.setContentsMargins(0, 0, 0, 0)
        self.course_layout.setSpacing(3)
        root.addLayout(self.course_layout)
        self.course_buttons: dict[int, QPushButton] = {}
        new_course = self._make_button("Nouveau cours", "plus")
        new_course.setProperty("secondaryText", True)
        new_course.setStyleSheet(
            f"QPushButton#sidebarButton {{ color: {SECONDARY}; text-align: left; }}"
        )
        new_course.clicked.connect(self.host.create_course)
        root.addWidget(new_course)
        root.addStretch(1)
        self.settings_button = self._make_button("Réglages", "gear")
        self.settings_button.clicked.connect(self.host.open_settings)
        root.addWidget(self.settings_button)
        self.refresh_profile()
        self.refresh_courses()
        self.select("home")

    def _make_button(self, label: str, icon_name: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("sidebarButton")
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(40)
        button.setProperty("sidebarIcon", icon_name)
        return button

    def _add_nav(self, layout, key, label, icon_name, callback) -> None:
        button = self._make_button(label, icon_name)
        button.clicked.connect(callback)
        self.nav_buttons[key] = button
        layout.addWidget(button)

    def refresh_profile(self) -> None:
        profile = self.host.store.get_profile()
        if profile is None:
            return
        name = field(profile, "name", "")
        self.profile_name.setText(name)
        self.profile_name.setToolTip(name)
        self.profile_level.setText(field(profile, "level") or "Ajoute ton niveau")
        avatar = Avatar(name, 32, self)
        self.profile_row.replaceWidget(self.avatar, avatar)
        self.avatar.deleteLater()
        self.avatar = avatar

    def refresh_courses(self) -> None:
        while self.course_layout.count():
            item = self.course_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.course_buttons = {}
        for course in self.host.store.list_courses():
            course_id = field(course, "id")
            title = field(course, "title", "")
            button = self._make_button(title, "book")
            button.setToolTip(title)
            button.setProperty("courseId", course_id)
            button.clicked.connect(
                lambda _checked=False, course_id=course_id: self.host.open_course(course_id)
            )
            self.course_layout.addWidget(button)
            self.course_buttons[course_id] = button
        self.select(self.host._sidebar_selection)

    def select(self, key) -> None:
        self.host._sidebar_selection = key
        for nav_key, button in self.nav_buttons.items():
            selected = key == nav_key
            button.setProperty("selected", selected)
            button.setIcon(
                icon(
                    button.property("sidebarIcon"),
                    "#FAFAFA" if selected else SECONDARY,
                )
            )
            button.style().unpolish(button)
            button.style().polish(button)
        for course_id, button in self.course_buttons.items():
            selected = key == ("course", course_id)
            button.setProperty("selected", selected)
            button.setIcon(icon("book", "#FAFAFA" if selected else SECONDARY))
            button.style().unpolish(button)
            button.style().polish(button)
        settings_selected = key == "settings"
        self.settings_button.setProperty("selected", settings_selected)
        self.settings_button.setIcon(
            icon("gear", "#FAFAFA" if settings_selected else SECONDARY)
        )
        self.settings_button.style().unpolish(self.settings_button)
        self.settings_button.style().polish(self.settings_button)


class HomeWindow(GlassBackdrop):
    def __init__(
        self,
        store,
        indexer,
        settings,
        on_library_changed,
        *,
        ask_fn=None,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.indexer = indexer
        self.embedder = indexer.embedder
        self.settings = settings
        self.on_library_changed = on_library_changed
        self.ask_fn = ask_fn
        self.mascot_id = load_mascot()
        self._home_closed = False
        self._current_page_key = "home"
        self._previous_page_key = "home"
        self._sidebar_selection = "home"
        self._chat_serial = 0
        self._course_pages: dict[int, CoursePage] = {}
        self._chat_pages: list[ChatPage] = []
        self._pages_by_key: dict[object, QWidget] = {}
        self._document_callback = events.on_done
        self.setObjectName("geraldHome")
        self.setWindowTitle("Gerald")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setFont(QFont(font_family()))
        self.setStyleSheet(stylesheet())
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        self.sidebar = Sidebar(self)
        root.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        self.pages.setObjectName("homePages")
        root.addWidget(self.pages, 1)
        self.home_page = HomePage(self)
        self.discussions_page = DiscussionsPage(self)
        self.settings_page = SettingsPage(self)
        self._persistent_pages = {
            "home": self.home_page,
            "discussions": self.discussions_page,
            "settings": self.settings_page,
        }
        for page in self._persistent_pages.values():
            self.pages.addWidget(page)
        self._pages_by_key.update(self._persistent_pages)
        self.pages.setCurrentWidget(self.home_page)
        events.document_updated.connect(self._on_document_updated)
        self.home_page.refresh()

    @property
    def current_page(self) -> QWidget:
        return self.pages.currentWidget()

    @property
    def current_page_key(self):
        return self._current_page_key

    def _show_page(self, page: QWidget, key, *, sidebar_selection=None) -> None:
        current = self.pages.currentWidget()
        if current is not page:
            self._previous_page_key = self._current_page_key
        if self.pages.indexOf(page) < 0:
            self.pages.addWidget(page)
        self._pages_by_key[key] = page
        self._current_page_key = key
        self.pages.setCurrentWidget(page)
        if sidebar_selection is not None:
            self.sidebar.select(sidebar_selection)
        fade_in(page)

    def navigate_to_key(self, key) -> None:
        if key in self._pages_by_key:
            page = self._pages_by_key[key]
            if page is self.home_page:
                self.home_page.refresh()
            elif page is self.discussions_page:
                self.discussions_page.refresh()
            elif isinstance(page, CoursePage):
                page.refresh()
            elif page is self.settings_page:
                page.refresh()
            selection = key if key in ("home", "discussions", "settings") else None
            if isinstance(key, tuple) and key and key[0] == "course":
                selection = key
            self._show_page(page, key, sidebar_selection=selection)
            return
        if isinstance(key, tuple) and key and key[0] == "course":
            self.open_course(key[1])

    def open_home(self) -> None:
        self.home_page.refresh()
        self._show_page(self.home_page, "home", sidebar_selection="home")

    def open_discussions(self) -> None:
        self.discussions_page.refresh()
        self._show_page(
            self.discussions_page,
            "discussions",
            sidebar_selection="discussions",
        )

    def open_settings(self) -> None:
        self.settings_page.refresh()
        self._show_page(self.settings_page, "settings", sidebar_selection="settings")

    def create_course(self) -> None:
        course = self.store.create_course("Nouveau cours", "")
        self.sidebar.refresh_courses()
        self.home_page.refresh()
        self.open_course(field(course, "id"), focus_title=True)

    def open_course(self, course_id: int, *, focus_title: bool = False) -> CoursePage:
        page = self._course_pages.get(course_id)
        if page is None:
            course = next(
                (item for item in self.store.list_courses() if field(item, "id") == course_id),
                None,
            )
            if course is None:
                self.open_home()
                return self.home_page
            page = CoursePage(self, course)
            self._course_pages[course_id] = page
        page.refresh()
        self._show_page(page, ("course", course_id), sidebar_selection=("course", course_id))
        if focus_title:
            page.title_input.selectAll()
            page.title_input.setFocus()
        return page

    def open_chat(
        self,
        conversation_id: int | None = None,
        course_id: int | None = None,
        read_only: bool = False,
    ) -> ChatPage:
        back_key = self._current_page_key
        self._chat_serial += 1
        key = ("chat", self._chat_serial)
        page = ChatPage(
            self,
            conversation_id=conversation_id,
            course_id=course_id,
            read_only=read_only,
            back_key=back_key,
        )
        self._chat_pages.append(page)
        self._show_page(page, key)
        return page

    def refresh(self) -> None:
        self.home_page.refresh()
        self.discussions_page.refresh()
        current = self.current_page
        if isinstance(current, ChatPage):
            current.refresh_messages()
        elif isinstance(current, CoursePage):
            current.refresh()
        elif current is self.settings_page:
            current.refresh()

    def set_mascot(self, mascot_id: str) -> None:
        if mascot_id not in MASCOTS_BY_ID:
            mascot_id = DEFAULT_MASCOT
        self.mascot_id = mascot_id
        save_mascot(mascot_id)
        self.home_page.set_mascot(mascot_id)
        self.settings_page.refresh_mascot()
        for page in self._chat_pages:
            page.set_mascot(mascot_id)

    def _notify_library_changed(self) -> None:
        if callable(self.on_library_changed):
            self.on_library_changed()

    @pyqtSlot(object)
    def _on_document_updated(self, document) -> None:
        course_id = field(document, "course_id")
        page = self._course_pages.get(course_id)
        if page is not None:
            page.refresh_documents()
        self.home_page.refresh()
        self._notify_library_changed()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.refresh()

    def closeEvent(self, event) -> None:
        self._home_closed = True
        self._disconnect_document_updates()
        super().closeEvent(event)

    def _disconnect_document_updates(self) -> None:
        try:
            events.document_updated.disconnect(self._on_document_updated)
        except (TypeError, RuntimeError):
            pass


class GeraldWindow(GlassBackdrop):
    def __init__(
        self,
        store,
        indexer,
        settings,
        on_library_changed,
        *,
        ask_fn=None,
        parent=None,
    ):
        super().__init__(parent)
        self.store = store
        self.indexer = indexer
        self.settings = settings
        self.on_library_changed = on_library_changed
        self.ask_fn = ask_fn
        self._home_closed = False
        self.setObjectName("geraldShell")
        self.setWindowTitle("Gerald")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setFont(QFont(font_family()))
        self.setStyleSheet(stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.views = QStackedWidget()
        self.views.setObjectName("geraldViews")
        root.addWidget(self.views)
        self.onboarding = None
        self.home_view = None
        if store.get_profile() is None:
            from gerald.home.onboarding import OnboardingWindow

            self.onboarding = OnboardingWindow(
                store,
                indexer,
                settings,
                on_library_changed,
                parent=self,
            )
            self.views.addWidget(self.onboarding)
            self.views.setCurrentWidget(self.onboarding)
            self.onboarding.finished.connect(self.show_home)
        else:
            self.show_home()

    @property
    def current_view(self) -> QWidget:
        return self.views.currentWidget()

    @property
    def sidebar(self):
        return self.home_view.sidebar if self.home_view is not None else None

    @property
    def pages(self):
        return self.home_view.pages if self.home_view is not None else self.views

    @property
    def home_page(self):
        return self.home_view.home_page if self.home_view is not None else None

    @property
    def discussions_page(self):
        return self.home_view.discussions_page if self.home_view is not None else None

    @property
    def settings_page(self):
        return self.home_view.settings_page if self.home_view is not None else None

    @property
    def current_page(self):
        return self.home_view.current_page if self.home_view is not None else self.current_view

    @property
    def current_page_key(self):
        return self.home_view.current_page_key if self.home_view is not None else None

    def open_course(self, course_id: int):
        return self.home_view.open_course(course_id) if self.home_view is not None else None

    def open_home(self) -> None:
        if self.home_view is not None:
            self.home_view.open_home()

    def open_chat(self, *args, **kwargs):
        return self.home_view.open_chat(*args, **kwargs) if self.home_view is not None else None

    def open_discussions(self) -> None:
        if self.home_view is not None:
            self.home_view.open_discussions()

    def open_settings(self) -> None:
        if self.home_view is not None:
            self.home_view.open_settings()

    def create_course(self) -> None:
        if self.home_view is not None:
            self.home_view.create_course()

    def navigate_to_key(self, key) -> None:
        if self.home_view is not None:
            self.home_view.navigate_to_key(key)

    def show_home(self) -> None:
        if self.home_view is None:
            self.home_view = HomeWindow(
                self.store,
                self.indexer,
                self.settings,
                self.on_library_changed,
                ask_fn=self.ask_fn,
                parent=self,
            )
            self.views.addWidget(self.home_view)
        self.views.setCurrentWidget(self.home_view)
        self.setMinimumSize(900, 600)
        self.resize(max(self.width(), 1100), max(self.height(), 720))
        self.home_view.refresh()
        fade_in(self.home_view)

    def refresh(self) -> None:
        if self.home_view is not None:
            self.home_view.refresh()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.ActivationChange
            and self.isActiveWindow()
            and self.home_view is not None
            and self.current_view is self.home_view
        ):
            self.home_view.refresh()

    def closeEvent(self, event) -> None:
        self._home_closed = True
        if self.home_view is not None:
            self.home_view._disconnect_document_updates()
        super().closeEvent(event)
