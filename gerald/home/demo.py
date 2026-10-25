from __future__ import annotations

from pathlib import Path


def seed_demo(store, indexer) -> None:
    if store.get_profile() is None:
        store.save_profile("", None, ["Maths"])

    courses = store.list_courses()
    course = next((item for item in courses if item.title == "Maths — Second degré"), None)
    if course is None:
        course = store.create_course("Maths — Second degré", "Maths")

    existing = {item.filename for item in store.list_documents(course.id)}
    root = Path(__file__).with_name("demo_docs")
    for path in sorted(root.glob("*.md")):
        if path.name not in existing:
            indexer.add_document(course.id, path)
