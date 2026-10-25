import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_notebook_is_nbformat_four_and_embeds_server_exactly():
    notebook_path = ROOT / "colab" / "gerald_grounder.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    write_cell = next(
        cell
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
        and "".join(cell["source"]).startswith("%%writefile /content/server.py\n")
    )
    embedded = "".join(write_cell["source"]).split("\n", maxsplit=1)[1]
    assert embedded == (ROOT / "colab" / "server.py").read_text(encoding="utf-8")


def test_trycloudflare_parser_extracts_quick_tunnel_url():
    source = (ROOT / "colab" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    parser = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_trycloudflare_url"
    )
    namespace = {"re": re}
    module = ast.Module(body=[parser], type_ignores=[])
    exec(compile(module, "colab/server.py", "exec"), namespace)

    assert namespace["parse_trycloudflare_url"](
        "INF | + https://quiet-willow-123.trycloudflare.com"
    ) == "https://quiet-willow-123.trycloudflare.com"
    assert namespace["parse_trycloudflare_url"]("Tunnel connection ready") is None
