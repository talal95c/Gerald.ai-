"""Run real web Realtime scenarios and audit their transcripts and visible effects."""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import tempfile
import wave
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from gerald import USER_AGENT
from gerald.config import load_settings

HERE = Path(__file__).parent
SCENARIOS_PATH = HERE / "scenarios.json"
RUBRIC_PATH = HERE / "rubric.md"
VIEWPORT = {"width": 1440, "height": 900}
JUDGE_MODEL = "gpt-5.5"

ENGLISH_TOKENS = (
    "the", "and", "you", "your", "is", "are", "this", "that", "let's", "now",
    "here", "we", "with", "what", "great", "first", "then", "next", "it's",
    "i'm", "don't", "can", "will", "just", "click", "step", "okay", "right",
)
ENGLISH_RE = re.compile(r"\b(?:" + "|".join(re.escape(token) for token in ENGLISH_TOKENS) + r")\b", re.I)
QUOTED_SPAN_RE = re.compile(
    r"«([^»]*)»|“([^”]*)”|\"([^\"\n]*)\"|(?<!\w)'([^'\n]*)'(?!\w)"
)
WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)
FALSE_SUCCESS_RE = re.compile(
    r"(?i)\b(j'ai|je t'ai|c'est|voilà)\b.{0,40}\b"
    r"(tracé|écrit|dessiné|souligné|entouré|affiché|effacé)"
)
ERASE_REFUSAL_PATTERNS = (
    re.compile(
        r"(?i)(je ne peux pas|je peux pas|je n'ai pas (la possibilité|accès|d'outil)|"
        r"impossible|pas en mesure|ne m'est pas possible).{0,80}"
        r"(effac|supprim|enlev|retir|gomm)"
    ),
    re.compile(
        r"(?i)(effac|supprim|enlev|retir|gomm).{0,60}"
        r"(pas possible|ne peux pas|peux pas|impossible)"
    ),
)
ANNOTATION_TOOLS = {"underline", "circle", "arrow", "highlight", "point", "note", "tip"}

INIT_SCRIPT = r"""(() => {
  window.__pcs = [];
  window.__voiceEventLog = [];
  window.__voiceEvents = [];
  const sanitize = value => {
    const copy = JSON.parse(JSON.stringify(value));
    const stripImages = content => {
      if (!Array.isArray(content)) return;
      for (const part of content) {
        if (part && part.type === "input_image") {
          part.image_url = "[image payload omitted; see screenshots]";
        }
      }
    };
    if (copy.item?.content) stripImages(copy.item.content);
    if (Array.isArray(copy.response?.output)) {
      for (const item of copy.response.output) stripImages(item.content);
    }
    return copy;
  };
  const record = (direction, data) => {
    if (typeof data !== "string") return;
    try {
      const event = JSON.parse(data);
      const safe = sanitize(event);
      window.__voiceEventLog.push({
        direction,
        at_ms: Math.round(performance.now()),
        type: safe.type || null,
        event: safe
      });
      if (direction === "server") window.__voiceEvents.push(safe.type || null);
    } catch (_) {}
  };
  const watchChannel = channel => {
    channel.addEventListener("message", event => record("server", event.data));
    const send = channel.send.bind(channel);
    channel.send = data => {
      record("client", data);
      return send(data);
    };
    return channel;
  };
  const Native = window.RTCPeerConnection;
  window.RTCPeerConnection = new Proxy(Native, {
    construct(target, args) {
      const pc = Reflect.construct(target, args);
      window.__pcs.push(pc);
      pc.addEventListener("datachannel", event => watchChannel(event.channel));
      const create = pc.createDataChannel.bind(pc);
      pc.createDataChannel = (...channelArgs) => watchChannel(create(...channelArgs));
      return pc;
    }
  });
})();"""

DOM_STATE_SCRIPT = r"""() => {
  const box = rect => ({x: rect.x, y: rect.y, w: rect.width, h: rect.height});
  const addOffset = (rect, offset) => ({
    x: rect.x + offset.x, y: rect.y + offset.y, w: rect.w, h: rect.h
  });
  const valid = rect => rect && rect.w > 0 && rect.h > 0;
  const frameElement = document.querySelector('iframe[title="Tableau"]');
  const frameRect = frameElement?.getBoundingClientRect();
  let boardWindow = null;
  try { boardWindow = frameElement?.contentWindow || null; } catch (_) {}
  const boardApi = boardWindow?.geraldBoard;
  const boardActive = !!boardApi && !!frameRect && frameRect.width > 0 && frameRect.height > 0;
  const offset = boardActive ? {x: frameRect.x, y: frameRect.y} : {x: 0, y: 0};
  const tdApi = window.geraldTD;
  let activeElements = [];
  try {
    activeElements = boardActive ? boardApi.elements() : (tdApi?.elements() || []);
  } catch (_) {}
  const visibleElements = activeElements.map(element => ({
    id: element.id,
    text: element.text || "",
    rect: boardActive ? addOffset(element.rect, offset) : element.rect,
    surface: boardActive ? "board" : "td"
  }));
  const geometry = [];
  const push = (kind, key, rect) => {
    if (valid(rect)) geometry.push({kind, key, rect});
  };
  for (const element of activeElements) {
    const rect = boardActive ? addOffset(element.rect, offset) : element.rect;
    if (element.id >= 10000) push("ink", `ink-${element.id}`, rect);
    else push("td_text", `visible-${element.id}`, rect);
  }
  if (boardActive) {
    for (const element of boardWindow.document.querySelectorAll("[data-gerald-text-id]")) {
      const katex = [...element.querySelectorAll(".katex")]
        .map(node => node.getBoundingClientRect())
        .filter(rect => rect.width > 0 && rect.height > 0);
      if (katex.length) {
        const left = Math.min(...katex.map(rect => rect.x));
        const top = Math.min(...katex.map(rect => rect.y));
        const right = Math.max(...katex.map(rect => rect.right));
        const bottom = Math.max(...katex.map(rect => rect.bottom));
        push("gerald_text", `gerald-text-${element.dataset.geraldTextId}`,
          {x: left + offset.x, y: top + offset.y, w: right - left, h: bottom - top});
      } else {
        push("gerald_text", `gerald-text-${element.dataset.geraldTextId}`,
          addOffset(box(element.getBoundingClientRect()), offset));
      }
    }
  }
  const collectNotes = (doc, prefix, noteOffset) => {
    for (const node of doc.querySelectorAll(
      '[data-gerald-mark-kind="note"],[data-gerald-mark-kind="tip"]'
    )) {
      const rect = box(node.getBoundingClientRect());
      const kind = node.getAttribute("data-gerald-mark-kind");
      push("note_tip", `${prefix}-${kind}-${geometry.length}`, addOffset(rect, noteOffset));
    }
  };
  collectNotes(document, "td", {x: 0, y: 0});
  if (boardApi) collectNotes(boardWindow.document, "board", offset);
  const activeDoc = boardActive ? boardWindow.document : document;
  const layer = activeDoc.querySelector(boardActive ? ".gerald-marks" : ".td-mark-layer");
  const markRoot = layer?.matches("svg") ? layer : layer?.querySelector("svg");
  const boardTexts = boardApi
    ? boardWindow.document.querySelectorAll("[data-gerald-text-id]").length
    : 0;
  const inkCount = boardApi
    ? boardApi.elements().filter(element => element.id >= 10000).length
    : 0;
  return {
    board_active: boardActive,
    visible_elements: visibleElements,
    geometry,
    gerald_texts: boardTexts,
    gerald_marks: markRoot?.children.length || 0,
    arrows: activeDoc.querySelectorAll('[data-gerald-mark-kind="arrow"]').length,
    ink_clusters: inkCount
  };
}"""


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_silence(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\0\0" * 48000)


def formula_paths(y: int, corrected: bool = False) -> list[list[tuple[int, int]]]:
    paths: list[list[tuple[int, int]]] = []

    def add(x: int, *points: tuple[int, int]) -> None:
        paths.append([(x + point[0], y + point[1]) for point in points])

    add(165, (24, 0), (48, 48), (0, 48), (24, 0))
    add(177, (0, 34), (24, 34))
    add(245, (0, 18), (42, 18))
    add(245, (0, 33), (42, 33))
    add(317, (6, 8), (12, 1), (33, 1), (42, 9), (38, 16), (6, 42), (42, 42))
    add(367, (41, 1), (8, 1), (6, 20), (31, 20), (41, 27), (37, 42), (6, 42))
    if corrected:
        add(441, (0, 24), (46, 24))
    else:
        add(441, (0, 24), (46, 24))
        add(464, (23, 1), (23, 47))
    add(517, (6, 8), (12, 1), (33, 1), (42, 9), (38, 16), (6, 42), (42, 42))
    add(567, (38, 42), (38, 1), (4, 28), (42, 28))
    add(641, (0, 18), (42, 18))
    add(641, (0, 33), (42, 33))
    if corrected:
        add(713, (8, 9), (20, 1), (20, 42))
        add(720, (7, 42), (35, 42))
    else:
        add(713, (38, 42), (38, 1), (4, 28), (42, 28))
        add(763, (40, 18), (40, 8), (33, 1), (13, 1), (5, 8),
            (5, 18), (13, 25), (31, 25), (40, 18))
        add(803, (40, 18), (37, 42))
    return paths


def draw_formula(page: Page, corrected: bool = False, y: int = 255) -> dict[str, Any]:
    board = page.frame_locator('iframe[title="Tableau"]')
    canvas = board.locator("canvas").first
    bounds = canvas.bounding_box()
    if not bounds:
        raise RuntimeError("The board canvas is unavailable")
    paths = formula_paths(y, corrected=corrected)
    for path in paths:
        page.mouse.move(bounds["x"] + path[0][0], bounds["y"] + path[0][1])
        page.mouse.down()
        for x, point_y in path[1:]:
            page.mouse.move(bounds["x"] + x, bounds["y"] + point_y, steps=3)
        page.mouse.up()
        page.wait_for_timeout(45)
    formula = "Δ = 25 − 24 = 1" if corrected else "Δ = 25 + 24 = 49"
    return {
        "path_count": len(paths),
        "formula": formula,
        "origin": [bounds["x"], bounds["y"]],
        "top": y,
        "input_method": "Playwright mouse move/down/up on the board canvas",
    }


def surface_url(base: str, surface: str) -> str:
    paths = {
        "td": "/td.html?voice=1&demo=1",
        "board": "/td.html?voice=1&demo=1",
        "board-live": "/td.html?voice=1&demo=1&live=1",
        "paint": "/td.html?voice=1&app=paint",
    }
    return f"{base.rstrip('/')}{paths[surface]}"


def get_board_frame(page: Page):
    return next((frame for frame in page.frames if "/board.html" in frame.url), None)


def wait_for_board(page: Page) -> None:
    page.locator('iframe[title="Tableau"]').wait_for(state="visible", timeout=15000)
    frame = get_board_frame(page)
    if frame is None:
        raise RuntimeError("The board iframe did not load")
    frame.wait_for_function("() => !!window.geraldBoard", timeout=15000)
    frame.locator("canvas").first.wait_for(state="visible", timeout=15000)


def connect_and_mute(page: Page) -> None:
    page.get_by_role("button", name="Parler à Gerald").click(timeout=15000)
    page.wait_for_function(
        "() => window.__pcs?.length === 1 && window.__pcs[0].connectionState === 'connected'",
        timeout=90000,
    )
    page.wait_for_function(
        "() => window.__geraldLog?.some(entry => entry.type === 'session_updated')",
        timeout=60000,
    )
    mute_typed_mic(page)


def mute_typed_mic(page: Page) -> None:
    mic = page.locator("button.td-mic")
    label = mic.get_attribute("aria-label")
    if label == "Couper le micro":
        mic.click()
    elif label != "Activer le micro":
        raise RuntimeError(f"Cannot mute fake mic; mic state is {label!r}")
    page.wait_for_function(
        """() => {
          const track = window.__pcs?.[0]?.getSenders().find(sender => sender.track)?.track;
          return document.querySelector('.td-mic')?.getAttribute('aria-label') === 'Activer le micro'
            && track && !track.enabled;
        }""",
        timeout=10000,
    )


def collect_dom_state(page: Page) -> dict[str, Any]:
    return page.evaluate(DOM_STATE_SCRIPT)


def collect_realtime_events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.__voiceEventLog || []")


def collect_app_events(page: Page) -> list[dict[str, Any]]:
    return page.evaluate("() => window.__geraldLog || []")


def wait_for_complete_turn(page: Page, turn: int, timeout: int = 180000) -> None:
    page.wait_for_function(
        """number => {
          const state = window.__geraldState;
          const log = window.__geraldLog || [];
          const done = log.filter(entry => entry.type === "response_done" && entry.turn === number);
          return state && state.settledTurn >= number && state.pendingTools === 0 &&
            state.responsesCreated === state.responsesDone && done.length > 0 &&
            Date.now() - state.settledAt >= 1500;
        }""",
        arg=turn,
        timeout=timeout,
    )


def send_turn(
    page: Page,
    question: str,
    visible_elements: list[dict[str, Any]],
    before_state: dict[str, Any],
) -> dict[str, Any]:
    mute_typed_mic(page)
    field = page.locator('input[data-gerald-id="30"]')
    field.fill(question)
    field.press("Enter")
    page.wait_for_function(
        "text => window.__geraldLog?.some(entry => entry.type === 'user' && entry.text === text)",
        arg=question,
        timeout=10000,
    )
    turn = page.evaluate(
        "text => window.__geraldLog.filter(entry => entry.type === 'user' && entry.text === text).at(-1).turn",
        question,
    )
    settled = True
    wait_error = None
    try:
        wait_for_complete_turn(page, turn)
    except PlaywrightTimeoutError as error:
        settled = False
        wait_error = str(error)
    frame = get_board_frame(page)
    if frame is not None and frame.evaluate("() => !!window.geraldBoard"):
        try:
            frame.evaluate("() => window.geraldBoard.waitForAnimations()")
        except Exception:
            pass
    page.wait_for_timeout(100)
    app_events = collect_app_events(page)
    entries = [entry for entry in app_events if entry.get("turn") == turn]
    result = {
        "turn": turn,
        "question": question,
        "settled": settled,
        "wait_error": wait_error,
        "visible_elements": visible_elements,
        "before_state": before_state,
        "after_state": collect_dom_state(page),
        "transcripts": [
            {"response_id": entry.get("response_id"), "text": entry.get("text", "")}
            for entry in entries
            if entry.get("type") == "transcript"
        ],
        "tool_calls": [entry for entry in entries if entry.get("type") == "tool_call"],
        "tool_results": [entry for entry in entries if entry.get("type") == "tool_result"],
        "responses": [
            entry for entry in entries if entry.get("type") in {"response_created", "response_done"}
        ],
    }
    return result


def collect_visible_elements(page: Page) -> list[dict[str, Any]]:
    state = collect_dom_state(page)
    return state["visible_elements"]


def rectangle_xyxy(rect: dict[str, float]) -> tuple[float, float, float, float]:
    return rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"]


def append_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for value in values:
            output.write(json.dumps(value, ensure_ascii=False) + "\n")


def run_attempt(
    browser,
    scenario: dict[str, Any],
    repetition: int,
    base: str,
    attempt_dir: Path,
) -> dict[str, Any]:
    attempt_dir.mkdir(parents=True, exist_ok=False)
    screenshot_dir = attempt_dir / "screenshots"
    screenshot_dir.mkdir()
    context = browser.new_context(viewport=VIEWPORT, permissions=["microphone"])
    context.add_init_script(INIT_SCRIPT)
    page = context.new_page()
    browser_errors: list[str] = []
    harness_events: list[dict[str, Any]] = []
    page.on("pageerror", lambda error: browser_errors.append(str(error)))
    page.on(
        "console",
        lambda message: browser_errors.append(message.text) if message.type == "error" else None,
    )
    turns: list[dict[str, Any]] = []
    status = "started"
    try:
        page.goto(surface_url(base, scenario["surface"]), wait_until="networkidle")
        if scenario["surface"] == "board":
            page.get_by_role("button", name="Ouvrir au tableau →").first.click()
        if scenario["surface"] in {"board", "board-live"}:
            wait_for_board(page)
        if scenario["surface"] == "paint":
            page.locator('iframe[title="miniPaint"]').wait_for(state="visible", timeout=15000)
        harness_events.append({"type": "surface_ready", "surface": scenario["surface"]})
        connect_and_mute(page)
        harness_events.append({"type": "session_updated"})
        harness_events.append({"type": "fake_mic_disabled"})

        setup_results = []
        if scenario.get("setup"):
            board = page.frame_locator('iframe[title="Tableau"]')
            board.get_by_role("button", name="Stylo", exact=True).click()
            for setup in scenario["setup"]:
                if setup.get("ink") not in {"wrong", "right"}:
                    raise ValueError(f"Unknown ink setup: {setup.get('ink')!r}")
                result = draw_formula(
                    page,
                    corrected=setup["ink"] == "right",
                    y=int(setup.get("y", 255)),
                )
                setup_results.append(result)
        save_json(attempt_dir / "setup.json", setup_results)
        page.screenshot(path=str(screenshot_dir / "initial.png"))
        harness_events.append({"type": "setup_complete", "ink_setups": setup_results})

        for index, question in enumerate(scenario["turns"], start=1):
            before_state = collect_dom_state(page)
            visible_elements = collect_visible_elements(page)
            turn = send_turn(page, question, visible_elements, before_state)
            turn["screenshot"] = f"screenshots/after-turn-{index:02d}.png"
            page.screenshot(path=str(attempt_dir / turn["screenshot"]))
            turns.append(turn)
            harness_events.append({
                "type": "turn_complete",
                "turn": turn["turn"],
                "question": question,
                "settled": turn["settled"],
            })
            if not turn["settled"]:
                status = "incomplete"
                break
        if status == "started":
            status = "complete" if len(turns) == len(scenario["turns"]) else "incomplete"

        realtime_events = collect_realtime_events(page)
        app_events = collect_app_events(page)
        save_json(attempt_dir / "browser-errors.json", browser_errors)
        save_json(attempt_dir / "realtime-events.json", realtime_events)
        save_json(attempt_dir / "app-events.json", app_events)
        raw_usage = sum_usage(realtime_events)
        attempt = {
            "scenario_id": scenario["id"],
            "repetition": repetition,
            "surface": scenario["surface"],
            "status": status,
            "setup": setup_results,
            "turns": turns,
            "realtime_events": realtime_events,
            "app_events": app_events,
            "harness_events": harness_events,
            "browser_errors": browser_errors,
            "realtime_usage": raw_usage,
            "final_screenshot": turns[-1]["screenshot"] if turns else "screenshots/initial.png",
        }
        append_jsonl(
            attempt_dir / "events.jsonl",
            [
                *({"source": "harness", **event} for event in harness_events),
                *({"source": "realtime", **event} for event in realtime_events),
                *({"source": "app", "event": event} for event in app_events),
            ],
        )
        return attempt
    except Exception as error:
        status = "error"
        try:
            page.screenshot(path=str(screenshot_dir / "failure.png"))
        except Exception:
            pass
        realtime_events = collect_realtime_events(page)
        app_events = collect_app_events(page)
        attempt = {
            "scenario_id": scenario["id"],
            "repetition": repetition,
            "surface": scenario["surface"],
            "status": status,
            "error": repr(error),
            "setup": [],
            "turns": turns,
            "realtime_events": realtime_events,
            "app_events": app_events,
            "harness_events": harness_events,
            "browser_errors": browser_errors,
            "realtime_usage": sum_usage(realtime_events),
            "final_screenshot": "screenshots/failure.png",
        }
        append_jsonl(
            attempt_dir / "events.jsonl",
            [
                *({"source": "harness", **event} for event in harness_events),
                *({"source": "realtime", **event} for event in realtime_events),
                *({"source": "app", "event": event} for event in app_events),
            ],
        )
        save_json(attempt_dir / "failure.json", {"error": repr(error), "status": status})
        return attempt
    finally:
        context.close()


def sum_usage(realtime_events: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)

    def visit(value: Any, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            totals[prefix] += value

    for record in realtime_events:
        event = record.get("event", {})
        if record.get("direction") == "server" and event.get("type") == "response.done":
            usage = event.get("response", {}).get("usage")
            if isinstance(usage, dict):
                visit(usage)
    return dict(sorted(totals.items()))


def transcript_entries(attempt: dict[str, Any]) -> list[dict[str, Any]]:
    app_events = attempt.get("app_events", [])
    normalized = [
        {
            "turn": event.get("turn"),
            "response_id": event.get("response_id"),
            "text": event.get("text", ""),
        }
        for event in app_events
        if event.get("type") == "transcript"
    ]
    if normalized:
        return normalized
    response_turns = {
        event.get("response_id"): event.get("turn")
        for event in app_events
        if event.get("type") == "response_done"
    }
    raw = []
    for record in attempt.get("realtime_events", []):
        event = record.get("event", {})
        if record.get("direction") == "server" and event.get("type") in {
            "response.output_audio_transcript.done",
            "response.audio_transcript.done",
        }:
            response_id = event.get("response_id")
            raw.append({
                "turn": response_turns.get(response_id),
                "response_id": response_id,
                "text": event.get("transcript", ""),
            })
    return raw


def parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {"raw": value}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def tool_activity(attempt: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    app_events = attempt.get("app_events", [])
    calls: list[dict[str, Any]] = []
    call_by_id: dict[str, dict[str, Any]] = {}
    for order, event in enumerate(app_events):
        if event.get("type") != "tool_call":
            continue
        call = {
            "call_id": event.get("call_id"),
            "name": event.get("name"),
            "args": parse_arguments(event.get("args", event.get("arguments"))),
            "turn": event.get("turn"),
            "order": order,
        }
        calls.append(call)
        if call["call_id"]:
            call_by_id[str(call["call_id"])] = call

    raw_outputs: dict[str, dict[str, Any]] = {}
    raw_order: dict[str, int] = {}
    for index, record in enumerate(attempt.get("realtime_events", [])):
        event = record.get("event", {})
        item = event.get("item", {})
        if (
            record.get("direction") == "client"
            and event.get("type") == "conversation.item.create"
            and item.get("type") == "function_call_output"
        ):
            call_id = str(item.get("call_id", ""))
            try:
                result = json.loads(item.get("output") or "{}")
            except json.JSONDecodeError:
                result = {"ok": False, "error": item.get("output", "Invalid tool output")}
            raw_outputs[call_id] = result if isinstance(result, dict) else {"value": result}
            raw_order[call_id] = index

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for order, event in enumerate(app_events):
        if event.get("type") != "tool_result":
            continue
        call_id = str(event.get("call_id", ""))
        call = call_by_id.get(call_id, {})
        result = raw_outputs.get(call_id)
        if result is None:
            result = event.get("result")
        if not isinstance(result, dict):
            result = {"ok": event.get("ok"), "error": event.get("error")}
        record = {
            "call_id": call_id or None,
            "name": event.get("name") or call.get("name"),
            "args": parse_arguments(event.get("args", call.get("args"))),
            "turn": event.get("turn", call.get("turn")),
            "result": result,
            "ok": result.get("ok") is True,
            "error": result.get("error") or event.get("error"),
            "order": order,
            "raw_order": raw_order.get(call_id),
        }
        results.append(record)
        if call_id:
            seen.add(call_id)
    for call_id, result in raw_outputs.items():
        if call_id in seen:
            continue
        call = call_by_id.get(call_id, {})
        results.append({
            "call_id": call_id,
            "name": call.get("name"),
            "args": call.get("args", {}),
            "turn": call.get("turn"),
            "result": result,
            "ok": result.get("ok") is True,
            "error": result.get("error"),
            "order": raw_order.get(call_id, len(app_events)),
            "raw_order": raw_order.get(call_id),
        })
    results.sort(key=lambda result: result["order"])
    return calls, results


def tool_family(name: str | None) -> str | None:
    if name in ANNOTATION_TOOLS:
        return "annotation"
    if name == "plot":
        return "plot"
    return name


def check_tool_errors(attempt: dict[str, Any]) -> dict[str, Any]:
    calls, results = tool_activity(attempt)
    errors = []
    for failed in results:
        if failed["result"].get("ok") is not False:
            continue
        later = [
            result for result in results
            if result["ok"]
            and result["turn"] == failed["turn"]
            and failed["turn"] is not None
            and result["order"] > failed["order"]
        ]
        recovery = next(
            (
                result for result in later
                if tool_family(result["name"]) == tool_family(failed["name"])
            ),
            None,
        )
        if recovery is None and failed["name"] == "plot":
            opened = next(
                (result for result in later if result["name"] == "open_board"),
                None,
            )
            if opened:
                recovery = next(
                    (
                        result for result in later
                        if result["name"] == "plot" and result["order"] > opened["order"]
                    ),
                    None,
                )
        errors.append({
            "turn": failed["turn"],
            "call_id": failed["call_id"],
            "name": failed["name"],
            "args": failed["args"],
            "error": failed["error"],
            "recovered": recovery is not None,
            "recovered_by": (
                {"name": recovery["name"], "call_id": recovery["call_id"]}
                if recovery else None
            ),
        })
    unrecovered = [error for error in errors if not error["recovered"]]
    return {
        "passed": not unrecovered,
        "details": {"errors": errors, "unrecovered": unrecovered, "calls": calls},
    }


def session_tool_names(attempt: dict[str, Any]) -> list[str]:
    outgoing: list[list[Any]] = []
    updated: list[list[Any]] = []
    for record in attempt.get("realtime_events", []):
        event = record.get("event", {})
        if record.get("direction") == "client" and event.get("type") == "session.update":
            tools = event.get("session", {}).get("tools")
            if isinstance(tools, list):
                outgoing.append(tools)
        if record.get("direction") == "server" and event.get("type") == "session.updated":
            tools = event.get("session", {}).get("tools")
            if isinstance(tools, list):
                updated.append(tools)
    source = updated[-1] if updated else (outgoing[-1] if outgoing else [])
    names = []
    for tool in source:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name") or tool.get("function", {}).get("name")
        if name:
            names.append(str(name))
    return names


def check_unknown_tools(attempt: dict[str, Any]) -> dict[str, Any]:
    calls, _ = tool_activity(attempt)
    allowed = session_tool_names(attempt)
    unknown = [call for call in calls if call["name"] not in allowed]
    return {
        "passed": not unknown,
        "details": {
            "session_tools": allowed,
            "unknown_calls": [
                {"name": call["name"], "args": call["args"], "turn": call["turn"]}
                for call in unknown
            ],
        },
    }


def clean_for_language(text: str, labels: list[str]) -> str:
    def strip_short_quote(match: re.Match[str]) -> str:
        quoted = next(group for group in match.groups() if group is not None)
        return " " if len(WORD_RE.findall(quoted)) <= 6 else match.group(0)

    cleaned = QUOTED_SPAN_RE.sub(strip_short_quote, text)
    for label in sorted({label for label in labels if label}, key=len, reverse=True):
        cleaned = cleaned.replace(label, " ")
    return cleaned


def check_language(attempt: dict[str, Any]) -> dict[str, Any]:
    visible_by_turn = {
        turn.get("turn"): [
            str(element.get("text", ""))
            for element in turn.get("visible_elements", [])
        ]
        for turn in attempt.get("turns", [])
    }
    offending = []
    for transcript in transcript_entries(attempt):
        text = transcript.get("text", "")
        cleaned = clean_for_language(text, visible_by_turn.get(transcript.get("turn"), []))
        tokens = [match.group(0) for match in ENGLISH_RE.finditer(cleaned)]
        if len(tokens) >= 2:
            sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
                if sentence.strip()
                and ENGLISH_RE.search(sentence)
            ]
            offending.append({
                "turn": transcript.get("turn"),
                "response_id": transcript.get("response_id"),
                "tokens": tokens,
                "sentence": sentences,
                "transcript": text,
            })
    return {"passed": not offending, "details": {"offending_transcripts": offending}}


def check_erase_refusal(attempt: dict[str, Any]) -> dict[str, Any]:
    matches = []
    for transcript in transcript_entries(attempt):
        for pattern in ERASE_REFUSAL_PATTERNS:
            match = pattern.search(transcript.get("text", ""))
            if match:
                matches.append({
                    "turn": transcript.get("turn"),
                    "response_id": transcript.get("response_id"),
                    "match": match.group(0),
                    "transcript": transcript.get("text", ""),
                })
    return {"passed": not matches, "details": {"refusals": matches}}


def check_false_success(attempt: dict[str, Any], tool_check: dict[str, Any]) -> dict[str, Any]:
    transcripts = transcript_entries(attempt)
    failures = []
    for error in tool_check["details"]["unrecovered"]:
        for transcript in transcripts:
            if transcript.get("turn") != error.get("turn"):
                continue
            match = FALSE_SUCCESS_RE.search(transcript.get("text", ""))
            if match:
                failures.append({
                    "turn": transcript.get("turn"),
                    "tool": error.get("name"),
                    "error": error.get("error"),
                    "phrase": match.group(0),
                    "transcript": transcript.get("text", ""),
                })
    return {"passed": not failures, "details": {"false_successes": failures}}


def intersection_area(left: dict[str, float], right: dict[str, float]) -> float:
    width = max(0.0, min(left["x"] + left["w"], right["x"] + right["w"]) - max(left["x"], right["x"]))
    height = max(0.0, min(left["y"] + left["h"], right["y"] + right["h"]) - max(left["y"], right["y"]))
    return width * height


def overlap_pairs(geometry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [item for item in geometry if item["kind"] in {"gerald_text", "note_tip"}]
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        for other in geometry:
            if candidate["key"] == other["key"]:
                continue
            area = intersection_area(candidate["rect"], other["rect"])
            if area <= 16:
                continue
            pair_key = tuple(sorted((candidate["key"], other["key"])))
            pairs[pair_key] = {
                "left": candidate,
                "right": other,
                "intersection_area": area,
            }
    return list(pairs.values())


def check_overlap(attempt: dict[str, Any], attempt_dir: Path) -> dict[str, Any]:
    overlaps = []
    for index, turn in enumerate(attempt.get("turns", []), start=1):
        geometry = turn.get("after_state", {}).get("geometry", [])
        pairs = overlap_pairs(geometry)
        if pairs:
            outline_path = attempt_dir / "screenshots" / f"after-turn-{index:02d}-overlap.png"
            page_image = attempt_dir / turn["screenshot"]
            image = Image.open(page_image).convert("RGB")
            draw = ImageDraw.Draw(image)
            for pair in pairs:
                draw.rectangle(rectangle_xyxy(pair["left"]["rect"]), outline=(255, 0, 0), width=4)
                draw.rectangle(rectangle_xyxy(pair["right"]["rect"]), outline=(255, 145, 0), width=4)
            image.save(outline_path)
            overlaps.append({
                "turn": turn.get("turn"),
                "pairs": pairs,
                "screenshot": str(outline_path.relative_to(attempt_dir)),
            })
    return {"passed": not overlaps, "details": {"overlaps": overlaps}}


def check_erase_effect(scenario: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    expected = scenario.get("expect") or {}
    after_turn = expected.get("after_turn")
    turns = attempt.get("turns", [])
    if not isinstance(after_turn, int) or after_turn < 1 or after_turn > len(turns):
        return {
            "passed": False,
            "details": {"error": "The expected after_turn has no captured DOM state."},
        }
    turn = turns[after_turn - 1]
    after = turn.get("after_state", {})
    before = turn.get("before_state", {})
    actual = {
        "gerald_texts": after.get("gerald_texts"),
        "gerald_marks": after.get("gerald_marks"),
        "arrows": after.get("arrows"),
        "ink_clusters": after.get("ink_clusters"),
        "ink_clusters_unchanged": (
            after.get("ink_clusters") == before.get("ink_clusters")
        ),
    }
    comparisons = {
        key: {"expected": value, "actual": actual.get(key), "passed": actual.get(key) == value}
        for key, value in expected.items()
        if key != "after_turn"
    }
    return {
        "passed": all(item["passed"] for item in comparisons.values()),
        "details": {"after_turn": after_turn, "comparisons": comparisons, "actual": actual},
    }


def judge_attempt(
    scenario: dict[str, Any],
    attempt: dict[str, Any],
    attempt_dir: Path,
    rubric: str,
    api_key: str,
) -> dict[str, Any]:
    turns = []
    for index, turn in enumerate(attempt.get("turns", []), start=1):
        calls = [
            {
                "name": call.get("name"),
                "args": parse_arguments(call.get("args", call.get("arguments"))),
                "call_id": call.get("call_id"),
            }
            for call in turn.get("tool_calls", [])
        ]
        outputs = [
            {
                "name": result.get("name"),
                "args": parse_arguments(result.get("args")),
                "call_id": result.get("call_id"),
                "result": result.get("result"),
                "ok": result.get("ok"),
                "error": result.get("error"),
            }
            for result in turn.get("tool_results", [])
        ]
        turns.append({
            "turn": index,
            "learner_turn": turn.get("question"),
            "transcripts": turn.get("transcripts", []),
            "tool_calls": calls,
            "tool_outputs": outputs,
            "visible_elements": turn.get("visible_elements", []),
        })
    screenshot = attempt_dir / attempt["final_screenshot"]
    image = Image.open(screenshot).convert("RGB")
    image.thumbnail((1440, 900))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    user_content = [
        {
            "type": "input_text",
            "text": json.dumps({
                "ground_truth": scenario.get("ground_truth"),
                "turns": turns,
                "final_screenshot": "The attached image is the final visible state.",
            }, ensure_ascii=False, indent=2),
        },
        {
            "type": "input_image",
            "image_url": "data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    ]
    criterion = {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "enum": [0, 1, 2]},
            "why": {"type": "string"},
        },
        "required": ["score", "why"],
        "additionalProperties": False,
    }
    criteria = ["grounded", "honesty", "language", "pedagogy"]
    schema = {
        "type": "object",
        "properties": {
            **{name: criterion for name in criteria},
            "worst_issue": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": [*criteria, "worst_issue", "summary"],
        "additionalProperties": False,
    }
    body: dict[str, Any] = {
        "model": JUDGE_MODEL,
        "input": [
            {"role": "system", "content": rubric},
            {"role": "user", "content": user_content},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "web_voice_grade",
                "schema": schema,
                "strict": True,
            }
        },
    }
    if JUDGE_MODEL.startswith("gpt-5"):
        body["reasoning"] = {"effort": "medium"}
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=240) as response:
        payload = json.loads(response.read())
    text = next(
        part["text"]
        for item in payload["output"]
        if item.get("type") == "message"
        for part in item["content"]
        if part.get("type") == "output_text"
    )
    grade = json.loads(text)
    return {
        "passed": grade["grounded"]["score"] >= 2 and grade["honesty"]["score"] >= 2,
        "details": grade,
    }


def check_attempt(
    scenario: dict[str, Any],
    attempt: dict[str, Any],
    attempt_dir: Path,
    no_judge: bool,
    rubric: str,
    api_key: str | None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    tool_check = check_tool_errors(attempt)
    for name in scenario["checks"]:
        if name == "lang":
            results[name] = check_language(attempt)
        elif name == "unknown_tools":
            results[name] = check_unknown_tools(attempt)
        elif name == "tool_errors":
            results[name] = tool_check
        elif name == "false_success":
            results[name] = check_false_success(attempt, tool_check)
        elif name == "erase_refusal":
            results[name] = check_erase_refusal(attempt)
        elif name == "erase_effect":
            results[name] = check_erase_effect(scenario, attempt)
        elif name == "overlap":
            results[name] = check_overlap(attempt, attempt_dir)
        elif name == "judge":
            if no_judge:
                results[name] = {
                    "passed": None,
                    "details": {"skipped": "disabled by --no-judge"},
                }
            elif not api_key:
                results[name] = {
                    "passed": None,
                    "details": {"error": "The judge requires OPENAI_API_KEY."},
                }
            else:
                try:
                    results[name] = judge_attempt(
                        scenario, attempt, attempt_dir, rubric, api_key
                    )
                except Exception as error:
                    results[name] = {
                        "passed": None,
                        "details": {"error": repr(error)},
                    }
        else:
            raise ValueError(f"Unsupported authored check: {name}")
    return results


def write_transcript(
    path: Path,
    attempt: dict[str, Any],
    checks: dict[str, Any],
) -> None:
    lines = [
        f"# {attempt['scenario_id']} — repetition {attempt['repetition']}",
        "",
        f"- Surface: `{attempt['surface']}`",
        f"- Status: **{attempt['status']}**",
        f"- Final screenshot: `{attempt['final_screenshot']}`",
        "",
    ]
    if attempt.get("error"):
        lines.extend([f"Runner error: `{attempt['error']}`", ""])
    for index, turn in enumerate(attempt.get("turns", []), start=1):
        lines.extend([
            f"## Turn {index}",
            "",
            f"**Learner:** {turn.get('question', '')}",
            "",
            f"**Settled:** {turn.get('settled')}",
            "",
            "**Gerald transcripts:**",
            "",
        ])
        transcripts = turn.get("transcripts", [])
        if transcripts:
            lines.extend(f"- {item.get('text', '')}" for item in transcripts)
        else:
            lines.append("- (no final transcript captured)")
        lines.extend(["", "**Tool calls and outputs:**", ""])
        results_by_id = {result.get("call_id"): result for result in turn.get("tool_results", [])}
        calls = turn.get("tool_calls", [])
        if calls:
            for call in calls:
                result = results_by_id.get(call.get("call_id"))
                lines.append(
                    f"- `{call.get('name')}` args `{json.dumps(parse_arguments(call.get('args', call.get('arguments'))), ensure_ascii=False)}`"
                )
                lines.append(
                    f"  - output: `{json.dumps(result.get('result'), ensure_ascii=False) if result else 'not captured'}`"
                )
        else:
            lines.append("- (none)")
        lines.extend(["", f"Screenshot: `{turn.get('screenshot')}`", ""])
    lines.extend(["## Checks", ""])
    for name, result in checks.items():
        status = "SKIPPED" if result["passed"] is None else ("PASS" if result["passed"] else "FAIL")
        lines.append(f"- **{name}: {status}**")
        if result.get("details"):
            lines.append(f"  - `{json.dumps(result['details'], ensure_ascii=False)}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_attempt_outputs(
    attempt_dir: Path,
    attempt: dict[str, Any],
    checks: dict[str, Any],
) -> None:
    attempt["checks"] = checks
    save_json(attempt_dir / "checks.json", {
        "scenario_id": attempt["scenario_id"],
        "repetition": attempt["repetition"],
        "status": attempt["status"],
        "checks": checks,
        "realtime_usage": attempt.get("realtime_usage", {}),
    })
    write_transcript(attempt_dir / "transcript.md", attempt, checks)


def aggregate_usage(attempts: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for attempt in attempts:
        for key, value in attempt.get("realtime_usage", {}).items():
            totals[key] += value
    return dict(sorted(totals.items()))


def write_summary(out: Path, label: str, base: str, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grouped[attempt["scenario_id"]].append(attempt)
    scenario_summaries = []
    for scenario_id, scenario_attempts in grouped.items():
        check_names = list(scenario_attempts[0].get("checks", {}))
        check_summary = {}
        for name in check_names:
            values = [attempt.get("checks", {}).get(name, {}).get("passed") for attempt in scenario_attempts]
            evaluated = [value for value in values if value is not None]
            check_summary[name] = {
                "passed": sum(value is True for value in evaluated),
                "failed": sum(value is False for value in evaluated),
                "skipped": len(values) - len(evaluated),
                "total": len(values),
                "status": (
                    "PASS" if evaluated and all(value is True for value in evaluated)
                    else "FAIL" if any(value is False for value in evaluated)
                    else "N/A"
                ),
            }
        scenario_summaries.append({
            "id": scenario_id,
            "attempts": [
                {
                    "repetition": attempt["repetition"],
                    "status": attempt["status"],
                    "checks": attempt.get("checks", {}),
                }
                for attempt in scenario_attempts
            ],
            "checks": check_summary,
        })
    language_failures = sum(
        attempt.get("checks", {}).get("lang", {}).get("passed") is False
        for attempt in attempts
    )
    erase_refusals = sum(
        attempt.get("checks", {}).get("erase_refusal", {}).get("passed") is False
        for attempt in attempts
    )
    hallucination_failures = sum(
        attempt.get("checks", {}).get("judge", {}).get("passed") is False
        for attempt in attempts
    )
    unrecovered_tool_errors = sum(
        len(attempt.get("checks", {}).get("tool_errors", {}).get("details", {}).get("unrecovered", []))
        for attempt in attempts
    )
    overlap_failures = sum(
        len(attempt.get("checks", {}).get("overlap", {}).get("details", {}).get("overlaps", []))
        for attempt in attempts
    )
    overlap_pairs_total = sum(
        sum(len(turn.get("pairs", [])) for turn in attempt.get("checks", {}).get("overlap", {}).get("details", {}).get("overlaps", []))
        for attempt in attempts
    )
    totals = {
        "language_failures": language_failures,
        "erase_refusals": erase_refusals,
        "overlap_failures": overlap_failures,
        "overlap_pairs": overlap_pairs_total,
        "hallucination_judge_failures": hallucination_failures,
        "unrecovered_tool_errors": unrecovered_tool_errors,
        "realtime_usage": aggregate_usage(attempts),
    }
    summary = {
        "label": label,
        "base": base,
        "created_at": datetime.now().astimezone().isoformat(),
        "attempt_count": len(attempts),
        "scenarios": scenario_summaries,
        "totals": totals,
    }
    save_json(out / "summary.json", summary)

    lines = [
        f"# Web voice audit — {label}",
        "",
        f"- Base URL: `{base}`",
        f"- Attempts: {len(attempts)}",
        "",
        "## Per-scenario checks",
        "",
        "| scenario | check | pass / attempts | status |",
        "|---|---|---:|---|",
    ]
    for scenario in scenario_summaries:
        for check_name, result in scenario["checks"].items():
            lines.append(
                f"| {scenario['id']} | {check_name} | "
                f"{result['passed']} / {result['total']} | {result['status']} |"
            )
    lines.extend([
        "",
        "## Totals",
        "",
        f"- Language failures: **{language_failures}**",
        f"- Erase refusals: **{erase_refusals}**",
        f"- Overlap failures: **{overlap_failures}** turns; **{overlap_pairs_total}** offending pairs",
        f"- Hallucination judge failures: **{hallucination_failures}**",
        f"- Unrecovered tool errors: **{unrecovered_tool_errors}**",
        f"- Realtime usage (sum of `response.done.usage`): "
        f"`{json.dumps(totals['realtime_usage'], ensure_ascii=False, sort_keys=True)}`",
        "",
    ])
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8767")
    parser.add_argument("--label", default="run")
    parser.add_argument("--only", default="")
    parser.add_argument("--reps", type=int, default=None)
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.label):
        parser.error("--label must contain only letters, numbers, dots, underscores, or hyphens")

    spec = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    repetitions = args.reps if args.reps is not None else int(spec.get("repetitions", 1))
    if repetitions < 1:
        parser.error("--reps must be at least 1")
    all_scenarios = spec["scenarios"]
    requested = {item for item in args.only.split(",") if item}
    known_ids = {scenario["id"] for scenario in all_scenarios}
    unknown_ids = requested - known_ids
    if unknown_ids:
        parser.error(f"unknown scenario id(s): {', '.join(sorted(unknown_ids))}")
    scenarios = [
        scenario for scenario in all_scenarios
        if not requested or scenario["id"] in requested
    ]
    if not scenarios:
        parser.error("no scenarios selected")

    output_dir = HERE / "results" / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{args.label}"
    output_dir.mkdir(parents=True, exist_ok=False)
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    api_key = None
    if not args.no_judge and any("judge" in scenario["checks"] for scenario in scenarios):
        api_key = load_settings().api_key
    attempts: list[dict[str, Any]] = []
    base = args.base.rstrip("/")
    with tempfile.TemporaryDirectory(prefix="web-voice-audio-") as temp_dir:
        silence = Path(temp_dir) / "silence.wav"
        write_silence(silence)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--use-fake-device-for-media-stream",
                    "--use-fake-ui-for-media-stream",
                    f"--use-file-for-fake-audio-capture={silence}",
                ],
            )
            try:
                for scenario in scenarios:
                    for repetition in range(1, repetitions + 1):
                        attempt_dir = (
                            output_dir / scenario["id"] / f"rep-{repetition:02d}"
                        )
                        attempt = run_attempt(
                            browser, scenario, repetition, base, attempt_dir
                        )
                        checks = check_attempt(
                            scenario, attempt, attempt_dir, args.no_judge, rubric, api_key
                        )
                        write_attempt_outputs(attempt_dir, attempt, checks)
                        attempts.append(attempt)
                        print(
                            f"{scenario['id']} rep {repetition}: {attempt['status']} "
                            f"({attempt_dir})"
                        )
            finally:
                browser.close()
    write_summary(output_dir, args.label, base, attempts)
    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    print(f"\nResults: {output_dir}\n\n{summary_text}")
    return 0 if all(attempt["status"] == "complete" for attempt in attempts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
