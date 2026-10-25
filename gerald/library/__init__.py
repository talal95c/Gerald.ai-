from __future__ import annotations

from dataclasses import asdict

from gerald.library.embeddings import OpenAIEmbedder
from gerald.library.ingest import Indexer, chunk_pages, extract_text
from gerald.library.qa import Answer, answer
from gerald.library.search import Hit, search
from gerald.library.store import Conversation, Course, Document, Message, Profile, Store


def ask(
    store: Store,
    embedder,
    question: str,
    conversation_id: int | None,
    course_id: int | None,
    api_key: str,
    model: str | None = None,
) -> tuple[int, Answer]:
    title = question.strip()[:60]
    if conversation_id is None:
        conversation = store.create_conversation(course_id, "chat", title)
    else:
        conversation = store.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError("conversation does not exist")
        if conversation.source != "chat":
            raise ValueError("only course chat conversations can be continued here")
    history = [
        {"role": message.role, "text": message.text}
        for message in store.get_messages(conversation.id)[-10:]
    ]
    hits = search(store, question, embedder, course_id=course_id, k=5)
    result = answer(question, hits, history, store.get_profile(), api_key, model)
    store.add_message(conversation.id, "user", question)
    store.add_message(
        conversation.id,
        "assistant",
        result.text,
        [asdict(hit) for hit in result.sources],
    )
    return conversation.id, result


__all__ = [
    "Answer",
    "Conversation",
    "Course",
    "Document",
    "Hit",
    "Indexer",
    "Message",
    "OpenAIEmbedder",
    "Profile",
    "Store",
    "answer",
    "ask",
    "chunk_pages",
    "extract_text",
    "search",
]
