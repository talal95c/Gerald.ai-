from __future__ import annotations

from gerald.library.search import search
from gerald.library.store import Store


def profile_block(store: Store) -> str:
    profile = store.get_profile()
    courses = store.list_courses()
    lines = ["PROFIL DE L'ÉLÈVE"]
    if profile is None:
        lines.append("Profil non renseigné.")
    else:
        lines.append(f"Nom : {profile.name}")
        if profile.level:
            lines.append(f"Niveau : {profile.level}")
        if profile.subjects:
            lines.append(f"Matières : {', '.join(profile.subjects)}")
    lines.append("Cours :")
    if not courses:
        lines.append("- Aucun cours")
    else:
        for course in courses:
            count = len(store.list_documents(course.id))
            lines.append(f"- {course.title} ({course.subject}) — {count} document(s)")
    return "\n".join(lines)


def course_search_results(
    store: Store,
    embedder,
    query: str,
    course: str | None = None,
) -> dict:
    course_id = None
    if course:
        matched_course = next(
            (
                item
                for item in store.list_courses()
                if item.title.casefold() == course.strip().casefold()
            ),
            None,
        )
        if matched_course is None:
            return {"ok": True, "results": []}
        course_id = matched_course.id
    hits = search(store, query, embedder, course_id=course_id, k=5)
    return {
        "ok": True,
        "results": [
            {
                "course": hit.course_title,
                "document": hit.document,
                "page": hit.page,
                "text": hit.text[:600],
            }
            for hit in hits
        ],
    }
