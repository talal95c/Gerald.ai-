import asyncio
import ast
import base64
import binascii
import hmac
import io
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[1]


class _EndpointHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code


def _point_endpoint(image_module):
    source = (ROOT / "colab" / "server.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    point = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "point"
    )
    point.decorator_list = []
    namespace = {
        "Header": lambda **_kwargs: None,
        "PointRequest": object,
        "HTTPException": _EndpointHTTPException,
        "hmac": hmac,
        "TOKEN": "test-token",
        "MAX_IMAGE_URL_CHARS": 15_000_000,
        "MAX_IMAGE_PIXELS": 40_000_000,
        "base64": base64,
        "binascii": binascii,
        "Image": image_module,
        "UnidentifiedImageError": type("UnidentifiedImageError", (Exception,), {}),
        "io": io,
        "re": re,
        "model": None,
    }
    module = ast.Module(body=[point], type_ignores=[])
    exec(compile(module, "colab/server.py", "exec"), namespace)
    return namespace["point"]


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


def test_colab_point_rejects_oversized_image_url():
    point = _point_endpoint(SimpleNamespace(DecompressionBombError=Exception))
    request = SimpleNamespace(image_url="x" * 15_000_001)

    with pytest.raises(_EndpointHTTPException) as failure:
        asyncio.run(point(request, "test-token"))

    assert failure.value.status_code == 413


def test_colab_point_rejects_image_dimensions_before_conversion():
    class FakeOpenedImage:
        width = 20_001
        height = 2_000

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def convert(self, _mode):
            raise AssertionError("oversized image must be rejected before conversion")

    class FakeImage:
        DecompressionBombError = type("DecompressionBombError", (Exception,), {})

        @staticmethod
        def open(_image):
            return FakeOpenedImage()

    point = _point_endpoint(FakeImage)
    request = SimpleNamespace(image_url="data:image/png;base64,AA==")

    with pytest.raises(_EndpointHTTPException) as failure:
        asyncio.run(point(request, "test-token"))

    assert failure.value.status_code == 413
