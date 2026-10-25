from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

import numpy as np

from gerald.library.store import Store


@dataclass(frozen=True)
class Hit:
    course_title: str
    document: str
    page: int | None
    text: str
    score: float


def _tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(character for character in normalized if not unicodedata.combining(character))
    return set(re.findall(r"[^\W_]+", unaccented, flags=re.UNICODE))


def _keyword_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & _tokens(text)) / len(query_tokens)


def _query_embedding(embedder, query: str) -> np.ndarray | None:
    if embedder is None:
        return None
    try:
        vectors = np.asarray(embedder.embed([query]), dtype=np.float32)
        if vectors.ndim == 2 and len(vectors) == 1 and vectors.shape[1] > 0:
            return vectors[0]
    except Exception:
        return None
    return None


def search(
    store: Store,
    query: str,
    embedder,
    course_id: int | None = None,
    k: int = 5,
) -> list[Hit]:
    if k <= 0 or not query.strip():
        return []
    rows = store._search_chunks(course_id)
    if not rows:
        return []
    query_tokens = _tokens(query)
    query_vector = _query_embedding(embedder, query)
    hits = []
    for row in rows:
        keyword = _keyword_score(query_tokens, row["text"])
        score = keyword
        embedding_usable = False
        blob = row["embedding"]
        if query_vector is not None and blob is not None:
            vector = np.frombuffer(blob, dtype=np.float32)
            if vector.size == query_vector.size:
                embedding_usable = True
                denominator = float(np.linalg.norm(vector) * np.linalg.norm(query_vector))
                cosine = float(np.dot(vector, query_vector) / denominator) if denominator else 0.0
                score = 0.7 * ((cosine + 1.0) / 2.0) + 0.3 * keyword
        if keyword <= 0 and not embedding_usable:
            continue
        hits.append(
            Hit(
                row["course_title"],
                row["filename"],
                row["page"],
                row["text"],
                score,
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.document.casefold(), hit.page or 0))
    return hits[:k]
