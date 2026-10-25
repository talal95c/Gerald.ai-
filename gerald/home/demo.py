from __future__ import annotations

import os
from pathlib import Path


def seed_demo(store, indexer) -> None:
    if os.getenv("GERALD_DEMO", "").strip().lower() in {"0", "false", "off"}:
        return
    if store.get_profile() is not None or store.list_courses():
        return

    course = store.create_course("Maths — Second degré", "Maths")

    existing = {item.filename for item in store.list_documents(course.id)}
    root = Path(__file__).with_name("demo_docs")
    for path in sorted(root.glob("*.md")):
        if path.name not in existing:
            indexer.add_document(course.id, path)
