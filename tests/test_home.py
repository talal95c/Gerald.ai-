import os
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog

import gerald.home as home_module
from fakes_library import Answer, FakeIndexer, FakeStore, Hit, fake_ask, seed
from gerald.home.agents import load_mascot
from gerald.home.icons import icon
from gerald.home.onboarding import OnboardingWindow
from gerald.home.pages import ChatPage
from gerald.home.widgets import FILE_FILTER, as_datetime, relative_date
from gerald.home.window import GeraldWindow, HomeWindow

_application = None


def app():
    global _application
    if _application is None:
        _application = QApplication.instance() or QApplication([])
        _application.setQuitOnLastWindowClosed(False)
    return _application


def wait_until(predicate, timeout=2):
    application = app()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    application.processEvents()
    return bool(predicate())


def data_dict(value):
    return asdict(value) if is_dataclass(value) else value


class DictStore:
    def __init__(self, store):
        self.store = store

    def __getattr__(self, name):
        return getattr(self.store, name)

    def get_profile(self):
        return data_dict(self.store.get_profile())

    def list_courses(self):
        return [data_dict(course) for course in self.store.list_courses()]

    def list_documents(self, course_id):
        return [
            data_dict(document)
            for document in self.store.list_documents(course_id)
        ]

    def recent_conversations(self, *args, **kwargs):
        return [
            data_dict(conversation)
            for conversation in self.store.recent_conversations(*args, **kwargs)
        ]

    def get_messages(self, conversation_id):
        return [
            data_dict(message)
            for message in self.store.get_messages(conversation_id)
        ]


def test_home_icons_render_into_their_full_dpr_pixmap():
    for name in (
        "home",
        "chat",
        "book",
        "plus",
        "gear",
        "document",
        "send",
        "close",
        "chevron-down",
    ):
        pixmap = icon(name).pixmap(QSize(16, 16))
        image = pixmap.toImage()
        midpoint_x = image.width() // 2
        midpoint_y = image.height() // 2
        assert any(
            image.pixelColor(x, y).alpha() > 0
            for x in range(midpoint_x, image.width())
            for y in range(midpoint_y, image.height())
        ), name


def test_onboarding_saves_profile_courses_and_queued_documents(monkeypatch, tmp_path):
    application = app()
    monkeypatch.setenv("GERALD_HOME", str(tmp_path))
    store = FakeStore()
    indexer = FakeIndexer(store)
    library_changes = []
    window = OnboardingWindow(
        store,
        indexer,
        SimpleNamespace(api_key="", hotkey="ctrl+shift"),
        lambda: library_changes.append(True),
    )
    finished = []
    window.finished.connect(lambda: finished.append(True))

    assert len(window.progress_dots) == 5
    assert all(
        window.stack.widget(index).layout().itemAt(1).spacerItem().sizeHint().height()
        == 8
        for index in range(5)
    )
    window.name_input.setText("  Talal  ")
    assert window.name_continue.isEnabled()
    window.name_continue.click()
    assert window.current_step == 1
    window.mascot_tiles["alba"].click()
    assert window.mascot_tiles["alba"].isChecked()
    assert not window.mascot_header.isHidden()
    window.mascot_continue.click()
    assert window.current_step == 2

    window.level_chips["Licence"].click()
    assert window.level == "Licence"
    window.level_continue.click()
    assert window.current_step == 3

    window.suggestion_buttons["Maths"].click()
    window.suggestion_buttons["Physique-Chimie"].click()
    window.subject_chip_widgets["Physique-Chimie"].remove_button.click()
    window.subject_input.setText("Informatique")
    QTest.keyClick(window.subject_input, Qt.Key.Key_Return)
    assert window.subjects == ["Maths", "Informatique"]
    assert "Maths" not in window.suggestion_buttons
    assert window.subject_continue.isEnabled()
    window.subject_continue.click()
    assert window.current_step == 4

    window.subject_combo.setCurrentText("Maths")
    window.drop_zone.files_dropped.emit(["/cours/Analyse.pdf"])
    window.subject_combo.setCurrentText("Informatique")
    window.drop_zone.files_dropped.emit(["/cours/Programmation.docx"])
    assert window.queued_files == [
        ("/cours/Analyse.pdf", "Maths"),
        ("/cours/Programmation.docx", "Informatique"),
    ]

    window.finish_button.click()

    assert store.get_profile().name == "Talal"
    assert store.get_profile().level == "Licence"
    assert store.get_profile().subjects == ["Maths", "Informatique"]
    courses = {course.subject: course for course in store.list_courses()}
    assert set(courses) == {"Maths", "Informatique"}
    add_calls = store.calls["add_document"]
    assert [(args[0], args[1]) for args, _kwargs in add_calls] == [
        (courses["Maths"].id, "/cours/Analyse.pdf"),
        (courses["Informatique"].id, "/cours/Programmation.docx"),
    ]
    assert all(kwargs["on_done"] is not None for _args, kwargs in add_calls)
    assert library_changes == [True]
    assert finished == [True]
    assert load_mascot() == "alba"
    window.close()
    application.processEvents()


def test_open_home_shows_and_reuses_onboarding_when_profile_is_missing(monkeypatch):
    application = app()
    monkeypatch.setattr(home_module, "_window", None)
    store = FakeStore()
    indexer = FakeIndexer(store)
    settings = SimpleNamespace(api_key="", hotkey="ctrl+shift")

    first = home_module.open_home(store, indexer, settings, lambda: None)
    second = home_module.open_home(store, indexer, settings, lambda: None)

    assert isinstance(first, GeraldWindow)
    assert first is second
    assert first.isVisible()
    assert isinstance(first.current_view, OnboardingWindow)
    onboarding = first.onboarding
    onboarding.name_input.setText("Talal")
    onboarding.finish()
    application.processEvents()
    assert first is home_module.open_home(store, indexer, settings, lambda: None)
    assert first.current_view is first.home_view
    assert first.isVisible()
    assert first.sidebar is first.home_view.sidebar
    assert first.pages is first.home_view.pages
    first.close()
    application.processEvents()


def test_open_home_with_profile_shows_and_reuses_home_window(monkeypatch):
    application = app()
    monkeypatch.setattr(home_module, "_window", None)
    store = seed(FakeStore())
    indexer = FakeIndexer(store)
    settings = SimpleNamespace(api_key="", hotkey="ctrl+shift")

    first = home_module.open_home(store, indexer, settings, lambda: None)
    second = home_module.open_home(store, indexer, settings, lambda: None)

    assert isinstance(first, GeraldWindow)
    assert first is second
    assert isinstance(first.home_view, HomeWindow)
    assert first.current_view is first.home_view
    first.close()
    application.processEvents()


def make_home(*, api_key="test-key", ask_fn=None):
    application = app()
    store = seed(FakeStore())
    indexer = FakeIndexer(store)
    library_changes = []
    settings = SimpleNamespace(
        api_key=api_key,
        hotkey="ctrl+shift",
        model="gpt-test",
    )
    window = HomeWindow(
        store,
        indexer,
        settings,
        lambda: library_changes.append(True),
        ask_fn=ask_fn or fake_ask(store),
    )
    window.show()
    application.processEvents()
    return window, store, indexer, library_changes


def test_navigation_hotkey_and_home_cards():
    application = app()
    window, store, _indexer, _library_changes = make_home()
    maths = store.list_courses()[0]

    assert window.home_page.greeting.text() == "Bonjour Talal"
    assert window.home_page.recent_rows
    assert len(window.home_page.course_cards) == 3
    assert "Ctrl" in [label.text() for label in window.home_page.hotkey_card.findChildren(type(window.home_page.greeting))]

    window.sidebar.nav_buttons["discussions"].click()
    assert window.current_page is window.discussions_page
    window.sidebar.course_buttons[maths.id].click()
    assert window.current_page_key == ("course", maths.id)
    assert window.current_page.title_input.text() == "Maths"
    window.current_page.ask_button.click()
    assert window.current_page.course_id == maths.id
    window.current_page.back_button.click()
    assert window.current_page_key == ("course", maths.id)
    window.sidebar.settings_button.click()
    assert window.current_page is window.settings_page
    window.sidebar.nav_buttons["home"].click()
    assert window.current_page is window.home_page
    window.home_page.ask_button.click()
    assert window.current_page.course_id is None
    window.current_page.back_button.click()
    assert window.current_page is window.home_page

    window.close()
    application.processEvents()


def test_settings_mascot_switch_updates_home_and_chat(monkeypatch, tmp_path):
    monkeypatch.setenv("GERALD_HOME", str(tmp_path))
    application = app()
    window, _store, _indexer, _library_changes = make_home()
    chat = window.open_chat()
    window.open_settings()

    window.settings_page.mascot_tiles["zoe"].click()
    application.processEvents()

    assert window.mascot_id == "zoe"
    assert window.home_page.prof_mascot.mascot_id == "zoe"
    assert "Zoé est prêt" in window.home_page.prof_status.text()
    assert window.settings_page.mascot_tiles["zoe"].property("selected") is True
    assert chat.busy_mascot.mascot_id == "zoe"
    assert chat.busy_label.text() == "Zoé réfléchit…"
    assert load_mascot() == "zoe"

    window.close()
    application.processEvents()


def test_pages_read_dict_backed_engine_records():
    application = app()
    base_store = seed(FakeStore())
    store = DictStore(base_store)
    indexer = FakeIndexer(base_store)
    settings = SimpleNamespace(api_key="test-key", hotkey="ctrl+shift")
    window = HomeWindow(store, indexer, settings, lambda: None)
    window.show()
    application.processEvents()

    course = store.list_courses()[0]
    page = window.open_course(course["id"])
    assert page.title_input.text() == course["title"]
    assert len(page.document_rows) == len(store.list_documents(course["id"]))

    conversation = store.recent_conversations(source="chat")[0]
    window.open_chat(
        conversation_id=conversation["id"],
        course_id=conversation["course_id"],
    )
    chat = window.current_page
    assert chat.title.text() == conversation["title"]
    assert chat.bubble_labels
    assert chat.source_chips

    window.open_settings()
    assert window.settings_page.name_input.text() == "Talal"
    window.close()
    application.processEvents()


def test_fake_library_contract_uses_utc_strings_and_message_source_dicts():
    store = seed(FakeStore())
    timestamps = [
        store.profile.created_at,
        store.list_courses()[0].updated_at,
        store.list_documents(store.list_courses()[0].id)[0].added_at,
        store.recent_conversations()[0].updated_at,
        store.get_messages(store.recent_conversations()[0].id)[0].created_at,
    ]
    assert all(
        isinstance(timestamp, str) and timestamp.endswith("+00:00")
        for timestamp in timestamps
    )
    assert isinstance(
        store.get_messages(store.recent_conversations(source="chat")[0].id)[-1].sources[0],
        dict,
    )

    conversation_id, answer = fake_ask(store)(
        store,
        object(),
        "Question de test",
        None,
        None,
        "test-key",
    )
    assert isinstance(answer, Answer)
    assert isinstance(answer.sources[0], Hit)
    assert isinstance(store.get_messages(conversation_id)[-1].sources[0], dict)


def test_course_title_notes_picker_drop_indexing_and_document_delete(monkeypatch):
    application = app()
    window, store, indexer, library_changes = make_home()
    course = store.list_courses()[0]
    page = window.open_course(course.id)

    page.title_input.setText("Analyse")
    page.title_input.editingFinished.emit()
    assert store.list_courses()[0].title == "Analyse"
    assert window.sidebar.course_buttons[course.id].text() == "Analyse"

    update_count = len(store.calls["update_course"])
    page.notes_input.setPlainText("Notes ajoutées")
    QTest.qWait(180)
    application.processEvents()
    assert len(store.calls["update_course"]) == update_count
    assert wait_until(lambda: store.list_courses()[0].notes == "Notes ajoutées")

    page.drop_zone.files_dropped.emit(["/cours/nouveau.pdf", "/cours/erreur.heic"])
    drop_ids = list(indexer.callbacks)
    assert len(drop_ids) == 2
    assert page.document_rows[drop_ids[0]].status_label.text() == "● Indexation…"
    indexer.finish(drop_ids[0], status="ready", n_chunks=7)
    assert wait_until(lambda: "Prêt · 7 passages" in page.document_rows[drop_ids[0]].status_label.text())
    indexer.finish(drop_ids[1], status="error", error="Format inconnu")
    assert wait_until(lambda: page.document_rows[drop_ids[1]].error_message.text() == "Format inconnu")

    picker_calls = []

    def choose_files(*args):
        picker_calls.append(args)
        return ["/cours/choisi.txt"], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", choose_files)
    page.choose_files()
    assert picker_calls[0][-1] == FILE_FILTER
    assert "Tous les fichiers (*)" in FILE_FILTER
    picker_id = max(indexer.callbacks)
    assert store.documents[picker_id].filename == "choisi.txt"
    page.delete_document(drop_ids[0])
    assert drop_ids[0] not in {document.id for document in store.list_documents(course.id)}
    assert library_changes

    window.close()
    application.processEvents()


def test_course_deletion_requires_confirmation_and_expires():
    application = app()
    window, store, _indexer, _library_changes = make_home()
    course = store.list_courses()[0]
    page = window.open_course(course.id)

    page.confirm_delete()
    assert page.delete_course_button.text() == "Confirmer la suppression"
    page.confirm_delete()
    assert course.id not in {item.id for item in store.list_courses()}
    assert window.current_page is window.home_page

    remaining = store.list_courses()[0]
    page = window.open_course(remaining.id)
    page.confirm_delete()
    page._delete_timer.setInterval(10)
    page._delete_timer.start()
    assert wait_until(lambda: page.delete_course_button.text() == "Supprimer le cours")
    window.close()
    application.processEvents()


def test_discussion_filters_and_agent_read_only():
    application = app()
    window, _store, _indexer, _library_changes = make_home()
    discussions = window.discussions_page

    assert len(discussions.rows) == 3
    discussions.filter_buttons["course"].click()
    assert len(discussions.rows) == 1
    discussions.filter_buttons["agent"].click()
    assert len(discussions.rows) == 2
    discussions.rows[0].clicked.emit()
    assert isinstance(window.current_page, ChatPage)
    assert window.current_page.read_only
    assert window.current_page.footer.isHidden()
    assert not window.current_page.read_only_footer.isHidden()

    window.close()
    application.processEvents()


def test_chat_send_follow_up_sources_and_threaded_error():
    application = app()
    window, store, _indexer, _library_changes = make_home()
    ask_once = window.ask_fn

    def duplicate_sources(*args, **kwargs):
        conversation_id, answer = ask_once(*args, **kwargs)
        return conversation_id, Answer(
            answer.text,
            [*answer.sources, *answer.sources],
        )

    window.ask_fn = duplicate_sources
    chat = window.open_chat(course_id=store.list_courses()[0].id)
    chat.input.setPlainText("Explique les intégrales")
    chat.send()

    assert wait_until(lambda: not chat._busy)
    assert [label.text() for label in chat.bubble_labels][-2:] == [
        "Explique les intégrales",
        "Voici une explication claire.",
    ]
    assert len(chat.source_chips) == 1
    assert chat.source_chips[0].text() == "cours.pdf · p. 3"
    assert chat.source_chips[0].toolTip().startswith("Une source")
    conversation_id = chat.conversation_id
    assert conversation_id is not None
    assert isinstance(store.get_messages(conversation_id)[-1].sources[0], dict)

    chat.input.setPlainText("Et un autre exemple ?")
    chat.send()
    assert wait_until(lambda: not chat._busy)
    calls = store.calls["ask"]
    assert calls[0][0][3] is None
    assert calls[1][0][3] == conversation_id
    assert calls[1][1]["model"] == "gpt-test"
    assert len(chat.source_chips) == 2

    window.close()
    application.processEvents()

    def fail(*_args, **_kwargs):
        raise RuntimeError("connexion indisponible")

    error_window, _store, _indexer, _changes = make_home(ask_fn=fail)
    error_chat = error_window.open_chat()
    error_chat.input.setPlainText("Question")
    error_chat.send()
    assert wait_until(lambda: not error_chat._busy and not error_chat.error_row.isHidden())
    assert "connexion indisponible" in error_chat.error_label.text()
    user_bubbles = len(error_chat.bubble_labels)
    error_chat.retry_button.click()
    assert wait_until(lambda: not error_chat._busy and not error_chat.error_row.isHidden())
    assert len(error_chat.bubble_labels) == user_bubbles
    error_window.close()
    application.processEvents()


def test_chat_answer_without_sources_has_no_source_row():
    application = app()

    def ask_without_sources(
        store,
        _embedder,
        question,
        conversation_id,
        course_id,
        _api_key,
        model=None,
    ):
        store.record(
            "ask",
            store,
            _embedder,
            question,
            conversation_id,
            course_id,
            _api_key,
            model=model,
        )
        if conversation_id is None:
            conversation = store.create_conversation(
                course_id, "chat", question[:80] or "Nouvelle discussion"
            )
            conversation_id = conversation.id
        store.add_message(conversation_id, "user", question)
        store.add_message(conversation_id, "assistant", "Réponse sans source")
        return conversation_id, Answer("Réponse sans source", [])

    window, _store, _indexer, _library_changes = make_home(
        ask_fn=ask_without_sources
    )
    chat = window.open_chat()
    chat.input.setPlainText("Question sans citation")
    chat.send()

    assert wait_until(
        lambda: not chat._busy
        and chat.bubble_labels[-1].text() == "Réponse sans source"
    )
    assert not chat.source_chips
    message_columns = []
    for index in range(chat.messages_layout.count()):
        message_layout = chat.messages_layout.itemAt(index).layout()
        if message_layout is not None:
            message_columns.append(message_layout)
    assert message_columns[-1].count() == 1
    window.close()
    application.processEvents()


def test_chat_bubbles_fit_sixty_character_answers_on_one_line():
    application = app()
    window, _store, _indexer, _library_changes = make_home()
    window.resize(1100, 720)
    application.processEvents()
    chat = window.open_chat()
    application.processEvents()

    answer = "L’intégrale mesure l’aire sous une courbe sur un intervalle."
    assert len(answer) == 60
    chat._append_message("assistant", answer, [])
    chat._append_message("user", answer)
    application.processEvents()

    bubbles = chat.message_bubbles[-2:]
    labels = chat.bubble_labels[-2:]
    line_height = labels[-1].fontMetrics().lineSpacing()
    assert all(label.hasHeightForWidth() for label in labels)
    assert all(
        label.heightForWidth(label.width()) == line_height
        for label in labels
    )
    assert all(
        bubble.height() >= 40
        and 0 < bubble.property("bubbleRadius") <= bubble.height() / 2
        for bubble in bubbles
    )
    assert all(
        bubble.width() <= chat._maximum_bubble_width()
        for bubble in bubbles
    )

    window.close()
    application.processEvents()


def test_chat_without_key_and_enter_shift_enter():
    application = app()
    window, store, _indexer, _changes = make_home(api_key="")
    chat = window.open_chat()
    chat.input.setPlainText("Question")
    chat.send()
    assert not chat.api_key_note.isHidden()
    assert "ask" not in store.calls

    window.settings.api_key = "test-key"
    chat.input.setPlainText("Première ligne")
    chat.input.setFocus()
    QTest.keyClick(chat.input, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert chat.input.document().blockCount() == 2
    chat.input.setPlainText("Envoi avec Entrée")
    QTest.keyClick(chat.input, Qt.Key.Key_Return)
    assert wait_until(lambda: not chat._busy and bool(store.calls.get("ask")))
    window.close()
    application.processEvents()


def test_settings_save_adds_courses_without_deleting_removed_subjects():
    application = app()
    window, store, _indexer, library_changes = make_home()
    settings = window.settings_page
    removed_course = store.list_courses()[0]

    settings.name_input.setText("Talal M.")
    settings.level_chips["Master"].click()
    settings.subject_chips["Maths"].remove_button.click()
    settings.subject_input.setText("Neurosciences")
    QTest.keyClick(settings.subject_input, Qt.Key.Key_Return)
    settings.save_button.click()

    profile = store.get_profile()
    assert profile.name == "Talal M."
    assert profile.level == "Master"
    assert "Neurosciences" in profile.subjects
    assert removed_course.id in {course.id for course in store.list_courses()}
    assert any(course.subject == "Neurosciences" for course in store.list_courses())
    assert settings.saved_label.text() == "Enregistré"
    assert library_changes
    window.close()
    application.processEvents()


def test_relative_dates_and_iso_timestamps():
    now = datetime(2025, 10, 25, 12, tzinfo=timezone.utc)
    now_text = now.isoformat()
    assert as_datetime(now_text).tzinfo is not None
    assert relative_date(now_text, now_text) == "à l'instant"
    assert relative_date((now - timedelta(minutes=5)).isoformat(), now_text) == "il y a 5 min"
    assert relative_date((now - timedelta(hours=2)).isoformat(), now_text) == "il y a 2 h"
    assert relative_date((now - timedelta(days=1)).isoformat(), now_text) == "hier"
    assert relative_date((now - timedelta(days=3)).isoformat(), now_text) == "il y a 3 j"
    assert relative_date("2025-10-12T12:00:00+00:00", now_text) == "12 oct."
    assert relative_date("2024-10-12T12:00:00+00:00", now_text) == "12 oct. 2024"
