from gerald.tools.recap import save_recap


def test_save_recap_writes_markdown_under_temporary_home(tmp_path):
    path = save_recap("# Leçon\n\nPoints clés.", home=tmp_path, open_file=False)

    assert path.parent == tmp_path / "Gerald" / "lessons"
    assert path.suffix == ".md"
    assert path.read_text(encoding="utf-8") == "# Leçon\n\nPoints clés.\n"
