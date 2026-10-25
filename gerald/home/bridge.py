from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading

from PyQt6.QtCore import QTimer, QUrl, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QFileDialog

from gerald.home.events import events
from gerald.home.qa import default_ask


def value(item, name: str, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def greeting_for_hour(hour: int) -> str:
    if 5 <= hour < 12:
        return "Bonjour."
    if 12 <= hour < 18:
        return "Bon après-midi."
    return "Bonsoir."


def json_sources(sources) -> list[dict]:
    result = []
    for source in sources or []:
        if isinstance(source, dict):
            result.append(source)
        else:
            result.append(
                {
                    key: value(source, key)
                    for key in ("course_title", "document", "page", "text", "score")
                    if value(source, key) is not None
                }
            )
    return result


class Bridge(QObject):
    stateChanged = pyqtSignal(str)
    modeChanged = pyqtSignal(str)
    answer = pyqtSignal(str)
    answerError = pyqtSignal(str)
    focusRequested = pyqtSignal(bool)
    sessionOpenChanged = pyqtSignal(bool)
    recapReady = pyqtSignal(str)
    agentStatus = pyqtSignal(str)

    def __init__(
        self, store, indexer, settings, *, ask_fn=None, open_board=None, end_session=None, on_library_changed=None
    ):
        super().__init__()
        self.store = store
        self.indexer = indexer
        self.settings = settings
        self.ask_fn = ask_fn or default_ask
        self.open_board = open_board
        self.end_session = end_session
        self.on_library_changed = on_library_changed
        self.mode = "greeting"
        self._session_open = False
        self._recap_requested_at: float | None = None
        self._recap_dir = Path.home() / "Gerald" / "lessons"
        self._fallback_board = None
        self._recap_timer = QTimer(self)
        self._recap_timer.setInterval(750)
        self._recap_timer.timeout.connect(self._find_recap)
        events.document_updated.connect(self._document_updated)

    @pyqtSlot(result=str)
    def state(self) -> str:
        hour = datetime.now().hour
        documents = [
            {
                "id": value(document, "id"),
                "filename": value(document, "filename", ""),
                "status": value(document, "status", "ready"),
                "error": value(document, "error"),
            }
            for course in self.store.list_courses()
            for document in self.store.list_documents(value(course, "id"))
        ]
        conversations = [
            {
                "id": value(item, "id"),
                "title": value(item, "title", ""),
                "source": value(item, "source", "chat"),
                "updated_at": value(item, "updated_at", ""),
            }
            for item in self.store.recent_conversations()
        ]
        return json.dumps(
            {
                "greeting": greeting_for_hour(hour),
                "hotkey_label": str(getattr(self.settings, "hotkey", "ctrl+shift")).replace(
                    "+", " + "
                ).upper(),
                "documents": documents,
                "conversations": conversations,
                "session_open": self._session_open,
                "recap_pending": self._recap_requested_at is not None,
            },
            ensure_ascii=False,
        )

    @pyqtSlot(str)
    def setMode(self, mode: str) -> None:
        if mode not in {"greeting", "collapsed", "panel", "settings"}:
            return
        self.mode = mode
        self.modeChanged.emit(mode)

    @pyqtSlot(str)
    def ask(self, question: str) -> None:
        question = question.strip()
        if not question:
            return

        def run() -> None:
            try:
                result = self.ask_fn(
                    self.store,
                    getattr(self.indexer, "embedder", None),
                    question,
                    None,
                    None,
                    getattr(self.settings, "api_key", ""),
                    model=None,
                )
                conversation_id, answer = result
                self.answer.emit(
                    json.dumps(
                        {
                            "text": value(answer, "text", ""),
                            "sources": json_sources(value(answer, "sources", [])),
                            "conversation_id": conversation_id,
                        },
                        ensure_ascii=False,
                    )
                )
                self.stateChanged.emit(self.state())
            except Exception as error:
                self.answerError.emit(str(error) or "Une erreur est survenue.")

        threading.Thread(target=run, name="gerald-home-ask", daemon=True).start()

    @pyqtSlot(int, result=str)
    def messages(self, conversation_id: int) -> str:
        return json.dumps(
            [
                {
                    "role": value(message, "role", ""),
                    "text": value(message, "text", ""),
                    "sources": json_sources(value(message, "sources")),
                }
                for message in self.store.get_messages(conversation_id)
            ],
            ensure_ascii=False,
        )

    @pyqtSlot()
    def addDocuments(self) -> None:
        courses = self.store.list_courses()
        if not courses:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            None, "Ajouter des documents", "", "Documents (*.pdf *.docx *.md *.txt)"
        )
        for path in paths:
            self.indexer.add_document(value(courses[0], "id"), path, events.on_done)

    @pyqtSlot(int)
    def deleteDocument(self, document_id: int) -> None:
        self.store.delete_document(document_id)
        self.stateChanged.emit(self.state())

    @pyqtSlot(str, str)
    def openBoard(self, title: str, lines_json: str) -> None:
        try:
            lines = json.loads(lines_json)
        except (TypeError, json.JSONDecodeError):
            lines = []
        if not isinstance(lines, list):
            lines = []
        lines = [str(line) for line in lines]
        if self.open_board is not None:
            self.open_board(title, lines)
        else:
            from gerald.board import BoardWindow

            if self._fallback_board is None:
                self._fallback_board = BoardWindow()
            self._fallback_board.set_exercise(title, lines)
            screen = QApplication.primaryScreen()
            if screen is not None:
                self._fallback_board.open_on_screen(screen)
        self._session_open = True
        self.sessionOpenChanged.emit(True)
        self.stateChanged.emit(self.state())

    @pyqtSlot()
    def endSession(self) -> None:
        if not self._session_open:
            return
        self._recap_requested_at = datetime.now().timestamp()
        self._recap_timer.start()
        if self.end_session is not None:
            self.end_session()
        self.stateChanged.emit(self.state())

    def _find_recap(self) -> None:
        if self._recap_requested_at is None:
            return
        candidates = [
            path
            for path in self._recap_dir.glob("*.md")
            if path.stat().st_mtime >= self._recap_requested_at
        ] if self._recap_dir.exists() else []
        if candidates:
            self._recap_timer.stop()
            self._recap_requested_at = None
            self._session_open = False
            self.sessionOpenChanged.emit(False)
            self.recapReady.emit(str(max(candidates, key=lambda path: path.stat().st_mtime)))
            self.stateChanged.emit(self.state())

    @pyqtSlot(str)
    def openRecap(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @pyqtSlot(bool)
    def requestFocus(self, requested: bool) -> None:
        self.focusRequested.emit(requested)

    def set_agent_status(self, status: str) -> None:
        self.agentStatus.emit(status)

    @pyqtSlot()
    def quit(self) -> None:
        QApplication.quit()

    def _document_updated(self, _document) -> None:
        if self.on_library_changed is not None:
            self.on_library_changed()
        self.stateChanged.emit(self.state())
