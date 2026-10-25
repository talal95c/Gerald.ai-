from __future__ import annotations

import argparse
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
import unicodedata

from gerald.tools.plot import build_plot
from gerald.tools.registry import TOOL_SCHEMAS


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "gerald" / "home" / "webui"
SYSTEM_PROMPT = ROOT / "gerald" / "prompts" / "system_prompt.md"
DEFAULT_TITLE = "Exercice 1"
DEFAULT_LINES = ["Résous dans ℝ : x² − 5x + 6 = 0"]
WEB_TOOL_NAMES = {
    "write",
    "write_math",
    "plot",
    "clear_gerald",
    "underline",
    "circle",
    "highlight",
    "arrow",
    "point",
    "note",
    "tip",
    "open_board",
}
INTENT_TOOL_NAMES = {
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
INTENT_VALUES = ["correction", "valide", "remarque"]
COLOR_GUIDANCE = (
    "Code couleur : rouge (intent=correction) pour signaler une erreur ou la correction, "
    "vert (intent=valide) pour ce qui est juste, bleu (intent=remarque) pour une remarque "
    "ou un rappel de méthode ; l'écriture normale reste noire."
)
TD_EXERCISES = [
    ("exercice-1", "Exercice 1", ["Résous dans ℝ : x² − 5x + 6 = 0"]),
    ("exercice-2", "Exercice 2", ["Résous dans ℝ : 2x² + 3x − 2 = 0"]),
    ("exercice-3", "Exercice 3", ["Écris sous forme canonique : x² − 4x + 1"]),
    ("exercice-4", "Exercice 4", ["Étudie le signe de −x² + x + 6"]),
]
OPENAI_REALTIME_CALLS = "https://api.openai.com/v1/realtime/calls"
MAX_BODY_BYTES = 1_000_000
logger = logging.getLogger("web_voice_board")


def _web_tools(live_mode: bool = False, doc_mode: bool = False) -> list[dict]:
    def preserve_targets(schema: dict) -> None:
        properties = schema.get("properties")
        if isinstance(properties, dict):
            if "element_id" in properties:
                properties.setdefault(
                    "target_text",
                    {
                        "type": "string",
                        "description": "Exact visible text to target, optionally a substring of the element.",
                    },
                )
            for value in properties.values():
                if isinstance(value, dict):
                    preserve_targets(value)

    tools = []
    for tool in TOOL_SCHEMAS:
        if tool["name"] not in WEB_TOOL_NAMES or tool["name"] == "tip":
            continue
        schema = deepcopy(tool["parameters"])
        preserve_targets(schema)
        description = tool["description"]
        if tool["name"] in INTENT_TOOL_NAMES:
            schema.setdefault("properties", {})["intent"] = {
                "type": "string",
                "enum": INTENT_VALUES,
                "description": "Optional semantic color intent; omit to keep the default color.",
            }
            description += f" {COLOR_GUIDANCE}"
        if tool["name"] == "plot":
            if live_mode:
                description += (
                    " Pour toute demande de courbe ou de graphe, appelle plot avec l'expression; "
                    "ne dessine jamais une courbe à la main; utilise une multiplication explicite, "
                    "par exemple x**2+1, et ajoute les points remarquables connus dans points."
                )
            else:
                description += (
                    " Pour toute demande de courbe ou de graphe, appelle plot avec l'expression; "
                    "ne dessine jamais une courbe à la main; utilise une multiplication explicite, par exemple "
                    "x**2-5*x+6, et ajoute les racines et le sommet connus dans points."
                )
        elif tool["name"] == "write":
            description += (
                " Réserve write aux mots ou courtes expressions françaises; pour toute formule mathématique, "
                "utilise write_math avec du LaTeX."
            )
        elif tool["name"] == "write_math":
            description += (
                " Utilise write_math pour les formules et fournis du LaTeX, par exemple "
                "\\Delta = b^2 - 4ac."
            )
        elif tool["name"] == "arrow":
            description += (
                " Si l'élève demande explicitement une flèche, utilise arrow au lieu d'une underline ou circle."
            )
        tools.append(
            {
                "type": "function",
                "name": tool["name"],
                "description": description,
                "parameters": schema,
            }
        )
    tools.append(
        {
            "type": "function",
            "name": "tip",
            "description": f"Show a short spoken hint in a bubble next to Gerald's pointer. {COLOR_GUIDANCE}",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "element_id": {"type": "integer"},
                    "target_text": {"type": "string"},
                    "intent": {
                        "type": "string",
                        "enum": INTENT_VALUES,
                        "description": "Optional semantic color intent; omit to keep the default color.",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        }
    )
    if doc_mode:
        tools.append(
            {
                "type": "function",
                "name": "open_board",
                "description": "Open an empty board over the current document without ending the voice session.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
            }
        )
    elif not live_mode:
        tools.append(
            {
                "type": "function",
                "name": "open_board",
                "description": "Open the selected TD exercise on the board without ending the voice session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "exercise_id": {
                            "type": "string",
                            "enum": [item[0] for item in TD_EXERCISES],
                        },
                    },
                    "required": ["exercise_id"],
                    "additionalProperties": False,
                },
            }
        )
    return tools


WEB_TOOLS = _web_tools()


def sanitize_document_title(title: str) -> str:
    sanitized = "".join(character for character in title if unicodedata.category(character) != "Cc")
    return sanitized.strip()[:120] or "document sans titre"


def session_instructions(
    title: str = DEFAULT_TITLE,
    lines: list[str] | None = None,
    live_mode: bool = False,
    doc_mode: bool = False,
) -> str:
    prompt = SYSTEM_PROMPT.read_text(encoding="utf-8")
    board_guidance = (
        "Pour cibler une écriture manuscrite, choisis l'element_id de sa boîte « encre élève #n » "
        "plutôt que des coordonnées devinées. Sur le tableau, utilise write_math avec du LaTeX "
        "(par exemple \\Delta = b^2 - 4ac) pour les formules; réserve write aux mots français courts. "
    )
    if live_mode:
        prompt = prompt.partition("\n## Board mode\n")[0]
        live_guidance = (
            "LIVE BOARD MODE — no TD or exercise document is loaded. The empty board is already open. "
            "Answer the learner's requested topic, using concise writing or marks on the board. "
            "For each explanation request, demonstrate at least one useful formula or diagram on the board; "
            "do not answer only with speech. "
            "Do not call open_board. "
        )
        return f"{prompt.rstrip()}\n{live_guidance}{board_guidance}{COLOR_GUIDANCE}"

    if doc_mode:
        prompt = prompt.partition("\n## Board mode\n")[0]
        document_title = sanitize_document_title(title)
        document_guidance = (
            f"DOCUMENT MODE — the learner opened « {document_title} ». Work directly on this visible document: "
            "explain its content, point to relevant passages, and use element_id for underline, circle, highlight, "
            "arrow, or other marks. The learner's visible document elements are supplied with each turn. "
            "Never invent document content or provide a full exercise solution; guide the learner one step at a time. "
            "If the learner asks to use the board, call parameterless open_board to open an empty board overlay; "
            "the document remains open underneath. Do not include or assume any TD exercise list. "
        )
        return f"{prompt.rstrip()}\n{document_guidance}{board_guidance}{COLOR_GUIDANCE}"

    exercise_lines = lines if lines is not None else DEFAULT_LINES
    td_context = "\n".join(
        ["TD MODE — exercises and stable exercise_id values:"]
        + [
            f"- {exercise_id}: {exercise_title} — {'; '.join(items)}"
            for exercise_id, exercise_title, items in TD_EXERCISES
        ]
    )
    board_context = "\n".join(["BOARD MODE", f"Exercise: {title}", *exercise_lines])
    td_guidance = (
        "Sur le TD, commence par expliquer oralement et pointer les éléments du document sans quitter la page. "
        "Propose « Viens, on va au tableau » et n'appelle open_board avec l'exercise_id correspondant "
        "que si l'élève le demande ou accepte la proposition, ou si une explication écrite est indispensable. "
        "Si l'élève demande à aller au tableau, appelle open_board avant de dire que tu l'ouvres; "
        "ne l'annonce jamais sans appeler l'outil. "
        "Dans cette démo web, les coordonnées des outils sont des pixels CSS de la vue active, origine "
        "(0,0) en haut à gauche; element_id et target_text désignent les éléments visibles listés dans le contexte. "
    )
    tutor_guidance = (
        "Explique d’abord la méthode pour identifier a, b et c, puis comment former "
        "Δ = b² − 4ac, sans calculer sa valeur ni résoudre l’équation. Dis ensuite "
        "« à toi de jouer » et laisse l’élève faire ses erreurs. Ne donne jamais la "
        "valeur de Δ ni les racines; si l’élève demande explicitement une flèche, utilise arrow "
        "au lieu d’une underline ou circle. Sinon, s’il se trompe, utilise une seule underline ou circle "
        "(intent=correction) sur le terme fautif et n'ajoute pas de note ou de tip. "
        "Pour toute demande de courbe ou de graphe, appelle plot avec l’expression correspondante; "
        "ne dessine jamais une courbe à la main avec draw_path; utilise une multiplication explicite, "
        "par exemple x**2-5*x+6, et ajoute dans points les racines et le sommet connus. "
        "Même après avoir tracé une courbe, ne prononce pas les racines ni leur approximation; "
        "invite l'élève à les lire lui-même. "
        "Quand il a résolu l’exercice, termine par « bravo » et un bref récapitulatif "
        "de la méthode. "
        + COLOR_GUIDANCE
    )
    return f"{prompt}\n{td_context}\n{board_context}\n{td_guidance}{board_guidance}{tutor_guidance}"


def build_session_config(
    model: str,
    title: str = DEFAULT_TITLE,
    lines: list[str] | None = None,
    live_mode: bool = False,
    doc_mode: bool = False,
) -> dict:
    tools = _web_tools(live_mode, doc_mode) if live_mode or doc_mode else deepcopy(WEB_TOOLS)
    return {
        "type": "realtime",
        "model": model,
        "instructions": session_instructions(title, lines, live_mode, doc_mode),
        "audio": {
            "output": {"voice": os.getenv("GERALD_VOICE", "marin")},
            "input": {
                "turn_detection": {"type": "server_vad"},
                "transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": "fr",
                },
            },
        },
        "tools": tools,
    }


def build_multipart(sdp: str, session: dict, boundary: str | None = None) -> tuple[bytes, str]:
    boundary = boundary or f"gerald-{uuid4().hex}"
    marker = boundary.encode("ascii")
    body = b"".join(
        [
            b"--" + marker + b"\r\n",
            b'Content-Disposition: form-data; name="sdp"\r\n',
            b"Content-Type: application/sdp\r\n\r\n",
            sdp.encode("utf-8"),
            b"\r\n--" + marker + b"\r\n",
            b'Content-Disposition: form-data; name="session"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            json.dumps(session, ensure_ascii=False).encode("utf-8"),
            b"\r\n--" + marker + b"--\r\n",
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def _parse_exercise(query: str) -> tuple[str, list[str]]:
    values = parse_qs(query)
    title = values.get("title", [DEFAULT_TITLE])[-1][:120]
    raw_lines = values.get("lines", [None])[-1]
    if raw_lines is None:
        return title, list(DEFAULT_LINES)
    try:
        lines = json.loads(raw_lines)
    except json.JSONDecodeError as error:
        raise ValueError("lines must be a JSON array of strings") from error
    if (
        not isinstance(lines, list)
        or len(lines) > 20
        or any(not isinstance(line, str) or len(line) > 500 for line in lines)
    ):
        raise ValueError("lines must contain at most 20 strings of 500 characters")
    return title, lines


class WebVoiceHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address,
        handler,
        *,
        host: str,
        web_root: Path = WEB_ROOT,
        public_hosts: tuple[str, ...] = (),
    ):
        self.host = host
        self.web_root = web_root
        self.public_hosts = tuple(item.strip().casefold() for item in public_hosts if item.strip())
        super().__init__(address, handler)

    @property
    def expected_host(self) -> str:
        return f"{self.host}:{self.server_port}"

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return frozenset({self.expected_host.casefold(), *self.public_hosts})


class WebVoiceHandler(SimpleHTTPRequestHandler):
    server: WebVoiceHTTPServer

    def __init__(self, request, client_address, server):
        super().__init__(
            request,
            client_address,
            server,
            directory=str(server.web_root),
        )

    def log_message(self, format_string: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format_string % args)

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, value: dict) -> None:
        self._send_bytes(
            status,
            json.dumps(value, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _read_body(self, limit: int = MAX_BODY_BYTES) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as error:
            raise ValueError("Content-Length is required") from error
        if length < 0 or length > limit:
            raise OverflowError("request body is too large")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("incomplete request body")
        return body

    def _valid_origin(self) -> bool:
        allowed = self.server.allowed_hosts
        hosts = {
            self.headers.get("Host", "").casefold(),
            self.headers.get("X-Forwarded-Host", "").split(",")[0].strip().casefold(),
        } - {""}
        if not hosts & allowed:
            logger.warning("rejected host %s (origin %s)", sorted(hosts), self.headers.get("Origin"))
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urlsplit(origin)
        if parsed.scheme in {"http", "https"} and parsed.netloc.casefold() in allowed:
            return True
        logger.warning("rejected origin %s (host %s)", origin, sorted(hosts))
        return False

    def do_GET(self) -> None:
        if not self._valid_origin():
            self._send_json(403, {"ok": False, "error": "origin or host not allowed"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self.send_response(302)
            self.send_header("Location", "/landing.html")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path in {"/td.html", "/board.html"}:
            query = parse_qs(parsed.query, keep_blank_values=True)
            query["voice"] = ["1"]
            encoded = urlencode(
                [(key, value) for key, values in query.items() for value in values]
            )
            location = parsed.path + (f"?{encoded}" if encoded else "")
            if query == parse_qs(parsed.query, keep_blank_values=True):
                super().do_GET()
                return
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if not self._valid_origin():
            self._send_json(403, {"ok": False, "error": "origin or host not allowed"})
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/api/session":
            self._session(parsed.query)
        elif parsed.path == "/api/plot":
            self._plot()
        else:
            self._send_json(404, {"ok": False, "error": "not found"})

    def _session(self, query: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            self._send_json(503, {"ok": False, "error": "OPENAI_API_KEY is not configured"})
            return
        try:
            sdp = self._read_body().decode("utf-8")
            if not sdp.strip():
                raise ValueError("SDP offer is empty")
            query_values = parse_qs(query)
            live_mode = query_values.get("live", ["0"])[-1] == "1"
            doc_mode = query_values.get("mode", [""])[-1] == "doc"
            if doc_mode:
                title, lines = sanitize_document_title(query_values.get("title", [""])[-1]), []
            else:
                title, lines = ("", []) if live_mode else _parse_exercise(query)
        except OverflowError as error:
            self._send_json(413, {"ok": False, "error": str(error)})
            return
        except (UnicodeDecodeError, ValueError) as error:
            self._send_json(400, {"ok": False, "error": str(error)})
            return

        model = os.getenv("GERALD_MODEL", "gpt-realtime-2").strip() or "gpt-realtime-2"
        session = build_session_config(model, title, lines, live_mode, doc_mode)
        body, content_type = build_multipart(sdp, session)
        request = Request(
            OPENAI_REALTIME_CALLS,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": content_type,
                "Accept": "application/sdp",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                self._send_bytes(response.status, response.read(), "text/plain; charset=utf-8")
        except HTTPError as error:
            response_body = error.read()
            logger.warning(
                "OpenAI Realtime call failed (%s): %s",
                error.code,
                response_body.decode("utf-8", "replace"),
            )
            self._send_bytes(error.code, response_body, "text/plain; charset=utf-8")
        except URLError as error:
            logger.warning("OpenAI Realtime call failed: %s", error.reason)
            self._send_json(502, {"ok": False, "error": "Realtime service unavailable"})

    def _plot(self) -> None:
        try:
            payload = json.loads(self._read_body(128_000))
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            image_size = payload.pop("image_size", None)
            occupied_boxes = payload.pop("occupied_boxes", [])
            if (
                not isinstance(image_size, list)
                or len(image_size) != 2
                or any(type(value) is not int or value <= 0 or value > 8192 for value in image_size)
            ):
                raise ValueError("image_size must contain positive integer width and height")
            if (
                not isinstance(occupied_boxes, list)
                or len(occupied_boxes) > 100
                or any(
                    not isinstance(box, list)
                    or len(box) != 4
                    or any(not isinstance(value, (int, float)) for value in box)
                    for box in occupied_boxes
                )
            ):
                raise ValueError("occupied_boxes must contain at most 100 [x, y, w, h] boxes")
            command, result = build_plot(payload, tuple(image_size), occupied_boxes)
        except OverflowError as error:
            self._send_json(413, {"ok": False, "error": str(error)})
            return
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"ok": False, "error": str(error)})
            return
        result["curves"] = [
            {
                "expr": curve.expr,
                "label": curve.label,
                "samples": [list(sample) if sample is not None else None for sample in curve.samples],
            }
            for curve in command.curves
        ]
        result["x_range"] = [command.x_min, command.x_max]
        result["y_range"] = [command.y_min, command.y_max]
        result["points"] = [
            {
                "label": point.label,
                "x": point.x,
                "y": point.y,
                "x_img": point.x_img,
                "y_img": point.y_img,
            }
            for point in command.points
        ]
        self._send_json(200, result)


def make_server(
    host: str = "127.0.0.1", port: int = 8765, public_hosts: tuple[str, ...] = ()
) -> WebVoiceHTTPServer:
    return WebVoiceHTTPServer((host, port), WebVoiceHandler, host=host, public_hosts=public_hosts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the voice-enabled Gerald teaching board")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--public-host",
        action="append",
        default=[h for h in os.getenv("GERALD_WEB_PUBLIC_HOSTS", "").split(",") if h],
        help="extra Host/Origin allowed, e.g. the HTTPS tunnel hostname (repeatable)",
    )
    args = parser.parse_args()
    if not WEB_ROOT.is_dir():
        parser.error(f"built web board not found at {WEB_ROOT}; run (cd web && npm run build)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = make_server(args.host, args.port, tuple(args.public_host))
    logger.info("Serving the Gerald board at http://%s:%d/", args.host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
