from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from copy import deepcopy


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Profile:
    name: str
    level: str | None
    subjects: list[str]
    created_at: str


@dataclass
class Course:
    id: int
    title: str
    subject: str
    notes: str
    created_at: str
    updated_at: str


@dataclass
class Document:
    id: int
    course_id: int
    filename: str
    stored_path: str
    status: str
    error: str | None
    n_chunks: int
    added_at: str


@dataclass
class Conversation:
    id: int
    course_id: int | None
    source: str
    title: str
    created_at: str
    updated_at: str


@dataclass
class Message:
    id: int
    conversation_id: int
    role: str
    text: str
    sources: list[dict] | None
    created_at: str


@dataclass
class Hit:
    course_title: str
    document: str
    page: int | None
    text: str
    score: float


@dataclass
class Answer:
    text: str
    sources: list[Hit]


class FakeStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.profile: Profile | None = None
        self.courses: dict[int, Course] = {}
        self.documents: dict[int, Document] = {}
        self.conversations: dict[int, Conversation] = {}
        self.messages: dict[int, list[Message]] = {}
        self.calls: dict[str, list[tuple[tuple, dict]]] = {}
        self._next_course_id = 1
        self._next_document_id = 1
        self._next_conversation_id = 1
        self._next_message_id = 1

    def record(self, name: str, *args, **kwargs) -> None:
        with self.lock:
            self.calls.setdefault(name, []).append((args, kwargs))

    def get_profile(self) -> Profile | None:
        with self.lock:
            return self.profile

    def save_profile(self, name: str, level: str | None, subjects: list[str]) -> Profile:
        self.record("save_profile", name, level, list(subjects))
        with self.lock:
            if self.profile is None:
                created_at = utc_now()
            else:
                created_at = self.profile.created_at
            self.profile = Profile(name.strip(), level, list(subjects), created_at)
            return self.profile

    def list_courses(self) -> list[Course]:
        with self.lock:
            return list(sorted(self.courses.values(), key=lambda item: item.id))

    def create_course(self, title: str, subject: str) -> Course:
        self.record("create_course", title, subject)
        with self.lock:
            now = utc_now()
            course = Course(self._next_course_id, title, subject, "", now, now)
            self._next_course_id += 1
            self.courses[course.id] = course
            return course

    def update_course(self, course_id: int, *, title=None, notes=None) -> Course:
        self.record("update_course", course_id, title=title, notes=notes)
        with self.lock:
            course = self.courses[course_id]
            if title is not None:
                course.title = title
            if notes is not None:
                course.notes = notes
            course.updated_at = utc_now()
            return course

    def delete_course(self, course_id: int) -> None:
        self.record("delete_course", course_id)
        with self.lock:
            self.courses.pop(course_id, None)
            self.documents = {
                key: value
                for key, value in self.documents.items()
                if value.course_id != course_id
            }
            deleted = [
                key for key, value in self.conversations.items() if value.course_id == course_id
            ]
            for key in deleted:
                self.conversations.pop(key, None)
                self.messages.pop(key, None)

    def list_documents(self, course_id: int) -> list[Document]:
        with self.lock:
            return [
                item
                for item in sorted(self.documents.values(), key=lambda row: row.id)
                if item.course_id == course_id
            ]

    def add_document(
        self,
        course_id: int,
        filename: str,
        *,
        stored_path: str | None = None,
        status: str = "ready",
        error: str | None = None,
        n_chunks: int = 0,
        added_at: str | None = None,
    ) -> Document:
        with self.lock:
            document = Document(
                self._next_document_id,
                course_id,
                filename,
                stored_path or filename,
                status,
                error,
                n_chunks,
                added_at or utc_now(),
            )
            self._next_document_id += 1
            self.documents[document.id] = document
            return document

    def delete_document(self, document_id: int) -> None:
        self.record("delete_document", document_id)
        with self.lock:
            self.documents.pop(document_id, None)

    def recent_conversations(
        self,
        limit: int = 20,
        source: str | None = None,
        course_id: int | None = None,
    ) -> list[Conversation]:
        with self.lock:
            conversations = list(self.conversations.values())
            if source is not None:
                conversations = [item for item in conversations if item.source == source]
            if course_id is not None:
                conversations = [item for item in conversations if item.course_id == course_id]
            conversations.sort(key=lambda item: item.updated_at, reverse=True)
            return conversations[:limit]

    def get_messages(self, conversation_id: int) -> list[Message]:
        with self.lock:
            return list(self.messages.get(conversation_id, []))

    def create_conversation(
        self,
        course_id: int | None,
        source: str,
        title: str,
        *,
        created_at: str | None = None,
    ) -> Conversation:
        with self.lock:
            now = created_at or utc_now()
            conversation = Conversation(
                self._next_conversation_id,
                course_id,
                source,
                title,
                now,
                now,
            )
            self._next_conversation_id += 1
            self.conversations[conversation.id] = conversation
            self.messages[conversation.id] = []
            return conversation

    def add_message(
        self,
        conversation_id: int,
        role: str,
        text: str,
        sources: list[object] | None = None,
        *,
        created_at: str | None = None,
    ) -> Message:
        with self.lock:
            message = Message(
                self._next_message_id,
                conversation_id,
                role,
                text,
                None
                if sources is None
                else [
                    asdict(source) if is_dataclass(source) else deepcopy(source)
                    for source in sources
                ],
                created_at or utc_now(),
            )
            self._next_message_id += 1
            self.messages.setdefault(conversation_id, []).append(message)
            conversation = self.conversations.get(conversation_id)
            if conversation is not None:
                conversation.updated_at = message.created_at
                if role == "user" and conversation.title == "Nouvelle discussion":
                    conversation.title = text[:80]
            return message


class FakeIndexer:
    def __init__(self, store: FakeStore):
        self.store = store
        self.embedder = object()
        self.callbacks: dict[int, object] = {}

    def add_document(self, course_id: int, path: str, on_done=None) -> Document:
        self.store.record("add_document", course_id, path, on_done=on_done)
        document = self.store.add_document(
            course_id,
            Path(path).name,
            stored_path=path,
            status="indexing",
            n_chunks=0,
        )
        self.callbacks[document.id] = on_done
        return document

    def finish(
        self,
        document_id: int,
        status: str = "ready",
        n_chunks: int = 4,
        error: str | None = None,
    ) -> Document:
        with self.store.lock:
            document = self.store.documents[document_id]
            document.status = status
            document.n_chunks = n_chunks
            document.error = error
            callback = self.callbacks.get(document_id)
        if callback is not None:
            worker = threading.Thread(target=callback, args=(document,))
            worker.start()
            worker.join()
        return document


def fake_ask(
    store: FakeStore,
    answer_text: str = "Voici une explication claire.",
    hit: Hit | None = None,
):
    def ask(*args, **kwargs):
        store.record("ask", *args, **kwargs)
        question = kwargs.get("question", args[2] if len(args) > 2 else "")
        conversation_id = kwargs.get(
            "conversation_id", args[3] if len(args) > 3 else None
        )
        course_id = kwargs.get("course_id", args[4] if len(args) > 4 else None)
        result_hit = hit or Hit(
            "Maths",
            "cours.pdf",
            3,
            "Une source de démonstration suffisamment longue pour confirmer la citation.",
            0.92,
        )
        if conversation_id is None or conversation_id not in store.conversations:
            conversation = store.create_conversation(
                course_id, "chat", question[:80] or "Nouvelle discussion"
            )
            conversation_id = conversation.id
        store.add_message(conversation_id, "user", question)
        store.add_message(conversation_id, "assistant", answer_text, [result_hit])
        return conversation_id, Answer(answer_text, [result_hit])

    return ask


def seed(store: FakeStore) -> FakeStore:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    store.profile = Profile(
        "Talal",
        "Licence",
        ["Maths", "Physique-Chimie", "Informatique"],
        now.isoformat(),
    )
    maths = store.create_course("Maths", "Maths")
    physics = store.create_course("Physique-Chimie", "Physique-Chimie")
    coding = store.create_course("Informatique", "Informatique")
    store.update_course(
        maths.id,
        notes="Les intégrales permettent de calculer une aire sous une courbe.",
    )
    store.update_course(
        physics.id,
        notes="Réviser les lois de conservation et les unités.",
    )
    store.update_course(coding.id, notes="Structures de données et algorithmique.")
    store.add_document(
        maths.id,
        "Analyse — chapitre 3.pdf",
        status="ready",
        n_chunks=42,
        added_at=(now - timedelta(days=1)).isoformat(),
    )
    store.add_document(
        maths.id,
        "TD intégrales.docx",
        status="indexing",
        n_chunks=0,
        added_at=(now - timedelta(minutes=12)).isoformat(),
    )
    store.add_document(
        maths.id,
        "scan-tableau.heic",
        status="error",
        error="Format non pris en charge",
        added_at=(now - timedelta(days=4)).isoformat(),
    )
    store.add_document(physics.id, "Mécanique.pdf", status="ready", n_chunks=18)
    store.add_document(coding.id, "Python — bases.md", status="ready", n_chunks=12)
    chat = store.create_conversation(
        maths.id,
        "chat",
        "Comment calculer une intégrale ?",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )
    citation = Hit(
        "Maths",
        "Analyse — chapitre 3.pdf",
        3,
        "Une intégrale définie mesure l'aire algébrique sous une courbe.",
        0.95,
    )
    store.add_message(
        chat.id,
        "user",
        "Comment calculer une intégrale ?",
        created_at=(now - timedelta(hours=2)).isoformat(),
    )
    store.add_message(
        chat.id,
        "assistant",
        "Une intégrale définie mesure l'aire algébrique sous une courbe.",
        [asdict(citation)],
        created_at=(now - timedelta(hours=2) + timedelta(minutes=1)).isoformat(),
    )
    agent = store.create_conversation(
        None,
        "agent",
        "Résumé de la dernière leçon",
        created_at=(now - timedelta(days=3)).isoformat(),
    )
    store.add_message(
        agent.id,
        "assistant",
        "Voici le résumé de ta dernière leçon.",
        created_at=(now - timedelta(days=3)).isoformat(),
    )
    older_agent = store.create_conversation(
        None,
        "agent",
        "Exercices de révision",
        created_at=(now - timedelta(days=8)).isoformat(),
    )
    store.add_message(
        older_agent.id,
        "assistant",
        "Quelques exercices pour réviser.",
        created_at=(now - timedelta(days=8)).isoformat(),
    )
    return store
