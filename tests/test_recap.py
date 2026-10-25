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


def test_save_recap_falls_back_to_notepad_when_windows_association_fails(tmp_path, monkeypatch):
    calls = []

    class WindowsOS:
        name = "nt"

        @staticmethod
        def startfile(_path):
            raise OSError("no markdown association")

    monkeypatch.setattr(recap_module, "os", WindowsOS)
    monkeypatch.setattr(
        recap_module.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )
    path = save_recap("Windows recap", home=tmp_path)
    assert calls[0][0] == ["notepad.exe", str(path)]
