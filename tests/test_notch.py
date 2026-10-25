from __future__ import annotations

import json
import os
import threading
import time
from types import SimpleNamespace

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from gerald.home.bridge import Bridge, greeting_for_hour
from gerald.home.demo import seed_demo
from gerald.home.events import events
from fakes_library import FakeIndexer, FakeStore


class EmptyStore:
    def list_courses(self):
        return []

    def list_documents(self, _course_id):
        return []

    def recent_conversations(self):
        return []


def test_greeting_changes_with_local_time():
    assert greeting_for_hour(8) == "Bonjour."
    assert greeting_for_hour(14) == "Bon après-midi."
    assert greeting_for_hour(22) == "Bonsoir."


def test_bridge_ask_emits_answer_without_sources(qapplication):
    bridge = Bridge(
        EmptyStore(),
        SimpleNamespace(embedder=object()),
        SimpleNamespace(api_key="demo"),
        ask_fn=lambda *_args, **_kwargs: (
            7,
            SimpleNamespace(text="La réponse est 42.", sources=[]),
        ),
    )
    received = []
    bridge.answer.connect(received.append)

    bridge.ask("Combien vaut 6 × 7 ?")

    deadline = time.monotonic() + 2
    while not received and time.monotonic() < deadline:
        QTest.qWait(10)
    assert len(received) == 1
    payload = json.loads(received[0])
    assert payload["text"] == "La réponse est 42."
    assert payload["sources"] == []
    assert payload["conversation_id"] == 7


def test_bridge_open_board_passes_exercise_and_tracks_session():
    opened = []
    bridge = Bridge(EmptyStore(), object(), object(), open_board=lambda *args: opened.append(args))

    bridge.openBoard("Exercice 2", '["Résous x² − 1 = 0"]')

    assert opened == [("Exercice 2", ["Résous x² − 1 = 0"])]
    assert bridge._session_open


def test_bridge_state_tracks_last_opened_exercise():
    bridge = Bridge(EmptyStore(), object(), object(), open_board=lambda _title, _lines: None)
    assert json.loads(bridge.state())["last_exercise"] is None

    bridge.openBoard("Exercice 2", '["a"]')

    assert json.loads(bridge.state())["last_exercise"] == {
        "title": "Exercice 2",
        "lines": ["a"],
    }


def test_bridge_state_lists_recaps_newest_first(tmp_path):
    bridge = Bridge(EmptyStore(), object(), object())
    bridge._recap_dir = tmp_path
    older = tmp_path / "ancienne.md"
    older.write_text("Texte\n# Ancienne révision", encoding="utf-8")
    newer = tmp_path / "fiche-du-jour.md"
    newer.write_text("# Polynômes du second degré", encoding="utf-8")
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    recaps = json.loads(bridge.state())["recaps"]

    assert [recap["path"] for recap in recaps] == [str(newer), str(older)]
    assert [recap["title"] for recap in recaps] == [
        "Polynômes du second degré",
        "Ancienne révision",
    ]
    assert all(recap["created_at"] for recap in recaps)


def test_bridge_messages_include_created_at():
    store = EmptyStore()
    store.get_messages = lambda _conversation_id: [
        SimpleNamespace(
            role="assistant",
            text="Une réponse.",
            sources=[],
            created_at="2025-10-25T10:30:00+00:00",
        )
    ]
    bridge = Bridge(store, object(), object())

    assert json.loads(bridge.messages(7))[0]["created_at"] == "2025-10-25T10:30:00+00:00"


def test_document_mode_resizes_notch_window(qapplication):
    from gerald.home.notch import NotchWindow

    bridge = Bridge(EmptyStore(), object(), object())
    modes = []
    bridge.modeChanged.connect(modes.append)

    bridge.setMode("document")

    assert modes == ["document"]
    assert NotchWindow.sizes["document"] == (1100, 760)


def test_bridge_open_td_emits_request():
    bridge = Bridge(EmptyStore(), object(), object())
    requested = []
    bridge.tdRequested.connect(lambda: requested.append(True))

    bridge.openTd()

    assert requested == [True]


def test_seed_demo_is_idempotent(monkeypatch):
    monkeypatch.delenv("GERALD_DEMO", raising=False)
    store = FakeStore()
    indexer = FakeIndexer(store)

    seed_demo(store, indexer)
    seed_demo(store, indexer)

    assert store.get_profile() is None
    assert [course.title for course in store.list_courses()] == ["Maths — Second degré"]
    documents = store.list_documents(store.list_courses()[0].id)
    assert len(documents) == 4
    assert len(store.calls["add_document"]) == 4


def test_seed_demo_skips_store_with_existing_course():
    store = FakeStore()
    store.create_course("Cours existant", "Histoire")

    seed_demo(store, FakeIndexer(store))

    assert [course.title for course in store.list_courses()] == ["Cours existant"]
    assert not store.calls.get("add_document")


def test_seed_demo_skips_store_with_profile():
    store = FakeStore()
    store.save_profile("Ada", "Lycée", ["Maths"])

    seed_demo(store, FakeIndexer(store))

    assert store.get_profile().name == "Ada"
    assert not store.list_courses()
    assert not store.calls.get("add_document")


def test_seed_demo_can_be_disabled_with_environment(monkeypatch):
    monkeypatch.setenv("GERALD_DEMO", "0")
    store = FakeStore()

    seed_demo(store, FakeIndexer(store))

    assert store.get_profile() is None
    assert not store.list_courses()
    assert not store.calls.get("create_course")
    assert not store.calls.get("add_document")


def test_end_session_discovers_recap_and_closes_session(tmp_path):
    bridge = Bridge(EmptyStore(), object(), object())
    bridge._recap_dir = tmp_path
    bridge._session_open = True
    bridge._recap_error = "ancienne erreur"
    bridge._recap_requested_at = bridge._clock() - 1
    recap = tmp_path / "fiche.md"
    recap.write_text("# Révision", encoding="utf-8")
    received = []
    bridge.recapReady.connect(received.append)

    bridge._find_recap()

    assert received == [str(recap)]
    assert not bridge._session_open
    assert json.loads(bridge.state())["recap_error"] is None


def test_end_session_offline_callback_keeps_session_open():
    bridge = Bridge(EmptyStore(), object(), object(), end_session=lambda: False)
    bridge._session_open = True

    bridge.endSession()

    state = json.loads(bridge.state())
    assert state["recap_error"] == "Hors ligne : la fiche sera possible une fois Gerald reconnecté."
    assert state["session_open"]
    assert not state["recap_pending"]
    assert not bridge._recap_timer.isActive()


def test_end_session_without_callback_reports_recap_unavailable():
    bridge = Bridge(EmptyStore(), object(), object())
    bridge._session_open = True

    bridge.endSession()

    state = json.loads(bridge.state())
    assert state["recap_error"] == "La fiche n'est pas disponible pour le moment."
    assert state["session_open"]
    assert not state["recap_pending"]
    assert not bridge._recap_timer.isActive()


def test_end_session_timeout_can_be_retried(tmp_path):
    now = [100.0]
    bridge = Bridge(EmptyStore(), object(), object(), end_session=lambda: True)
    bridge._recap_dir = tmp_path
    bridge._clock = lambda: now[0]
    bridge._session_open = True

    bridge.endSession()
    now[0] += Bridge.RECAP_TIMEOUT_S + 0.1
    bridge._find_recap()

    state = json.loads(bridge.state())
    assert not state["recap_pending"]
    assert state["recap_error"] == "La fiche n'a pas pu être générée. Réessaie."
    assert state["session_open"]
    assert not bridge._recap_timer.isActive()

    bridge.endSession()

    assert json.loads(bridge.state())["recap_error"] is None


def test_document_completion_from_worker_thread_updates_state(qapplication):
    bridge = Bridge(EmptyStore(), object(), object())
    updates = []
    bridge.stateChanged.connect(updates.append)

    worker = threading.Thread(target=lambda: events.on_done(object()))
    worker.start()
    worker.join()
    QTest.qWait(20)

    assert updates


def test_open_home_returns_a_stable_cached_widget(qapplication, monkeypatch):
    import gerald.home as home
    import gerald.home.demo as demo
    import gerald.home.notch as notch

    class FakeNotch(QWidget):
        def __init__(self, _bridge):
            super().__init__()

    class FakeTd(QWidget):
        def __init__(self, _bridge):
            super().__init__()

        def show_td(self):
            self.show()

    monkeypatch.setattr(home, "_window", None)
    monkeypatch.setattr(home, "_td_window", None)
    monkeypatch.setattr(demo, "seed_demo", lambda *_args: None)
    monkeypatch.setattr(notch, "NotchWindow", FakeNotch)
    monkeypatch.setattr(notch, "TdWindow", FakeTd)

    first = home.open_home(object(), object(), object(), lambda: None)
    second = home.open_home(object(), object(), object(), lambda: None)

    assert first is second
    first.close()
    home._td_window.close()


def test_notch_activation_waits_for_explicit_focus_request(qapplication, monkeypatch):
    import gerald.home.notch as notch

    class FakeSurface(QWidget):
        def __init__(self, _bridge, _file, parent=None):
            super().__init__(parent)

    monkeypatch.setattr(notch, "_WebSurface", FakeSurface)
    window = notch.NotchWindow(Bridge(EmptyStore(), object(), object()))
    activated = []
    monkeypatch.setattr(QWidget, "activateWindow", lambda self: activated.append(self))

    window.activateWindow()
    assert activated == []

    window._focus_requested = True
    window.activateWindow()
    assert activated == [window]
    window.close()
