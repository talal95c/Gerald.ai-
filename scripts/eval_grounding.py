from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
import io
import json
from pathlib import Path
import statistics
import time
from typing import Any

from PIL import Image

from gerald.brain.realtime import RealtimeClient
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.config import load_settings
from gerald.perception.eval_metrics import annotate_screenshot, center_distance, prediction_hit, scale_box
from gerald.perception.elements import collect_elements_detailed, serialize_context
from gerald.perception.grounder import configured_grounder
from gerald.tools.registry import (
    ArrowCommand,
    CircleCommand,
    HighlightCommand,
    LinkCommand,
    PointCommand,
    UnderlineCommand,
)

CASES_PATH = Path(__file__).parents[1] / "evals" / "grounding_cases.json"
PROMPT_PATH = Path(__file__).parents[1] / "gerald" / "prompts" / "system_prompt.md"
RESULTS_DIR = Path(__file__).parents[1] / "evals" / "results"


class NullPlayer:
    def enqueue(self, _audio: bytes) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


def prediction_rect(commands: list[object]) -> tuple[float, float, float, float] | None:
    for command in commands:
        if isinstance(command, (PointCommand, CircleCommand, HighlightCommand, UnderlineCommand)):
            rect = command.rect
            return rect.x, rect.y, rect.w, rect.h
        if isinstance(command, (ArrowCommand, LinkCommand)):
            x, y = command.end
            return float(x), float(y), 0.0, 0.0
    return None


def _target_locator(page, target: dict[str, str]):
    if "css" in target:
        return page.locator(target["css"])
    if "role" in target and "name" in target:
        return page.get_by_role(target["role"], name=target["name"], exact=True)
    raise ValueError(f"unsupported target locator: {target}")


async def _first_visible_box(page, target: dict[str, str], dpr: float):
    locator = _target_locator(page, target)
    for index in range(await locator.count()):
        candidate = locator.nth(index)
        if not await candidate.is_visible():
            continue
        box = await candidate.bounding_box()
        if box is None:
            return None, "first visible locator has no bounding box"
        return scale_box(box, dpr), None
    return None, "no visible match for target locator"


async def _run_realtime(
    capture,
    elements,
    context_text: str,
    question: str,
    settings,
) -> tuple[
    list[object],
    list[dict[str, Any]],
    dict[str, float | None],
    dict | None,
    dict | None,
    str | None,
    str | None,
]:
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    completed = asyncio.Event()
    commands: list[object] = []
    tool_calls: list[dict[str, Any]] = []
    timings: dict[str, float | None] = {
        "t_first_audio": None,
        "t_first_mark": None,
        "t_done": None,
        "t_total": None,
    }
    usage: dict | None = None
    response_started: float | None = None

    def on_event(event: dict[str, Any]) -> None:
        nonlocal usage
        event_type = event.get("type")
        if event_type == "response.function_call_arguments.done":
            raw_arguments = event.get("arguments", "{}")
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError:
                arguments = raw_arguments
            tool_calls.append(
                {
                    "call_id": event.get("call_id"),
                    "name": event.get("name"),
                    "arguments": arguments,
                }
            )
        elif event_type == "response.done":
            response = event.get("response", {})
            usage = response.get("usage") or usage
            if not any(item.get("type") == "function_call" for item in response.get("output", [])):
                if response_started is not None and timings["t_total"] is None:
                    timings["t_total"] = time.monotonic() - response_started
                completed.set()

    def on_commands(draw_commands: list[object]) -> None:
        commands.extend(draw_commands)
        if draw_commands and timings["t_first_mark"] is None and response_started is not None:
            timings["t_first_mark"] = time.monotonic() - response_started

    client = RealtimeClient(
        settings.api_key,
        settings.model,
        settings.voice,
        instructions,
        player=NullPlayer(),
        on_event=on_event,
        on_commands=on_commands,
    )
    runner = None
    try:
        await client.connect()
        send = client._send

        async def timed_send(event: dict[str, Any]) -> None:
            nonlocal response_started
            await send(event)
            if event.get("type") == "response.create" and response_started is None:
                response_started = time.monotonic()

        client._send = timed_send
        handle_event = client.handle_event

        async def timed_handle_event(event: dict[str, Any]) -> None:
            event_type = event.get("type")
            if response_started is not None:
                if (
                    event_type in {"response.output_audio.delta", "response.audio.delta"}
                    and timings["t_first_audio"] is None
                ):
                    timings["t_first_audio"] = time.monotonic() - response_started
                elif event_type == "response.done" and timings["t_done"] is None:
                    timings["t_done"] = time.monotonic() - response_started
            await handle_event(event)

        client.handle_event = timed_handle_event
        runner = asyncio.create_task(client.run())
        await client.finish_turn(capture, elements, context_text, question, has_audio=False)
        await asyncio.wait_for(completed.wait(), timeout=120)
        grounding = None
        grounding_note = None
        first_mark_error = None
        for call in tool_calls:
            if call["name"] not in {"point", "circle", "highlight", "underline", "arrow", "link"}:
                continue
            output = client._tool_outputs.get(str(call.get("call_id") or ""))
            if output is None:
                continue
            try:
                parsed = json.loads(output)
            except json.JSONDecodeError:
                continue
            if not parsed.get("ok"):
                if first_mark_error is None:
                    first_mark_error = parsed.get("error")
                continue
            if "grounding" not in parsed:
                continue
            grounding = parsed["grounding"]
            if isinstance(grounding, dict):
                endpoint = "to" if call["name"] == "arrow" else "b" if call["name"] == "link" else None
                if endpoint:
                    grounding = grounding.get(endpoint)
            grounding_note = parsed.get("note")
            break
        return commands, tool_calls, timings, usage, grounding, grounding_note, first_mark_error
    finally:
        if runner is not None:
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass
        await client.close()


def _summary(results: list[dict[str, Any]]) -> None:
    scored = [row for row in results if row.get("status") in {"OK", "NO_MARK"}]
    audio = [
        row["latencies"]["t_first_audio"]
        for row in scored
        if row.get("latencies", {}).get("t_first_audio") is not None
    ]
    token_total = 0
    for row in results:
        usage = row.get("usage") or {}
        token_total += usage.get("total_tokens", 0) or (
            (usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)
        )
    print("kind       hit rate    median distance")
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        by_kind[row["kind"]].append(row)
    by_kind["overall"] = scored
    for kind, rows in by_kind.items():
        rate = sum(bool(row.get("hit")) for row in rows) / len(rows) if rows else 0
        values = [row["distance"] for row in rows if row.get("distance") is not None]
        median_distance = f"{statistics.median(values):.1f}px" if values else "n/a"
        print(f"{kind:<10} {rate:>6.1%}      {median_distance}")
    print(f"mean t_first_audio: {statistics.mean(audio):.3f}s" if audio else "mean t_first_audio: n/a")
    grounder_times = [
        row["latencies"]["grounder"]
        for row in results
        if row.get("latencies", {}).get("grounder") is not None
    ]
    if grounder_times:
        print(f"mean grounder latency: {statistics.mean(grounder_times):.3f}s")
    print(f"total tokens: {token_total}")


async def _evaluate(args: argparse.Namespace) -> int:
    cases_path = Path(args.cases) if args.cases else CASES_PATH
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    base_dir = cases_path.resolve().parent
    cases = data["cases"]
    if args.only:
        selected = {value.strip() for value in args.only.split(",") if value.strip()}
        known = {case["id"] for case in cases}
        missing = selected - known
        if missing:
            raise SystemExit(f"unknown case id(s): {', '.join(sorted(missing))}")
        cases = [case for case in cases if case["id"] in selected]
    settings = load_settings()
    if not args.dry_gt and not args.grounder_only and not settings.api_key:
        raise SystemExit("OPENAI_API_KEY is required unless --dry-gt is used")
    grounder = configured_grounder(args.grounder_only) if args.grounder_only else None
    if args.grounder_only and grounder is None:
        raise SystemExit(f"unknown grounder backend: {args.grounder_only}")

    from playwright.async_api import async_playwright

    results: list[dict[str, Any]] = []
    run_ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_dir = RESULTS_DIR / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        if args.headless:
            browser = await playwright.chromium.launch()
        else:
            browser = await playwright.chromium.connect_over_cdp("http://localhost:29229")
        context = await browser.new_context(viewport=data["viewport"])
        try:
            for repeat_index in range(1, args.repeat + 1):
                for case in cases:
                    page = await context.new_page()
                    gt = None
                    reason = None
                    dpr = 1.0
                    screenshot = None
                    image = None
                    prediction = None
                    elements = []
                    ocr_seconds = 0.0
                    first_mark_error = None
                    try:
                        url = case["url"]
                        if "://" not in url:
                            url = (base_dir / url).resolve().as_uri()
                        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        await page.wait_for_timeout(1500)
                        dpr = float(await page.evaluate("() => window.devicePixelRatio"))
                        gt, reason = await _first_visible_box(page, case["target"], dpr)
                    except Exception as error:
                        reason = f"navigation or locator error: {error}"
                    try:
                        screenshot = await page.screenshot()
                    except Exception as error:
                        reason = reason or f"screenshot failed: {error}"
                    if screenshot is not None:
                        try:
                            image = Image.open(io.BytesIO(screenshot)).convert("RGB")
                        except Exception as error:
                            reason = reason or f"screenshot decode failed: {error}"
                    if image is not None and not args.grounder_only:
                        capture = capture_from_image(
                            image,
                            MonitorRect(0, 0, image.width, image.height),
                            settings.max_image_width,
                        )
                        collection = collect_elements_detailed(capture)
                        elements = collection.elements
                        ocr_seconds = collection.ocr_seconds
                    image_size = (
                        {"width": image.width, "height": image.height}
                        if image is not None
                        else None
                    )
                    row: dict[str, Any] = {
                        "id": case["id"],
                        "kind": case["kind"],
                        "repeat": repeat_index,
                        "status": "GT_MISSING" if gt is None else "GT_FOUND",
                        "hit": None,
                        "distance": None,
                        "grounding_layer": None,
                        "layer": None,
                        "grounding_note": None,
                        "tool_args": [],
                        "latencies": {
                            "t_first_audio": None,
                            "t_first_mark": None,
                            "t_done": None,
                            "t_total": None,
                        },
                        "usage": None,
                        "dpr": dpr,
                        "gt": gt,
                        "ground_truth": gt,
                        "prediction": None,
                        "image_size": image_size,
                        "elements_count": len(elements),
                        "ocr_seconds": round(ocr_seconds, 3),
                        "tool_error": None,
                        "reason": reason,
                    }
                    if gt is not None and image is None:
                        row["status"] = "SCREENSHOT_ERROR"
                    if gt is not None and image is not None and args.grounder_only:
                        description = case.get("description")
                        if not isinstance(description, str) or not description:
                            row["status"] = "DESCRIPTION_MISSING"
                            row["reason"] = "case has no grounder description"
                        else:
                            started = time.monotonic()
                            try:
                                point = grounder.locate(image, description)
                                latency = time.monotonic() - started
                                row["tool_args"] = [{"description": description}]
                                row["latencies"]["grounder"] = latency
                                row["grounding_layer"] = "grounder" if point is not None else None
                                row["layer"] = row["grounding_layer"]
                                if point is None:
                                    row["status"] = "NO_MARK"
                                else:
                                    prediction = (float(point[0]), float(point[1]), 0.0, 0.0)
                                    row["prediction"] = prediction
                                    row["hit"] = prediction_hit(
                                        prediction,
                                        gt,
                                        data["hit_margin_px"] * dpr,
                                    )
                                    row["distance"] = center_distance(prediction, gt)
                                    row["status"] = "OK"
                            except Exception as error:
                                row["status"] = "GROUNDER_ERROR"
                                row["reason"] = str(error)
                    elif gt is not None and image is not None and not args.dry_gt:
                        context_text = serialize_context(
                            elements,
                            capture.image_width,
                            capture.image_height,
                        )
                        try:
                            (
                                commands,
                                tool_args,
                                latencies,
                                usage,
                                layer,
                                grounding_note,
                                first_mark_error,
                            ) = await _run_realtime(
                                capture,
                                elements,
                                context_text,
                                case["question"],
                                settings,
                            )
                            prediction = prediction_rect(commands)
                            row["tool_args"] = tool_args
                            row["latencies"] = latencies
                            row["usage"] = usage
                            row["grounding_layer"] = layer
                            row["layer"] = layer
                            row["grounding_note"] = grounding_note
                            row["tool_error"] = first_mark_error
                            row["status"] = "NO_MARK" if prediction is None else "OK"
                            if prediction is not None:
                                row["prediction"] = prediction
                                margin = data["hit_margin_px"] * dpr
                                row["hit"] = prediction_hit(prediction, gt, margin)
                                row["distance"] = center_distance(prediction, gt)
                        except Exception as error:
                            row["status"] = "API_ERROR"
                            row["reason"] = str(error)
                    if image is not None:
                        repeated_suffix = f"-repeat-{repeat_index}" if args.repeat > 1 else ""
                        image_name = f"{case['id']}{repeated_suffix}.png"
                        annotate_screenshot(image, gt, prediction).save(run_dir / image_name)
                        row["screenshot_path"] = str(
                            Path("evals") / "results" / run_ts / image_name
                        )
                    results.append(row)
                    if args.dry_gt:
                        suffix = (
                            f"GT_MISSING — {reason}"
                            if gt is None
                            else "SCREENSHOT_ERROR" if screenshot is None else "GT_FOUND"
                        )
                        print(f"{case['id']:<15} {suffix}")
                    await page.close()
        finally:
            await context.close()

    output_path = RESULTS_DIR / f"{run_ts}.jsonl"
    output_path.write_text(
        "".join(json.dumps(result, ensure_ascii=False) + "\n" for result in results),
        encoding="utf-8",
    )
    print(f"results: {output_path}")
    if not args.dry_gt:
        _summary(results)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate visual grounding against browser ground truth.")
    parser.add_argument("--dry-gt", action="store_true", help="resolve target boxes and take screenshots only")
    parser.add_argument(
        "--grounder-only",
        choices=("openrouter", "moondream", "moondream-cloud"),
        help="evaluate a visual grounder without Realtime",
    )
    parser.add_argument("--only", help="comma-separated case IDs")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--cases", help="cases JSON (default: evals/grounding_cases.json); relative urls resolve from its folder")
    parser.add_argument("--headless", action="store_true", help="launch a private headless Chromium instead of the CDP browser")
    args = parser.parse_args()
    if args.dry_gt and args.grounder_only:
        parser.error("--dry-gt and --grounder-only cannot be used together")
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    return args


def main() -> int:
    return asyncio.run(_evaluate(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
