from gerald.tools.recap import save_recap
from gerald.tools import recap as recap_module


def test_save_recap_writes_markdown_under_temporary_home(tmp_path):
    path = save_recap("# Leçon\n\nPoints clés.", home=tmp_path, open_file=False)

    assert path.parent == tmp_path / "Gerald" / "lessons"
    assert path.suffix == ".md"
    assert path.read_text(encoding="utf-8") == "# Leçon\n\nPoints clés.\n"


def test_save_recap_uses_an_exclusive_collision_suffix(tmp_path, monkeypatch):
    class FixedDateTime:
        @staticmethod
        def now():
            from datetime import datetime

            return datetime(2026, 10, 25, 14, 7)

    monkeypatch.setattr(recap_module, "datetime", FixedDateTime)
    first = save_recap("Premier", home=tmp_path, open_file=False)
    second = save_recap("Second", home=tmp_path, open_file=False)

    assert first.name == "2026-10-25_14-07.md"
    assert second.name == "2026-10-25_14-07-2.md"
    assert first.read_text(encoding="utf-8") == "Premier\n"
    assert second.read_text(encoding="utf-8") == "Second\n"
