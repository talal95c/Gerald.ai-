# Library API

The local library is a Qt-free data and learning layer. Its public API is
exported from `gerald.library`.

## Store

```python
Store(home: Path | None = None)
```

Opens `{home}/gerald.db`; `GERALD_HOME` or `~/.gerald` is used when `home` is
omitted. SQLite access uses one `check_same_thread=False` connection protected
by a lock. Schema setup is idempotent.

```python
get_profile() -> Profile | None
save_profile(name, level, subjects) -> Profile
list_courses() -> list[Course]
create_course(title, subject) -> Course
update_course(course_id, *, title=None, notes=None) -> Course | None
delete_course(id) -> None
list_documents(course_id) -> list[Document]
delete_document(id) -> None
recent_conversations(limit=20, source=None, course_id=None) -> list[Conversation]
get_messages(conversation_id) -> list[Message]
```

Imported documents are copied under `documents/{course_id}/`; duplicate
filenames receive a numeric suffix. Deleting a course or document also removes
its imported file. Course deletion cascades to documents and chunks and clears
the course association from conversations.

## Ingestion and retrieval

```python
extract_text(path) -> list[tuple[int | None, str]]
chunk_pages(pages, size=1200, overlap=200) -> list[tuple[int | None, str]]
OpenAIEmbedder(api_key, model="text-embedding-3-small")
search(store, query, embedder, course_id=None, k=5) -> list[Hit]
```

PDF pages retain their 1-based page number; other supported formats use
`None`. The indexer copies, extracts, chunks and embeds in batches of 64.
Search may return fewer than `k`; keyword-only search drops chunks with no overlap.

```python
Indexer(store, embedder)
Indexer.add_document(course_id, path, on_done=None) -> Document
```

`add_document` returns the `indexing` row immediately. `on_done(Document)` runs
on an indexer worker thread after the row reaches `ready` or `error`. UI
callbacks must marshal updates to the Qt thread. Embedding failures leave
chunks searchable by keyword with `embedding = NULL`.

## Q&A and conversations

```python
answer(question, hits, history, profile, api_key, model=None) -> Answer
ask(store, embedder, question, conversation_id, course_id, api_key, model=None)
    -> tuple[int, Answer]
```

`ask` creates a `chat` conversation when needed, searches up to five passages,
includes at most ten prior messages, and persists the user and assistant
messages with cited-source metadata. Network calls are synchronous; callers
should invoke `ask` off the UI thread and marshal results back to Qt.

## Row types

The public row dataclasses are `Profile`, `Course`, `Document`, `Conversation`,
`Message`, `Hit` and `Answer`. `Answer.sources` contains only passages cited in
the returned answer.
