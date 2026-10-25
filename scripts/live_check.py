from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
import json
import time
from pathlib import Path

from PIL import Image

from gerald.audio.player import AudioPlayer
from gerald.brain.realtime import RealtimeClient
from gerald.capture.screen import MonitorRect, capture_from_image, capture_screen
from gerald.config import load_settings, set_physical_dpi_awareness
from gerald.perception.elements import collect_elements, serialize_context
from gerald.tools.registry import CircleCommand, PointCommand


class NullPlayer:
    def enqueue(self, _audio: bytes) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one live Realtime teaching turn without a microphone.")
    parser.add_argument("image", nargs="?", help="PNG or other image file (omit to capture the current monitor)")
    parser.add_argument("--question", required=True)
    parser.add_argument("--expect", nargs=2, type=float, metavar=("X", "Y"))
    parser.add_argument("--play", action="store_true", help="play the assistant's audio response")
    parser.add_argument("--json", action="store_true", help="print one machine-readable result line")
    return parser.parse_args()


async def run() -> int:
    args = _parse_args()
    settings = load_settings()
    if not settings.api_key:
        raise SystemExit("OPENAI_API_KEY is required for live_check")
    if args.image:
        image = Image.open(args.image)
        capture = capture_from_image(
            image,
            MonitorRect(0, 0, image.width, image.height),
            settings.max_image_width,
        )
    else:
        set_physical_dpi_awareness()
        capture = capture_screen(settings.max_image_width)
    elements = collect_elements(capture)
    context = serialize_context(elements, capture.image_width, capture.image_height)
    instructions = (Path(__file__).parents[1] / "gerald" / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
    completed = asyncio.Event()
    point_commands: list[PointCommand | CircleCommand] = []
    draw_commands: list[object] = []
    tool_calls: list[dict] = []
    output_events = []
    timings: dict[str, float | None] = {
        "t_first_audio": None,
        "t_first_mark": None,
        "t_done": None,
        "t_total": None,
    }
    response_started: float | None = None

    def on_event(event: dict) -> None:
        output_events.append(event)
        if event.get("type") == "response.done":
            response = event.get("response", {})
            calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
            tool_calls.extend(
                {"name": call.get("name"), "arguments": call.get("arguments")}
                for call in calls
            )
            if not calls:
                if response_started is not None and timings["t_total"] is None:
                    timings["t_total"] = time.monotonic() - response_started
                completed.set()
            for call in calls:
                if not args.json:
                    print(f"tool call: {call.get('name')} {call.get('arguments')}")
        elif event.get("type") in {"response.output_audio_transcript.delta", "response.audio_transcript.delta"}:
            if not args.json:
                print(event.get("delta", ""), end="", flush=True)

    def on_commands(commands: list[object]) -> None:
        nonlocal response_started
        for command in commands:
            draw_commands.append(command)
            if isinstance(command, (PointCommand, CircleCommand)):
                point_commands.append(command)
            if timings["t_first_mark"] is None and response_started is not None:
                timings["t_first_mark"] = time.monotonic() - response_started
            if not args.json:
                print(f"resolved: {command}")

    client = RealtimeClient(
        settings.api_key,
        settings.model,
        settings.voice,
        instructions,
        player=AudioPlayer() if args.play else NullPlayer(),
        on_event=on_event,
        on_commands=on_commands,
    )
    try:
        await client.connect()
        send = client._send

        async def timed_send(event: dict) -> None:
            nonlocal response_started
            await send(event)
            if event.get("type") == "response.create" and response_started is None:
                response_started = time.monotonic()

        client._send = timed_send
        handle_event = client.handle_event

        async def timed_handle_event(event: dict) -> None:
            event_type = event.get("type")
            if response_started is not None:
                if event_type in {"response.output_audio.delta", "response.audio.delta"} and timings["t_first_audio"] is None:
                    timings["t_first_audio"] = time.monotonic() - response_started
                elif event_type == "response.done" and timings["t_done"] is None:
                    timings["t_done"] = time.monotonic() - response_started
            await handle_event(event)

        client.handle_event = timed_handle_event
        runner = asyncio.create_task(client.run())
        await client.finish_turn(capture, elements, context, args.question, has_audio=False)
        await asyncio.wait_for(completed.wait(), timeout=120)
    finally:
        runner.cancel() if 'runner' in locals() else None
        await client.close()
    usage = next(
        (event.get("response", {}).get("usage") for event in reversed(output_events) if event.get("type") == "response.done"),
        None,
    )
    tool_results = []
    for output in client._tool_outputs.values():
        try:
            tool_results.append(json.loads(output))
        except json.JSONDecodeError:
            tool_results.append({"raw": output})
    error = None
    if args.expect and point_commands:
        rect = point_commands[0].rect
        image_x, image_y = capture.screen_to_img(*rect.center)
        error = ((image_x - args.expect[0]) ** 2 + (image_y - args.expect[1]) ** 2) ** 0.5
    if args.json:
        def command_json(command: object) -> dict | str:
            if is_dataclass(command):
                return {"type": type(command).__name__, **asdict(command)}
            return repr(command)

        print(json.dumps({
            "latencies": {key: round(value, 3) if value is not None else None for key, value in timings.items()},
            "tool_calls": tool_calls,
            "commands": [command_json(command) for command in draw_commands],
            "tool_results": tool_results,
            "usage": usage,
            "expect_error_px": error,
        }))
    else:
        print(
            "\nLatencies: "
            + ", ".join(
                f"{key}={value:.2f}s" if value is not None else f"{key}=n/a"
                for key, value in timings.items()
            )
        )
        print(f"Token usage: {json.dumps(usage) if usage else 'not reported'}")
        for result in tool_results:
            print(f"tool result: {json.dumps(result)}")
        if error is not None:
            print(f"First point/circle error: {error:.2f}px")
        elif args.expect:
            print("No point or circle tool call was produced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
