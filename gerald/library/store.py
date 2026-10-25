from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Profile:
    name: str
    level: str | None
    subjects: list[str]
    created_at: str


@dataclass(frozen=True)
class Course:
    id: int
    title: str
    subject: str
    notes: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Document:
    id: int
    course_id: int
    filename: str
    stored_path: str
    status: str
    error: str | None
    n_chunks: int
    added_at: str


@dataclass(frozen=True)
class Conversation:
    id: int
    course_id: int | None
    source: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: int
    conversation_id: int
    role: str
    text: str
    sources: list[dict] | None
    created_at: str


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, home: Path | None = None) -> None:
        configured_home = home or os.getenv("GERALD_HOME")
        self.home = Path(configured_home).expanduser() if configured_home else Path.home() / ".gerald"
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "documents").mkdir(parents=True, exist_ok=True)
        self.database_path = self.home / "gerald.db"
        self._lock = threading.Lock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self._lock:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    name TEXT NOT NULL,
                    level TEXT,
                    subjects TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('indexing', 'ready', 'error')),
                    error TEXT,
                    n_chunks INTEGER NOT NULL DEFAULT 0,
                    added_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    ord INTEGER NOT NULL,
                    page INTEGER,
                    text TEXT NOT NULL,
                    embedding BLOB
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
                    source TEXT NOT NULL CHECK (source IN ('chat', 'agent')),
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    text TEXT NOT NULL,
                    sources TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            self.connection.commit()

    @staticmethod
    def _profile(row: sqlite3.Row | None) -> Profile | None:
        if row is None:
            return None
        return Profile(
            row["name"],
            row["level"],
            json.loads(row["subjects"]),
            row["created_at"],
        )

    @staticmethod
    def _course(row: sqlite3.Row | None) -> Course | None:
        if row is None:
            return None
        return Course(
            row["id"],
            row["title"],
            row["subject"],
            row["notes"],
            row["created_at"],
            row["updated_at"],
        )

    @staticmethod
    def _document(row: sqlite3.Row | None) -> Document | None:
        if row is None:
            return None
        return Document(
            row["id"],
            row["course_id"],
            row["filename"],
            row["stored_path"],
            row["status"],
            row["error"],
            row["n_chunks"],
            row["added_at"],
        )

    @staticmethod
    def _conversation(row: sqlite3.Row | None) -> Conversation | None:
        if row is None:
            return None
        return Conversation(
            row["id"],
            row["course_id"],
            row["source"],
            row["title"],
            row["created_at"],
            row["updated_at"],
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> Message:
        sources = json.loads(row["sources"]) if row["sources"] is not None else None
        return Message(
            row["id"],
            row["conversation_id"],
            row["role"],
            row["text"],
            sources,
            row["created_at"],
        )

    def get_profile(self) -> Profile | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return self._profile(row)

    def save_profile(self, name: str, level: str | None, subjects: list[str]) -> Profile:
        now = _timestamp()
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO profile (id, name, level, subjects, created_at)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    level = excluded.level,
                    subjects = excluded.subjects
                """,
                (name.strip(), level, json.dumps(subjects, ensure_ascii=False), now),
            )
            self.connection.commit()
            row = self.connection.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return self._profile(row)  # type: ignore[return-value]

    def list_courses(self) -> list[Course]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM courses ORDER BY updated_at DESC, id"
            ).fetchall()
        return [self._course(row) for row in rows]  # type: ignore[misc]

    def get_course(self, course_id: int) -> Course | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM courses WHERE id = ?",
                (course_id,),
            ).fetchone()
        return self._course(row)

    def create_course(self, title: str, subject: str) -> Course:
        now = _timestamp()
        with self._lock:
            cursor = self.connection.execute(
                "INSERT INTO courses (title, subject, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title.strip(), subject.strip(), now, now),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM courses WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._course(row)  # type: ignore[return-value]

    def update_course(
        self,
        course_id: int,
        *,
        title: str | None = None,
        notes: str | None = None,
    ) -> Course | None:
        updates = []
        values: list[str | int] = []
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if notes is not None:
            updates.append("notes = ?")
            values.append(notes)
        with self._lock:
            if updates:
                updates.append("updated_at = ?")
                values.extend((_timestamp(), course_id))
                self.connection.execute(
                    f"UPDATE courses SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
                self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM courses WHERE id = ?",
                (course_id,),
            ).fetchone()
        return self._course(row)

    def delete_course(self, course_id: int) -> None:
        with self._lock:
            rows = self.connection.execute(
                "SELECT stored_path FROM documents WHERE course_id = ?",
                (course_id,),
            ).fetchall()
            self.connection.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            self.connection.commit()
        self._remove_files(row["stored_path"] for row in rows)
        try:
            (self.home / "documents" / str(course_id)).rmdir()
        except OSError:
            pass

    def list_documents(self, course_id: int) -> list[Document]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM documents WHERE course_id = ? ORDER BY added_at DESC, id DESC",
                (course_id,),
            ).fetchall()
        return [self._document(row) for row in rows]  # type: ignore[misc]

    def _create_document(self, course_id: int, filename: str) -> Document:
        safe_name = Path(filename).name or "document"
        directory = self.home / "documents" / str(course_id)
        directory.mkdir(parents=True, exist_ok=True)
        with self._lock:
            reserved = {
                row["stored_path"]
                for row in self.connection.execute(
                    "SELECT stored_path FROM documents WHERE course_id = ?",
                    (course_id,),
                ).fetchall()
            }
            stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
            candidate = directory / safe_name
            suffix_number = 2
            while str(candidate) in reserved or candidate.exists():
                candidate = directory / f"{stem} ({suffix_number}){suffix}"
                suffix_number += 1
            now = _timestamp()
            cursor = self.connection.execute(
                """
                INSERT INTO documents
                    (course_id, filename, stored_path, status, added_at)
                VALUES (?, ?, ?, 'indexing', ?)
                """,
                (course_id, candidate.name, str(candidate), now),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._document(row)  # type: ignore[return-value]

    def get_document(self, document_id: int) -> Document | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return self._document(row)

    def _finish_document(
        self,
        document_id: int,
        *,
        status: str,
        error: str | None,
        n_chunks: int,
    ) -> Document | None:
        with self._lock:
            self.connection.execute(
                "UPDATE documents SET status = ?, error = ?, n_chunks = ? WHERE id = ?",
                (status, error, n_chunks, document_id),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
        return self._document(row)

    def _replace_chunks(
        self,
        document_id: int,
        chunks: list[tuple[int | None, str, bytes | None]],
    ) -> None:
        with self._lock:
            self.connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            self.connection.executemany(
                """
                INSERT INTO chunks (document_id, ord, page, text, embedding)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (document_id, order, page, text, embedding)
                    for order, (page, text, embedding) in enumerate(chunks)
                ],
            )
            self.connection.commit()

    def delete_document(self, document_id: int) -> None:
        with self._lock:
            row = self.connection.execute(
                "SELECT stored_path FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            self.connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            self.connection.commit()
        if row is not None:
            self._remove_files([row["stored_path"]])

    def _remove_files(self, paths) -> None:
        document_root = (self.home / "documents").resolve()
        for stored_path in paths:
            try:
                path = Path(stored_path).resolve()
                if path != document_root and document_root in path.parents:
                    path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove an imported document")

    def _search_chunks(self, course_id: int | None = None) -> list[sqlite3.Row]:
        query = """
            SELECT chunks.page, chunks.text, chunks.embedding,
                   documents.filename, courses.title AS course_title
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            JOIN courses ON courses.id = documents.course_id
            WHERE documents.status = 'ready'
        """
        values: tuple[int, ...] = ()
        if course_id is not None:
            query += " AND courses.id = ?"
            values = (course_id,)
        query += " ORDER BY chunks.id"
        with self._lock:
            return self.connection.execute(query, values).fetchall()

    def create_conversation(
        self,
        course_id: int | None,
        source: str,
        title: str,
    ) -> Conversation:
        now = _timestamp()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO conversations (course_id, source, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (course_id, source, title, now, now),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._conversation(row)  # type: ignore[return-value]

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return self._conversation(row)

    def update_conversation(self, conversation_id: int, *, title: str | None = None) -> None:
        with self._lock:
            if title is None:
                self.connection.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (_timestamp(), conversation_id),
                )
            else:
                self.connection.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title, _timestamp(), conversation_id),
                )
            self.connection.commit()

    def add_message(
        self,
        conversation_id: int,
        role: str,
        text: str,
        sources: list[dict] | None = None,
    ) -> Message:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        created_at = _timestamp()
        with self._lock:
            cursor = self.connection.execute(
                """
                INSERT INTO messages (conversation_id, role, text, sources, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    text,
                    json.dumps(sources, ensure_ascii=False) if sources is not None else None,
                    created_at,
                ),
            )
            self.connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (created_at, conversation_id),
            )
            self.connection.commit()
            row = self.connection.execute(
                "SELECT * FROM messages WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._message(row)

    def get_messages(self, conversation_id: int) -> list[Message]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        return [self._message(row) for row in rows]

    def recent_conversations(
        self,
        limit: int = 20,
        source: str | None = None,
        course_id: int | None = None,
    ) -> list[Conversation]:
        query = "SELECT * FROM conversations WHERE 1 = 1"
        values: list[int | str] = []
        if source is not None:
            query += " AND source = ?"
            values.append(source)
        if course_id is not None:
            query += " AND course_id = ?"
            values.append(course_id)
        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        values.append(max(0, int(limit)))
        with self._lock:
            rows = self.connection.execute(query, values).fetchall()
        return [self._conversation(row) for row in rows]  # type: ignore[misc]

    def close(self) -> None:
        with self._lock:
            self.connection.close()
