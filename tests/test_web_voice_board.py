from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
from http.client import HTTPConnection
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import threading
from urllib.parse import urlencode

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "web_voice_board.py"
_SPEC = spec_from_file_location("web_voice_board", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
web_voice_board = module_from_spec(_SPEC)
_SPEC.loader.exec_module(web_voice_board)


class _StubResponse:
    def __init__(self, body: bytes, status: int = 201):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self.body


@pytest.fixture
def server():
    instance = web_voice_board.WebVoiceHTTPServer(
        ("127.0.0.1", 0),
        web_voice_board.WebVoiceHandler,
        host="127.0.0.1",
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=2)

@pytest.fixture
def public_server():
    instance = web_voice_board.WebVoiceHTTPServer(
        ("127.0.0.1", 0),
        web_voice_board.WebVoiceHandler,
        host="127.0.0.1",
        public_hosts=("gerald-voix-td-tableau--4pp45m8r.preview.devinapps.com",),
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield instance
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=2)


def _request(server, method: str, path: str, body: bytes = b"", headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    result = response.status, response.read(), response.headers
    connection.close()
    return result


def test_session_posts_sdp_and_filtered_realtime_config(monkeypatch, server):
    captured = []

    def fake_urlopen(request, timeout):
        captured.append((request, timeout))
        return _StubResponse(b"v=0\r\nanswer")

    monkeypatch.setattr(web_voice_board, "urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-logged")
    monkeypatch.setenv("GERALD_MODEL", "gpt-realtime-2")
    title = "Exercice 1"
    lines = ["Résous dans ℝ : x² − 5x + 6 = 0"]
    query = urlencode({"title": title, "lines": json.dumps(lines, ensure_ascii=False)})

    status, body, response_headers = _request(
        server,
        "POST",
        f"/api/session?{query}",
        b"v=0\r\noffer",
        {"Content-Type": "application/sdp"},
    )

    assert status == 201
    assert body == b"v=0\r\nanswer"
    request, timeout = captured[0]
    assert timeout == 60
    assert request.full_url == web_voice_board.OPENAI_REALTIME_CALLS
    assert request.get_header("Authorization") == "Bearer test-key-not-logged"
    content_type = next(
        value for key, value in request.headers.items() if key.casefold() == "content-type"
    )
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: "
        + content_type.encode("ascii")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + request.data
    )
    parts = {
        part.get_param("name", header="content-disposition"): part
        for part in message.iter_parts()
    }
    assert parts["sdp"].get_content_type() == "application/sdp"
    assert parts["sdp"].get_payload(decode=True) == b"v=0\r\noffer"
    assert parts["session"].get_content_type() == "application/json"
    session = json.loads(parts["session"].get_content())
    assert session["model"] == "gpt-realtime-2"
    assert session["type"] == "realtime"
    assert session["audio"]["output"]["voice"] == "marin"
    assert session["audio"]["input"]["transcription"] == {
        "model": "gpt-4o-mini-transcribe",
        "language": "fr",
    }
    assert session["instructions"] == web_voice_board.session_instructions(title, lines)
    assert session["instructions"].startswith(web_voice_board.SYSTEM_PROMPT.read_text(encoding="utf-8"))
    assert "BOARD MODE\nExercise: Exercice 1" in session["instructions"]
    assert "« à toi de jouer »" in session["instructions"]
    assert (
        "valeur de Δ ni les racines tant que l’élève ne les a pas trouvées lui-même. Dès qu’il a écrit "
        "lui-même la bonne valeur de Δ et demande une rédaction ou une solution propre, rédige-la au "
        "tableau avec write_math, une ligne par étape (Δ = b² − 4ac = …, x = (−b ± √Δ)/2a, "
        "x₁ = …, x₂ = …), puis félicite-le en une phrase. Pour une erreur de signe, vise le signe et le "
        "nombre ensemble (target_text « + 24 », pas « 24 ») et donne l’indice en une phrase, par exemple "
        "« −4ac donne −24 »."
    ) in session["instructions"]
    assert (
        "Si l’élève demande explicitement une flèche, utilise arrow et underline "
        "(intent=correction) sur le même target_text dans le même tour."
    ) in session["instructions"]
    assert "encre élève #n" in session["instructions"]
    assert "x**2-5*x+6" in session["instructions"]
    assert "ne l'annonce jamais sans appeler l'outil" in session["instructions"]
    assert "n'ajoute pas de note ou de tip" in session["instructions"]
    tool_names = {tool["name"] for tool in session["tools"]}
    assert tool_names == web_voice_board.WEB_TOOL_NAMES
    assert len(tool_names) == len(session["tools"])
    tools_by_name = {tool["name"]: tool for tool in session["tools"]}
    assert "write_math" in tools_by_name["write"]["description"]
    assert "LaTeX" in tools_by_name["write_math"]["description"]
    assert r"\Delta = b^2 - 4ac" in tools_by_name["write_math"]["description"]
    assert "le target_text de to" in tools_by_name["arrow"]["description"]
    assert "réserve write aux mots français courts" in session["instructions"]
    intent_tool_names = {
        "write",
        "write_math",
        "underline",
        "circle",
        "highlight",
        "arrow",
        "point",
        "note",
        "tip",
    }
    for name in intent_tool_names:
        schema = tools_by_name[name]["parameters"]
        assert schema["properties"]["intent"]["type"] == "string"
        assert schema["properties"]["intent"]["enum"] == [
            "correction",
            "valide",
            "remarque",
        ]
        assert "intent" not in schema.get("required", [])
        assert "Code couleur" in tools_by_name[name]["description"]
    for color_intent in (
        "rouge (intent=correction)",
        "vert (intent=valide)",
        "bleu (intent=remarque)",
        "l'écriture normale reste noire",
            "souligne aussi le même terme fautif avec underline (intent=correction) dans le même tour",
    ):
        assert color_intent in session["instructions"]
    assert "une seule underline ou circle (intent=correction)" in session["instructions"]
    assert "l’élève demande explicitement une flèche" in session["instructions"]
    plot_tool = next(tool for tool in session["tools"] if tool["name"] == "plot")
    plot_schema = plot_tool["parameters"]
    json.dumps(plot_schema)
    assert plot_schema["type"] == "object"
    assert plot_schema["required"] == ["functions", "x_min", "x_max"]
    assert plot_schema["properties"]["functions"]["minItems"] == 1
    assert plot_schema["properties"]["functions"]["maxItems"] == 3
    assert plot_schema["properties"]["functions"]["items"]["required"] == ["expr"]
    assert "appelle plot" in plot_tool["description"]
    assert "appelle plot" in session["instructions"]
    for tool in session["tools"]:
        if tool["name"] in {"underline", "circle", "point", "note", "highlight", "arrow", "tip"}:
            assert "element_id" in str(tool["parameters"])
            assert "target_text" in str(tool["parameters"])


def test_live_session_omits_default_exercise_context(monkeypatch, server):
    captured = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-logged")

    def fake_urlopen(request, timeout):
        assert timeout == 60
        captured.append(request)
        return _StubResponse(b"v=0\r\nanswer")

    monkeypatch.setattr(web_voice_board, "urlopen", fake_urlopen)
    status, _body, _headers = _request(
        server,
        "POST",
        "/api/session?live=1",
        b"v=0\r\noffer",
        {"Content-Type": "application/sdp"},
    )

    assert status == 201
    request = captured[0]
    content_type = next(
        value for key, value in request.headers.items() if key.casefold() == "content-type"
    )
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: "
        + content_type.encode("ascii")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + request.data
    )
    session_part = next(
        part
        for part in message.iter_parts()
        if part.get_param("name", header="content-disposition") == "session"
    )
    session = json.loads(session_part.get_content())
    assert "LIVE BOARD MODE" in session["instructions"]
    assert "do not answer only with speech" in session["instructions"]
    assert "x² − 5x + 6" not in session["instructions"]
    assert "x**2-5*x+6" not in session["instructions"]
    assert "x**2-5*x+6" not in " ".join(
        tool["description"] for tool in session["tools"]
    )
    assert "open_board" not in {tool["name"] for tool in session["tools"]}


def test_document_session_uses_sanitized_title_and_live_tools():
    config = web_voice_board.build_session_config(
        "gpt-realtime-2",
        "Cours\u0000 de Pythagore",
        [],
        doc_mode=True,
    )
    instructions = config["instructions"]
    assert "DOCUMENT MODE" in instructions
    assert "« Cours de Pythagore »" in instructions
    assert "x² − 5x + 6" not in instructions
    assert "x**2-5*x+6" not in instructions
    assert "do not answer only with speech" not in instructions
    assert "provide a full exercise solution" in instructions
    tools = {tool["name"]: tool for tool in config["tools"]}
    assert set(tools) == web_voice_board.WEB_TOOL_NAMES
    open_board = tools["open_board"]["parameters"]
    assert open_board["properties"] == {}
    assert open_board["required"] == []


def test_document_title_sanitization_strips_controls_and_limits_length():
    title = "  A\u0000B\n" + "x" * 130
    sanitized = web_voice_board.sanitize_document_title(title)
    assert sanitized == ("AB" + "x" * 118)
    assert len(sanitized) == 120


def test_paint_mode_uses_guidance_and_exact_tool_list():
    config = web_voice_board.build_session_config("gpt-realtime-2", paint_mode=True)
    guidance = web_voice_board.PAINT_MODE_GUIDANCE.read_text(encoding="utf-8")
    assert config["instructions"].startswith(guidance)
    assert config["instructions"].endswith(web_voice_board.COLOR_GUIDANCE)
    assert [tool["name"] for tool in config["tools"]] == [
        "point",
        "circle",
        "arrow",
        "highlight",
        "note",
        "tip",
        "clear_gerald",
    ]
    assert "write" not in {tool["name"] for tool in config["tools"]}
    assert "plot" not in {tool["name"] for tool in config["tools"]}
    assert "open_board" not in {tool["name"] for tool in config["tools"]}


def test_minipaint_index_is_served(server):
    status, _body, _headers = _request(server, "GET", "/vendor/minipaint/index.html")
    assert status == 200


def test_plot_endpoint_returns_root_and_vertex_points(server):
    payload = {
        "functions": [{"expr": "x**2-5*x+6", "label": "f(x)"}],
        "x_min": -1,
        "x_max": 6,
        "image_size": [800, 600],
        "points": [
            {"x": 2, "y": 0, "label": "Racine 2"},
            {"x": 3, "y": 0, "label": "Racine 3"},
            {"x": 2.5, "y": -0.25, "label": "Sommet"},
        ],
    }
    status, body, _headers = _request(
        server,
        "POST",
        "/api/plot",
        json.dumps(payload).encode("utf-8"),
        {"Content-Type": "application/json"},
    )

    assert status == 200
    result = json.loads(body)
    assert result["ok"] is True
    assert result["x_range"] == [-1, 6]
    assert [point["label"] for point in result["points"]] == [
        "Racine 2",
        "Racine 3",
        "Sommet",
    ]
    assert [(point["x"], point["y"]) for point in result["points"]] == [
        (2, 0),
        (3, 0),
        (2.5, -0.25),
    ]
    x, y, width, height = result["box"]
    assert all(
        x <= point["x_img"] <= x + width and y <= point["y_img"] <= y + height
        for point in result["points"]
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://attacker.example"},
        {"Host": "attacker.example"},
    ],
)
def test_foreign_origin_or_host_is_rejected(monkeypatch, server, headers):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-logged")
    called = False

    def fake_urlopen(_request, _timeout):
        nonlocal called
        called = True
        return _StubResponse(b"should not be called")

    monkeypatch.setattr(web_voice_board, "urlopen", fake_urlopen)
    status, body, response_headers = _request(
        server,
        "POST",
        "/api/session",
        b"v=0\r\noffer",
        {"Content-Type": "application/sdp", **headers},
    )

    assert status == 403
    assert response_headers["Connection"].lower() == "close"
    assert json.loads(body)["error"] == "origin or host not allowed"
    assert not called


def test_root_redirects_to_landing_and_td_board_defaults_to_voice(server):
    status, _body, headers = _request(server, "GET", "/")
    assert status == 302
    assert headers["Location"] == "/landing.html"

    status, _body, _headers = _request(server, "GET", "/landing.html")
    assert status == 200

    status, _body, _headers = _request(server, "GET", "/app.html")
    assert status == 200

    status, _body, headers = _request(server, "GET", "/td.html?voice=0&from=demo")
    assert status == 302
    assert "voice=1" in headers["Location"]
    assert "from=demo" in headers["Location"]

    status, _body, headers = _request(server, "GET", "/td.html?live=1")
    assert status == 302
    assert headers["Location"] == "/td.html?live=1&voice=1"

    status, _body, headers = _request(server, "GET", "/board.html?title=Exercice%201")
    assert status == 302
    assert "title=Exercice+1" in headers["Location"]
    assert "voice=1" in headers["Location"]

    status, _body, headers = _request(server, "GET", "/board.html?voice=0&title=Exercice%201")
    assert status == 302
    assert "voice=1" in headers["Location"]


def test_static_route_rejects_foreign_origin(server):
    status, body, _headers = _request(
        server,
        "GET",
        "/landing.html",
        headers={"Origin": "http://attacker.example"},
    )
    assert status == 403
    assert json.loads(body)["error"] == "origin or host not allowed"


def test_public_https_origin_is_allowed_and_unknown_host_is_rejected(
    monkeypatch, public_server
):
    public_host = "gerald-voix-td-tableau--4pp45m8r.preview.devinapps.com"
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-logged")
    monkeypatch.setattr(
        web_voice_board,
        "urlopen",
        lambda _request, timeout: _StubResponse(b"v=0\r\nanswer", status=200),
    )
    status, body, _headers = _request(
        public_server,
        "POST",
        "/api/session",
        b"v=0\r\noffer",
        {
            "Content-Type": "application/sdp",
            "Host": public_host,
            "Origin": f"https://{public_host}",
        },
    )
    assert status == 200
    assert body == b"v=0\r\nanswer"

    status, body, _headers = _request(
        public_server,
        "POST",
        "/api/session",
        b"v=0\r\noffer",
        {
            "Content-Type": "application/sdp",
            "Host": "unknown.example",
            "Origin": f"https://{public_host}",
        },
    )
    assert status == 403
    assert json.loads(body)["error"] == "origin or host not allowed"


def test_session_limiter_caps_per_client_and_per_day():
    now = [0.0]
    limiter = web_voice_board.SessionLimiter(per_client_hour=2, per_day=3, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("c")
    now[0] = 3_600.0
    assert not limiter.allow("a")
    now[0] = 86_400.0
    assert limiter.allow("a")


def test_session_returns_429_when_limit_reached(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return _StubResponse(b"v=0\r\nanswer\r\n")

    monkeypatch.setattr(web_voice_board, "urlopen", fake_urlopen)
    instance = web_voice_board.WebVoiceHTTPServer(
        ("127.0.0.1", 0),
        web_voice_board.WebVoiceHandler,
        host="127.0.0.1",
        limiter=web_voice_board.SessionLimiter(per_client_hour=1),
    )
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        headers = {
            "Host": f"127.0.0.1:{instance.server_port}",
            "Content-Type": "application/sdp",
        }
        first = _request(instance, "POST", "/api/session", b"v=0\r\noffer\r\n", headers)
        second = _request(instance, "POST", "/api/session", b"v=0\r\noffer\r\n", headers)
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=2)
    assert first[0] == 201
    assert second[0] == 429
    assert len(calls) == 1


def test_healthz_skips_host_check(server):
    status, body, _ = _request(server, "GET", "/healthz", headers={"Host": "10.0.0.5:10000"})
    assert status == 200
    assert json.loads(body) == {"ok": True}
