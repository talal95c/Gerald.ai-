from gerald.library.context import course_search_results, profile_block
from gerald.library.store import Store


def test_profile_block_includes_student_profile_course_titles_and_document_counts(tmp_path):
    store = Store(tmp_path / "library")
    store.save_profile("Léa", "Lycée", ["SVT", "Maths"])
    course = store.create_course("Biologie", "SVT")
    store._create_document(course.id, "cours.pdf")
    store._create_document(course.id, "fiche.docx")

    block = profile_block(store)

    assert block.startswith("PROFIL DE L'ÉLÈVE")
    assert "Nom : Léa" in block
    assert "Niveau : Lycée" in block
    assert "Matières : SVT, Maths" in block
    assert "- Biologie (SVT) — 2 document(s)" in block
    store.close()


def test_course_search_limits_passage_text_and_filters_by_course_title(tmp_path):
    store = Store(tmp_path / "library")
    course = store.create_course("Biologie", "SVT")
    document = store._create_document(course.id, "cours.txt")
    passage = "photosynthèse " + ("détail " * 100)
    store._replace_chunks(document.id, [(2, passage, None)])
    store._finish_document(document.id, status="ready", error=None, n_chunks=1)

    result = course_search_results(store, None, "photosynthèse", "biologie")
    assert result["ok"] is True
    assert len(result["results"]) == 1
    assert result["results"][0]["course"] == "Biologie"
    assert result["results"][0]["document"] == "cours.txt"
    assert result["results"][0]["page"] == 2
    assert len(result["results"][0]["text"]) == 600
    assert course_search_results(store, None, "photosynthèse", "Maths") == {
        "ok": True,
        "results": [],
    }
    store.close()
