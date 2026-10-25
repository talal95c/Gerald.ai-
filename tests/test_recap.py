from types import SimpleNamespace

import pytest

from gerald.tools.recap import save_recap
from gerald.tools import recap as recap_module
from gerald.home import bridge as bridge_module


def simulate_platform(monkeypatch, module, name, associated):
    fake_os = SimpleNamespace(name=name)
    monkeypatch.setattr(module, "os", fake_os)
    monkeypatch.setattr(module, "has_file_association", lambda _suffix: associated)
    return fake_os


def test_save_recap_writes_markdown_under_temporary_home(tmp_path, monkeypatch):
    simulate_platform(monkeypatch, recap_module, "posix", True)
    path = save_recap("# Leçon\n\nPoints clés.", home=tmp_path, open_file=False)

    assert path.parent == tmp_path / "Gerald" / "lessons"
    assert path.suffix == ".md"
    assert path.read_text(encoding="utf-8") == "# Leçon\n\nPoints clés.\n"


def test_save_recap_uses_an_exclusive_collision_suffix(tmp_path, monkeypatch):
    simulate_platform(monkeypatch, recap_module, "posix", True)
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

    fake_os = simulate_platform(monkeypatch, recap_module, "nt", False)
    fake_os.startfile = lambda _path: (_ for _ in ()).throw(OSError("no markdown association"))
    monkeypatch.setattr(
        recap_module.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )
    path = save_recap("Windows recap", home=tmp_path)
    assert calls[0][0] == ["notepad.exe", str(path)]


def test_save_recap_uses_startfile_when_windows_association_exists(tmp_path, monkeypatch):
    calls = []
    fake_os = simulate_platform(monkeypatch, recap_module, "nt", True)
    fake_os.startfile = calls.append
    monkeypatch.setattr(recap_module.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("notepad was used"))

    path = save_recap("Windows recap", home=tmp_path)

    assert calls == [str(path)]


def test_bridge_open_recap_falls_back_to_notepad_when_url_handler_fails(tmp_path, monkeypatch):
    calls = []

    fake_os = simulate_platform(monkeypatch, bridge_module, "nt", False)
    fake_os.startfile = lambda _path: pytest.fail("startfile was used without an association")
    monkeypatch.setattr(bridge_module.QDesktopServices, "openUrl", lambda _url: pytest.fail("openUrl was used on Windows"))
    monkeypatch.setattr(bridge_module.subprocess, "Popen", lambda args: calls.append(args))
    bridge = bridge_module.Bridge(None, None, None)
    path = tmp_path / "lesson.md"

    bridge.openRecap(str(path))

    assert calls == [["notepad.exe", str(path)]]


def test_bridge_open_recap_uses_in_app_view_when_no_handler_exists(tmp_path, monkeypatch):
    shown = []
    simulate_platform(monkeypatch, bridge_module, "posix", True)
    monkeypatch.setattr(bridge_module.QDesktopServices, "openUrl", lambda _url: False)
    monkeypatch.setattr(bridge_module.Bridge, "_show_recap_in_app", lambda _self, path: shown.append(path))
    bridge = bridge_module.Bridge(None, None, None)
    path = tmp_path / "lesson.md"

    bridge.openRecap(str(path))

    assert shown == [str(path)]


def test_bridge_open_recap_uses_startfile_with_windows_association(tmp_path, monkeypatch):
    calls = []
    fake_os = simulate_platform(monkeypatch, bridge_module, "nt", True)
    fake_os.startfile = calls.append
    monkeypatch.setattr(bridge_module.subprocess, "Popen", lambda *_args: pytest.fail("notepad was used"))
    bridge = bridge_module.Bridge(None, None, None)
    path = tmp_path / "lesson.md"

    bridge.openRecap(str(path))

    assert calls == [str(path)]
