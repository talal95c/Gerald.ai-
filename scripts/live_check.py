from __future__ import annotations

import argparse
import asyncio
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
    started = time.monotonic()
    point_commands: list[PointCommand | CircleCommand] = []
    output_events = []

    def on_event(event: dict) -> None:
        output_events.append(event)
        if event.get("type") == "response.done":
            response = event.get("response", {})
            calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
            if not calls:
                completed.set()
            for call in calls:
                print(f"tool call: {call.get('name')} {call.get('arguments')}")
        elif event.get("type") in {"response.output_audio_transcript.delta", "response.audio_transcript.delta"}:
            print(event.get("delta", ""), end="", flush=True)

    def on_commands(commands: list[object]) -> None:
        for command in commands:
            if isinstance(command, (PointCommand, CircleCommand)):
                point_commands.append(command)
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
        runner = asyncio.create_task(client.run())
        await client.finish_turn(capture, elements, context, args.question, has_audio=False)
        await asyncio.wait_for(completed.wait(), timeout=120)
    finally:
        runner.cancel() if 'runner' in locals() else None
        await client.close()
    elapsed = time.monotonic() - started
    print(f"\nLatency: {elapsed:.2f}s")
    usage = next(
        (event.get("response", {}).get("usage") for event in reversed(output_events) if event.get("type") == "response.done"),
        None,
    )
    print(f"Token usage: {json.dumps(usage) if usage else 'not reported'}")
    if args.expect and point_commands:
        rect = point_commands[0].rect
        image_x, image_y = capture.screen_to_img(*rect.center)
        error = ((image_x - args.expect[0]) ** 2 + (image_y - args.expect[1]) ** 2) ** 0.5
        print(f"First point/circle error: {error:.2f}px")
    elif args.expect:
        print("No point or circle tool call was produced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
