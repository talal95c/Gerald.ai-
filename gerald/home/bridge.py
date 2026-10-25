from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from PyQt6.QtCore import QTimer, QUrl, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QTextBrowser, QVBoxLayout

from gerald.home.events import events
from gerald.home.qa import default_ask
from gerald.tools.recap import has_file_association


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
    RECAP_TIMEOUT_S = 60.0

    stateChanged = pyqtSignal(str)
    modeChanged = pyqtSignal(str)
    answer = pyqtSignal(str)
    answerError = pyqtSignal(str)
    focusRequested = pyqtSignal(bool)
    sessionOpenChanged = pyqtSignal(bool)
    recapReady = pyqtSignal(str)
    agentStatus = pyqtSignal(str)
    tdRequested = pyqtSignal()

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
        self._last_exercise: tuple[str, list[str]] | None = None
        self._recap_requested_at: float | None = None
        self._recap_error: str | None = None
        self._clock = time.time
        self._recap_dir = Path.home() / "Gerald" / "lessons"
        self._fallback_board = None
        self._recap_timer = QTimer(self)
        self._recap_timer.setInterval(750)
        self._recap_timer.timeout.connect(self._find_recap)
        events.document_updated.connect(self._document_updated)

    @pyqtSlot(result=str)
    def state(self) -> str:
        hour = datetime.now().hour
        recaps = []
        if self._recap_dir.exists():
            recap_paths = sorted(
                self._recap_dir.glob("*.md"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for path in recap_paths:
                stat = path.stat()
                heading = next(
                    (
                        line.lstrip().lstrip("#").strip()
                        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                        if line.lstrip().startswith("#")
                    ),
                    path.stem,
                )
                recaps.append(
                    {
                        "path": str(path),
                        "title": heading or path.stem,
                        "created_at": datetime.fromtimestamp(stat.st_mtime)
                        .astimezone()
                        .isoformat(),
                    }
                )
        documents = [
            {
                "id": value(document, "id"),
                "filename": value(document, "filename", ""),
                "status": value(document, "status", "ready"),
                "error": value(document, "error"),
                "folder": value(course, "title") or "Mes cours",
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
                "recap_error": self._recap_error,
                "last_exercise": (
                    {"title": self._last_exercise[0], "lines": self._last_exercise[1]}
                    if self._last_exercise is not None
                    else None
                ),
                "recaps": recaps,
            },
            ensure_ascii=False,
        )

    @pyqtSlot(str)
    def setMode(self, mode: str) -> None:
        if mode not in {"greeting", "collapsed", "panel", "settings", "document"}:
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
    def documentText(self, document_id: int) -> str:
        reader = getattr(self.store, "document_text", None)
        return reader(document_id) if reader else ""

    @pyqtSlot(int, result=str)
    def messages(self, conversation_id: int) -> str:
        return json.dumps(
            [
                {
                    "role": value(message, "role", ""),
                    "text": value(message, "text", ""),
                    "created_at": value(message, "created_at", ""),
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
        self._last_exercise = (title, lines)
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
    def openTd(self) -> None:
        self.tdRequested.emit()

    @pyqtSlot()
    def endSession(self) -> None:
        if not self._session_open:
            return
        if self.end_session is None:
            self._recap_timer.stop()
            self._recap_requested_at = None
            self._recap_error = "La fiche n'est pas disponible pour le moment."
            self.stateChanged.emit(self.state())
            return
        result = self.end_session()
        if result is False:
            self._recap_timer.stop()
            self._recap_requested_at = None
            self._recap_error = "Hors ligne : la fiche sera possible une fois Gerald reconnecté."
            self.stateChanged.emit(self.state())
            return
        self._recap_error = None
        self._recap_requested_at = self._clock()
        self._recap_timer.start()
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
            self._recap_error = None
            self._session_open = False
            self.sessionOpenChanged.emit(False)
            self.recapReady.emit(str(max(candidates, key=lambda path: path.stat().st_mtime)))
            self.stateChanged.emit(self.state())
        elif self._clock() - self._recap_requested_at > self.RECAP_TIMEOUT_S:
            self._recap_timer.stop()
            self._recap_requested_at = None
            self._recap_error = "La fiche n'a pas pu être générée. Réessaie."
            self.stateChanged.emit(self.state())

    @pyqtSlot(str)
    def openRecap(self, path: str) -> None:
        if os.name == "nt":
            if has_file_association(Path(path).suffix):
                try:
                    os.startfile(path)
                    return
                except OSError:
                    pass
            try:
                subprocess.Popen(["notepad.exe", path])
                return
            except OSError:
                pass
        elif QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            return
        self._show_recap_in_app(path)

    def _show_recap_in_app(self, path: str) -> None:
        dialog = QDialog()
        dialog.setWindowTitle(Path(path).stem)
        dialog.resize(720, 640)
        browser = QTextBrowser(dialog)
        browser.setMarkdown(Path(path).read_text(encoding="utf-8"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(browser)
        dialog.exec()

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
