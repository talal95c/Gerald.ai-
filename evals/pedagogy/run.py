"""Pedagogy harness: run real Gerald turns on scenario screenshots, then score them.

Usage: python evals/pedagogy/run.py --label baseline [--only code-bug,board-correct] [--no-judge]
Needs OPENAI_API_KEY. Actions are recorded, never executed. Results go to evals/pedagogy/results/<stamp>-<label>/.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import os
import re
import tempfile
import threading
import time
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from gerald import USER_AGENT
from gerald.brain.realtime import RealtimeClient
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.config import load_settings
from gerald.library import Indexer, OpenAIEmbedder, Store
from gerald.library.context import course_search_results, profile_block
from gerald.perception.elements import collect_elements_detailed, serialize_context

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
ASSETS = HERE / "assets"
ACTION_TOOLS = {"click", "type_text", "press_keys", "scroll"}
BOARD_TOOLS = {"write", "write_math", "draw_path", "clear_gerald"}
NON_MARK_TOOLS = ACTION_TOOLS | {"save_recap", "search_courses", "clear", "clear_gerald"}
CRITERIA = [
    "correctness", "explains_why", "guides_not_dumps", "checks_understanding",
    "adapted_level", "drawing_quality", "honesty", "voice_style",
]
MARKDOWN = re.compile(r"(\*\*|^\s*#|^\s*[-*•] |`)", re.MULTILINE)


class NullPlayer:
    def enqueue(self, _audio: bytes) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


class RecordingActions:
    """Stands in for InputActions: records action calls, never touches the real mouse/keyboard."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def new_session() -> object:
        return object()

    @staticmethod
    def abort(_session: object) -> None:
        pass

    def execute(self, _session, name, args, *_rest) -> str:
        self.calls.append({"name": name, "args": args})
        return json.dumps({"ok": True, "note": "eval harness: action simulated, screen unchanged"})


def command_json(command: object) -> dict[str, Any]:
    if is_dataclass(command):
        return {"type": type(command).__name__, **asdict(command)}
    return {"type": type(command).__name__, "repr": repr(command)}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rect_of(data: dict[str, Any]) -> tuple[float, float, float, float] | None:
    rect = data.get("rect")
    if isinstance(rect, dict) and {"x", "y", "w", "h"} <= rect.keys():
        return rect["x"], rect["y"], rect["w"], rect["h"]
    return None


def mark_geometry(command: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    """Screen-pixel boxes a mark touches (rects, or small boxes around arrow/link/path points)."""
    rect = _rect_of(command)
    if rect:
        return [rect]
    boxes = []
    for key in ("start", "end"):
        point = command.get(key)
        if isinstance(point, (list, tuple)) and len(point) == 2:
            boxes.append((point[0] - 4, point[1] - 4, 8, 8))
    return boxes


def hits_target(boxes, targets, margin: float = 16) -> bool:
    for x, y, w, h in boxes:
        cx, cy = x + w / 2, y + h / 2
        for tx, ty, tw, th in targets:
            inside = tx - margin <= cx <= tx + tw + margin and ty - margin <= cy <= ty + th + margin
            encloses = x <= tx + tw / 2 <= x + w and y <= ty + th / 2 <= y + h
            if inside or encloses:
                return True
    return False


def annotate(image: Image.Image, marks: list[dict[str, Any]], board_ops: list[dict[str, Any]], scale: float) -> Image.Image:
    """Render Gerald's marks on the original-resolution screenshot, numbered in drawing order."""
    canvas = image.convert("RGBA")
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    blue, yellow = (10, 132, 255, 255), (255, 214, 10, 90)
    small, big = _font(18), _font(26)
    order = 0

    def badge(x: float, y: float) -> None:
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=(255, 59, 48, 255))
        draw.text((x, y), str(order), fill="white", font=small, anchor="mm")

    for item in [*({"kind": "mark", **m} for m in marks), *({"kind": "board", **b} for b in board_ops)]:
        order += 1
        if item["kind"] == "mark":
            kind = item["type"]
            rect = _rect_of(item)
            if kind == "PointCommand" and rect:
                cx, cy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
                draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), outline=blue, width=4)
                draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=blue)
                if item.get("label"):
                    draw.text((cx + 16, cy - 30), item["label"], fill=blue, font=small)
                badge(cx - 18, cy - 18)
            elif kind == "CircleCommand" and rect:
                x, y, w, h = rect
                draw.ellipse((x - 10, y - 8, x + w + 10, y + h + 8), outline=blue, width=4)
                badge(x - 10, y - 8)
            elif kind == "HighlightCommand" and rect:
                x, y, w, h = rect
                draw.rectangle((x, y, x + w, y + h), fill=yellow)
                badge(x, y)
            elif kind == "UnderlineCommand" and rect:
                x, y, w, h = rect
                draw.line((x, y + h + 2, x + w, y + h + 2), fill=blue, width=4)
                badge(x - 14, y + h)
            elif kind == "NoteCommand" and rect:
                x, y, w, h = rect
                text = item.get("text", "")
                tx, ty = x + w + 12, y
                box = draw.textbbox((tx, ty), text, font=small)
                draw.rounded_rectangle((box[0] - 8, box[1] - 6, box[2] + 8, box[3] + 6), radius=8, fill=(255, 255, 255, 235), outline=blue, width=2)
                draw.text((tx, ty), text, fill=(29, 29, 31, 255), font=small)
                badge(box[0] - 8, box[1] - 6)
            elif kind in {"ArrowCommand", "LinkCommand"}:
                (x1, y1), (x2, y2) = item["start"], item["end"]
                draw.line((x1, y1, x2, y2), fill=blue, width=4)
                if kind == "ArrowCommand":
                    import math
                    angle = math.atan2(y2 - y1, x2 - x1)
                    for delta in (2.6, -2.6):
                        draw.line((x2, y2, x2 + 18 * math.cos(angle + delta), y2 + 18 * math.sin(angle + delta)), fill=blue, width=4)
                elif item.get("label"):
                    draw.text(((x1 + x2) / 2 + 8, (y1 + y2) / 2 - 24), item["label"], fill=blue, font=small)
                badge(x1, y1)
            else:
                text = item.get("text") or item.get("title") or kind
                draw.rounded_rectangle((canvas.width - 520, 20 + 60 * (order - 1), canvas.width - 20, 70 + 60 * (order - 1)), radius=12, fill=(255, 255, 255, 240), outline=blue, width=2)
                draw.text((canvas.width - 505, 32 + 60 * (order - 1)), f"[{kind}] {str(text)[:44]}", fill=(29, 29, 31, 255), font=small)
                badge(canvas.width - 520, 20 + 60 * (order - 1))
        else:
            args = item.get("args", {})
            if item["name"] in {"write", "write_math"}:
                x, y = args.get("x", 0) / scale, args.get("y", 0) / scale
                text = args.get("text") if item["name"] == "write" else f"${args.get('latex', '')}$"
                draw.text((x, y), str(text), fill=blue, font=big)
                badge(x - 18, y + 4)
            elif item["name"] == "draw_path":
                points = [(p[0] / scale, p[1] / scale) for p in args.get("points", []) if len(p) == 2]
                if args.get("closed") and points:
                    points.append(points[0])
                if len(points) >= 2:
                    draw.line(points, fill=blue, width=4, joint="curve")
                    badge(*points[0])
            else:
                text = json.dumps(args, ensure_ascii=False)[:60]
                draw.text((20, canvas.height - 40 - 30 * order), f"[{item['name']}] {text}", fill=blue, font=small)
    return Image.alpha_composite(canvas, layer).convert("RGB")


def setup_store(home: Path, profile: dict[str, Any], course_docs: bool, api_key: str) -> tuple[Store, OpenAIEmbedder]:
    store = Store(home)
    store.save_profile(profile["name"], profile.get("level"), profile.get("subjects", []))
    embedder = OpenAIEmbedder(api_key)
    if course_docs:
        course = store.create_course("Énergie cinétique", "Physique")
        done = threading.Event()
        Indexer(store, embedder).add_document(course.id, HERE / "course" / "energie-cinetique.txt", on_done=lambda _d: done.set())
        if not done.wait(60):
            raise RuntimeError("course indexing timed out")
    return store, embedder


async def run_scenario(scenario: dict[str, Any], defaults: dict[str, Any], settings, out: Path, prompt: str) -> dict[str, Any]:
    targets_by_page = json.loads((ASSETS / "targets.json").read_text(encoding="utf-8"))
    home = Path(tempfile.mkdtemp(prefix=f"gerald-eval-{scenario['id']}-"))
    store, embedder = setup_store(home, scenario.get("profile") or defaults, bool(scenario.get("course_docs")), settings.api_key)
    instructions = f"{prompt.rstrip()}\n\n{profile_block(store)}"
    actions = RecordingActions()
    state: dict[str, Any] = {}

    def reset_turn() -> None:
        state.update(transcript=[], tool_calls=[], marks=[], board_ops=[], done=asyncio.Event(), t0=time.monotonic(), t_audio=None, t_done=None)

    reset_turn()
    loop = asyncio.get_running_loop()

    def on_event(event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind in {"response.output_audio.delta", "response.audio.delta"} and state["t_audio"] is None:
            state["t_audio"] = time.monotonic() - state["t0"]
        if kind in {"response.output_audio_transcript.done", "response.audio_transcript.done"}:
            state["transcript"].append(event.get("transcript", ""))
        if kind == "response.done":
            response = event.get("response", {})
            calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
            for call in calls:
                try:
                    arguments = json.loads(call.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {"raw": call.get("arguments")}
                output = client._tool_outputs.get(call.get("call_id", ""), "")
                state["tool_calls"].append({"name": call.get("name"), "args": arguments, "output": output[:400]})
            if not calls or client._tool_rounds >= 4 or response.get("status") == "cancelled":
                state["t_done"] = time.monotonic() - state["t0"]
                loop.call_soon_threadsafe(state["done"].set)

    def on_commands(commands: list[object]) -> None:
        state["marks"].extend(command_json(command) for command in commands)

    def on_board_tool(name: str, args: dict[str, Any]) -> str:
        state["board_ops"].append({"name": name, "args": args})
        return json.dumps({"ok": True})

    client = RealtimeClient(
        settings.api_key,
        settings.model,
        settings.voice,
        instructions,
        player=NullPlayer(),
        on_event=on_event,
        on_commands=on_commands,
        usage_log=out / "usage.jsonl",
        input_actions=actions,
        on_board_tool=on_board_tool,
        on_course_search=lambda query, course: course_search_results(store, embedder, query, course),
    )
    turns_out = []
    await client.connect()
    runner = asyncio.create_task(client.run())
    try:
        for index, turn in enumerate(scenario["turns"], start=1):
            page = turn.get("image", scenario["image"])
            image = Image.open(ASSETS / f"{page}.png").convert("RGB")
            capture = capture_from_image(image, MonitorRect(0, 0, image.width, image.height), settings.max_image_width)
            elements = collect_elements_detailed(capture).elements
            context = serialize_context(elements, capture.image_width, capture.image_height)
            if scenario.get("board"):
                context = f"BOARD MODE\n{context}"
            reset_turn()
            actions_before = len(actions.calls)
            await client.start_turn()
            state["t0"] = time.monotonic()
            await client.finish_turn(capture, elements, context, turn["question"], has_audio=False)
            try:
                await asyncio.wait_for(state["done"].wait(), timeout=120)
            except asyncio.TimeoutError:
                state["t_done"] = None
            await asyncio.sleep(0.3)
            target_ids = turn.get("targets", scenario.get("targets", []))
            targets = [targets_by_page[page][t] for t in target_ids if t in targets_by_page.get(page, {})]
            annotated = annotate(image, [m for m in state["marks"] if m["type"] != "ClearCommand"], [b for b in state["board_ops"] if b["name"] != "clear_gerald"], capture.scale)
            image_path = out / f"{scenario['id']}-t{index}.png"
            annotated.save(image_path)
            turns_out.append({
                "question": turn["question"],
                "page": page,
                "transcript": " ".join(t.strip() for t in state["transcript"] if t.strip()),
                "tool_calls": state["tool_calls"],
                "marks": state["marks"],
                "board_ops": state["board_ops"],
                "actions": actions.calls[actions_before:],
                "targets": targets,
                "image": image_path.name,
                "t_first_audio": round(state["t_audio"], 2) if state["t_audio"] is not None else None,
                "t_done": round(state["t_done"], 2) if state["t_done"] is not None else None,
                "scale": capture.scale,
            })
    finally:
        runner.cancel()
        await client.close()
    result = {"id": scenario["id"], "category": scenario["category"], "goal": scenario["goal"],
              "profile": scenario.get("profile") or defaults, "turns": turns_out}
    result["checks"] = deterministic_checks(scenario, turns_out)
    return result


def deterministic_checks(scenario: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, bool | None]:
    expect = scenario.get("expect", {})
    board = bool(scenario.get("board"))
    checks: dict[str, bool | None] = {}
    words = [len(turn["transcript"].split()) for turn in turns]
    checks["spoke"] = all(count > 0 for count in words)
    checks["concise"] = all(count <= expect.get("max_words", 80) for count in words)
    checks["no_markdown"] = not any(MARKDOWN.search(turn["transcript"]) for turn in turns)
    screen_marks = [[m for m in turn["marks"] if m["type"] != "ClearCommand"] for turn in turns]
    board_marks = [[b for b in turn["board_ops"] if b["name"] != "clear_gerald"] for turn in turns]
    limit = 8 if board else 4
    totals = [len(s) + len(b) for s, b in zip(screen_marks, board_marks)]
    policy = expect.get("marks", "optional")
    if policy == "required":
        checks["marks_count_ok"] = all(1 <= total <= limit for total in totals)
    elif policy == "none":
        checks["marks_count_ok"] = all(total == 0 for total in totals)
    else:
        checks["marks_count_ok"] = all(total <= limit for total in totals)
    if policy != "none" and any(turn["targets"] for turn in turns):
        hit = True
        for turn, marks, ops in zip(turns, screen_marks, board_marks):
            if not turn["targets"] or (policy == "optional" and not marks and not ops):
                continue
            boxes = [box for mark in marks for box in mark_geometry(mark)]
            for op in ops:
                if op["name"] == "draw_path":
                    points = [(p[0] / turn["scale"], p[1] / turn["scale"]) for p in op["args"].get("points", []) if len(p) == 2]
                    if points:
                        xs, ys = zip(*points)
                        boxes.append((min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
            hit = hit and hits_target(boxes, turn["targets"])
        checks["on_target"] = hit
    else:
        checks["on_target"] = None
    names = [[call["name"] for call in turn["tool_calls"]] for turn in turns]
    checks["tool_errors"] = not any('"ok": false' in call["output"].replace('"ok":false', '"ok": false') for turn in turns for call in turn["tool_calls"])
    for tool in expect.get("required_tools", []):
        checks[f"used_{tool}"] = any(tool in turn_names for turn_names in names)
    if expect.get("no_actions"):
        checks["no_actions"] = not any(turn["actions"] for turn in turns)
    if expect.get("confirm_before_action"):
        first, rest = turns[0], turns[1:]
        checks["asked_before_acting"] = not first["actions"]
        checks["acted_after_yes"] = any(
            any(call["args"].get("confirmed") is True for call in turn["actions"]) for turn in rest
        )
    return checks


def judge(result: dict[str, Any], out: Path, rubric: str, model: str, api_key: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps({
        "scenario_goal": result["goal"],
        "learner_profile": result["profile"],
        "turns": [{
            "turn": i,
            "learner_question": turn["question"],
            "gerald_speech_transcript": turn["transcript"],
            "gerald_tool_calls": [{"name": c["name"], "args": c["args"]} for c in turn["tool_calls"]],
            "annotated_screenshot": f"image {i} below (Gerald's drawings in blue, red numbers = drawing order)",
        } for i, turn in enumerate(result["turns"], start=1)],
    }, ensure_ascii=False, indent=1)}]
    for turn in result["turns"]:
        image = Image.open(out / turn["image"])
        image.thumbnail((1440, 900))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        content.append({"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()})
    criterion = {"type": "object", "properties": {"score": {"type": "integer", "enum": [0, 1, 2]}, "why": {"type": "string"}}, "required": ["score", "why"], "additionalProperties": False}
    schema = {"type": "object", "properties": {**{name: criterion for name in CRITERIA}, "worst_issue": {"type": "string"}, "summary": {"type": "string"}},
              "required": [*CRITERIA, "worst_issue", "summary"], "additionalProperties": False}
    body = {
        "model": model,
        "input": [{"role": "system", "content": rubric}, {"role": "user", "content": content}],
        "text": {"format": {"type": "json_schema", "name": "pedagogy_grade", "schema": schema, "strict": True}},
    }
    if model.startswith("gpt-5"):
        body["reasoning"] = {"effort": "medium"}
    request = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=240) as response:
        payload = json.loads(response.read())
    text = next(part["text"] for item in payload["output"] if item.get("type") == "message" for part in item["content"] if part.get("type") == "output_text")
    grade = json.loads(text)
    grade["score_pct"] = round(100 * sum(grade[name]["score"] for name in CRITERIA) / (2 * len(CRITERIA)), 1)
    return grade


def write_report(results: list[dict[str, Any]], out: Path, label: str) -> None:
    lines = [f"# Pedagogy harness — {label}", ""]
    graded = [r for r in results if "grade" in r]
    if graded:
        mean = sum(r["grade"]["score_pct"] for r in graded) / len(graded)
        lines.append(f"Judge score (mean): **{mean:.1f}%** over {len(graded)} scenarios")
        lines.append("")
        lines.append("| criterion | mean /2 |")
        lines.append("|---|---|")
        for name in CRITERIA:
            lines.append(f"| {name} | {sum(r['grade'][name]['score'] for r in graded) / len(graded):.2f} |")
        lines.append("")
    all_checks = [(name, value) for r in results for name, value in r["checks"].items() if value is not None]
    passed = sum(1 for _n, v in all_checks if v)
    lines.append(f"Deterministic checks: **{passed}/{len(all_checks)}** passed")
    lines.append("")
    lines.append("| scenario | judge % | failed checks | worst issue |")
    lines.append("|---|---|---|---|")
    for r in results:
        failed = ", ".join(n for n, v in r["checks"].items() if v is False) or "—"
        grade = r.get("grade", {})
        lines.append(f"| {r['id']} | {grade.get('score_pct', '—')} | {failed} | {grade.get('worst_issue', r.get('error', '—'))} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    parser.add_argument("--only", default="")
    parser.add_argument("--judge-model", default="gpt-5.5")
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    spec = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    only = {item for item in args.only.split(",") if item}
    scenarios = [s for s in spec["scenarios"] if not only or s["id"] in only]
    out = HERE / "results" / f"{datetime.now():%Y%m%d-%H%M%S}-{args.label}"
    out.mkdir(parents=True)
    prompt = (ROOT / "gerald" / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
    rubric = (HERE / "rubric.md").read_text(encoding="utf-8")
    results = []
    for scenario in scenarios:
        print(f"== {scenario['id']}", flush=True)
        try:
            result = await run_scenario(scenario, spec["default_profile"], settings, out, prompt)
        except Exception as error:  # keep going; a crashed scenario is a finding
            results.append({"id": scenario["id"], "category": scenario["category"], "checks": {"ran": False}, "error": repr(error)[:300]})
            print(f"   error: {error!r}", flush=True)
            continue
        if not args.no_judge:
            try:
                result["grade"] = await asyncio.to_thread(judge, result, out, rubric, args.judge_model, settings.api_key)
            except Exception as error:
                result["judge_error"] = repr(error)[:300]
        for turn in result["turns"]:
            print(f"   Q: {turn['question']}\n   A: {turn['transcript']}\n   tools: {[c['name'] for c in turn['tool_calls']]}", flush=True)
        print(f"   checks: {result['checks']}  judge: {result.get('grade', {}).get('score_pct')}", flush=True)
        results.append(result)
        (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(results, out, args.label)
    print(f"\nresults: {out}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("GERALD_START_HIDDEN", "1")
    raise SystemExit(asyncio.run(main()))
