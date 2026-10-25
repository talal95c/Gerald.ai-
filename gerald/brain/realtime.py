from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np

from gerald.actions.input import ACTION_TOOL_NAMES, InputActions
from gerald.audio.player import AudioPlayer
from gerald.capture.screen import Capture
from gerald.perception.elements import Element
from gerald.tools.recap import save_recap
from gerald.tools.registry import BOARD_TOOL_NAMES, TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)
REALTIME_URL = "wss://api.openai.com/v1/realtime"


class RealtimeClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        voice: str,
        instructions: str,
        player: AudioPlayer | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_commands: Callable[[list[object]], None] | None = None,
        usage_log: Path | None = None,
        require_confirmation: bool = True,
        capture_after_action: Callable[[], tuple[Capture, list[Element], str]] | None = None,
        on_marks_visible: Callable[[bool], None] | None = None,
        input_actions: InputActions | None = None,
        request_action_confirmation: Callable[
            [str, tuple[int, int, int, int] | None, float], bool
        ]
        | None = None,
        on_board_tool: Callable[[str, dict[str, Any]], str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.player = player or AudioPlayer()
        self.on_event = on_event or (lambda event: None)
        self.on_commands = on_commands or (lambda commands: None)
        self.on_marks_visible = on_marks_visible or (lambda _visible: None)
        self.on_board_tool = on_board_tool or (
            lambda name, _args: json.dumps({"ok": False, "error": f"board is unavailable for {name}"})
        )
        self.input_actions = input_actions or InputActions(
            require_confirmation=require_confirmation,
            request_confirmation=request_action_confirmation,
        )
        self.capture_after_action = capture_after_action
        self.usage_log = usage_log if usage_log is not None else Path.home() / ".gerald" / "usage.jsonl"
        self.websocket = None
        self.capture: Capture | None = None
        self.image_array: np.ndarray | None = None
        self.elements: list[Element] = []
        self._tool_rounds = 0
        self._action_session = self.input_actions.new_session()
        self._executed_call_ids: set[str] = set()
        self._tool_outputs: dict[str, str] = {}
        self._turn_started_at: float | None = None
        self._closed = False
        self._response_active = False
        self.last_board_image = None

    @property
    def session_url(self) -> str:
        return f"{REALTIME_URL}?model={quote(self.model)}"

    def session_update_event(self) -> dict[str, Any]:
        return {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": self.instructions,
                "tools": TOOL_SCHEMAS,
                "tool_choice": "auto",
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "transcription": {"model": "gpt-4o-mini-transcribe"},
                        "turn_detection": None,
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "voice": self.voice,
                    },
                },
            },
        }

    async def connect(self, websocket_factory: Callable[..., Any] | None = None) -> None:
        if websocket_factory is None:
            from websockets.asyncio.client import connect

            websocket_factory = connect
        self.websocket = await websocket_factory(
            self.session_url,
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
            max_size=32 * 1024 * 1024,
        )
        await self._send(self.session_update_event())
        while True:
            event = await self._receive()
            if event.get("type") == "session.updated":
                self.on_event(event)
                break
            if event.get("type") == "error":
                raise RuntimeError(event.get("error", {}).get("message", "Realtime session setup failed"))

    async def _send(self, event: dict[str, Any]) -> None:
        if self.websocket is None:
            raise RuntimeError("Realtime connection is not open")
        await self.websocket.send(json.dumps(event))

    async def _receive(self) -> dict[str, Any]:
        if self.websocket is None:
            raise RuntimeError("Realtime connection is not open")
        data = await self.websocket.recv()
        return json.loads(data)

    async def start_turn(self) -> None:
        self.player.stop()
        self.input_actions.abort(self._action_session)
        if self.websocket is not None and self._response_active:
            await self._send({"type": "response.cancel"})
            self._response_active = False
        self._tool_rounds = 0
        self._action_session = self.input_actions.new_session()
        self._turn_started_at = time.monotonic()

    def abort_actions(self) -> None:
        self.input_actions.abort(self._action_session)

    async def send_recap(self) -> None:
        await self.cancel()
        self._tool_rounds = 0
        self._action_session = self.input_actions.new_session()
        self._turn_started_at = time.monotonic()
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Fais un récap écrit de cette leçon : ce qu'on a vu, les étapes clés, "
                                "3 points à retenir, et un mini exercice. Réponds par l'outil save_recap."
                            ),
                        }
                    ],
                },
            }
        )
        await self._send({"type": "response.create"})
        self._response_active = True
        self._turn_started_at = time.monotonic()

    async def send_audio(self, audio: bytes) -> None:
        if audio:
            await self._send(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(audio).decode("ascii"),
                }
            )

    async def finish_turn(
        self,
        capture: Capture,
        elements: list[Element],
        context: str,
        question: str = "",
        has_audio: bool = True,
    ) -> None:
        self.capture = capture
        self.image_array = np.asarray(capture.full_image or capture.image)
        self.last_board_image = capture.full_image if "BOARD MODE" in context else None
        self.elements = elements
        if has_audio:
            await self._send({"type": "input_audio_buffer.commit"})
        else:
            await self._send({"type": "input_audio_buffer.clear"})
        text = context if not question else f"{context}\n\nQuestion: {question}"
        await self._send(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": capture.data_url},
                        {"type": "input_text", "text": text},
                    ],
                },
            }
        )
        await self._send({"type": "response.create"})
        self._response_active = True
        self._turn_started_at = time.monotonic()

    async def cancel(self) -> None:
        self.player.stop()
        self.input_actions.abort(self._action_session)
        if self.websocket is not None and self._response_active:
            await self._send({"type": "response.cancel"})
        if self.websocket is not None:
            await self._send({"type": "input_audio_buffer.clear"})
        self._response_active = False

    async def close(self) -> None:
        self._closed = True
        self.input_actions.abort(self._action_session)
        self.player.close()
        websocket, self.websocket = self.websocket, None
        if websocket is not None:
            await websocket.close()

    async def run(self) -> None:
        delay = 1.0
        while not self._closed:
            try:
                if self.websocket is None:
                    await self.connect()
                    delay = 1.0
                event = await self._receive()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Realtime connection dropped; reconnecting", exc_info=True)
                self.on_event({"type": "connection.lost"})
                websocket, self.websocket = self.websocket, None
                if websocket is not None:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15)
                continue
            try:
                await self.handle_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Realtime event handler failed; keeping connection open")

    async def handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "response.created":
            self._response_active = True
        elif event_type in {"response.output_audio.delta", "response.audio.delta"}:
            audio = event.get("delta", "")
            if audio:
                self.player.enqueue(base64.b64decode(audio))
        elif event_type in {
            "response.output_audio_transcript.delta",
            "response.audio_transcript.delta",
            "conversation.item.input_audio_transcription.completed",
        }:
            self.on_event(event)
        elif event_type == "response.function_call_arguments.done":
            await self._execute_function_call(
                str(event.get("call_id") or ""),
                str(event.get("name") or ""),
                event.get("arguments") or "{}",
            )
            self.on_event(event)
        elif event_type == "response.done":
            response = event.get("response", {})
            self._response_active = False
            self._log_usage(response)
            await self._handle_response_done(response)
            self.on_event(event)
        else:
            self.on_event(event)

    async def _execute_function_call(self, call_id: str, name: str, arguments: str) -> str:
        if call_id in self._executed_call_ids:
            return self._tool_outputs[call_id]
        try:
            args = json.loads(arguments or "{}")
            if not isinstance(args, dict):
                raise ValueError("function arguments must be an object")
            if name in ACTION_TOOL_NAMES:
                loop = asyncio.get_running_loop()
                output = await loop.run_in_executor(
                    None,
                    partial(
                        self.input_actions.execute,
                        self._action_session,
                        name,
                        args,
                        self.capture,
                        self.elements,
                        self.image_array,
                        self.on_commands,
                        self.on_marks_visible,
                    ),
                )
            elif name == "save_recap":
                path = await asyncio.get_running_loop().run_in_executor(
                    None,
                    partial(
                        save_recap,
                        args.get("markdown", ""),
                        board_image=self.last_board_image,
                    ),
                )
                output = json.dumps({"ok": True, "path": str(path)})
            elif name in BOARD_TOOL_NAMES:
                output = await asyncio.get_running_loop().run_in_executor(
                    None,
                    partial(self.on_board_tool, name, args),
                )
            else:
                commands, output = execute_tool(
                    name,
                    args,
                    self.capture,  # type: ignore[arg-type]
                    self.elements,
                    self.image_array,
                )
                if commands:
                    self.on_commands(commands)
        except Exception as error:
            output = json.dumps({"ok": False, "error": str(error)})
        self._executed_call_ids.add(call_id)
        self._tool_outputs[call_id] = output
        return output

    async def _handle_response_done(self, response: dict[str, Any]) -> None:
        calls = [
            item for item in response.get("output", [])
            if item.get("type") == "function_call"
        ]
        if not calls:
            return
        self._tool_rounds += 1
        for call in calls:
            call_id = call.get("call_id", "")
            if not isinstance(call_id, str) or not call_id:
                continue
            if call_id in self._executed_call_ids:
                output = self._tool_outputs[call_id]
            elif response.get("status") == "cancelled":
                output = json.dumps({"ok": False, "error": "response cancelled"})
                self._executed_call_ids.add(call_id)
                self._tool_outputs[call_id] = output
            else:
                output = await self._execute_function_call(
                    call_id,
                    call.get("name", ""),
                    call.get("arguments") or "{}",
                )
            await self._send(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": output,
                    },
                }
            )
        action_succeeded = False
        for call in calls:
            call_id = call.get("call_id")
            if call.get("name") not in ACTION_TOOL_NAMES or not isinstance(call_id, str):
                continue
            try:
                action_succeeded |= json.loads(self._tool_outputs.get(call_id, "{}")).get("ok") is True
            except (TypeError, json.JSONDecodeError):
                continue
        if response.get("status") != "cancelled" and self._tool_rounds < 4:
            if action_succeeded:
                await self._refresh_after_action()
            await self._send({"type": "response.create"})
            self._response_active = True

    async def _refresh_after_action(self) -> None:
        if self.capture_after_action is None:
            return
        try:
            capture, elements, context = await asyncio.get_running_loop().run_in_executor(
                None,
                self.capture_after_action,
            )
            self.capture = capture
            self.image_array = np.asarray(capture.full_image or capture.image)
            self.elements = elements
            self.last_board_image = capture.full_image if "BOARD MODE" in context else None
            await self._send(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_image", "image_url": capture.data_url},
                            {"type": "input_text", "text": f"SCREEN AFTER YOUR ACTION\n{context}"},
                        ],
                    },
                }
            )
        except Exception:
            logger.warning("Could not capture the screen after an action", exc_info=True)
            await self._send(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "SCREEN AFTER YOUR ACTION: fresh capture unavailable.",
                            }
                        ],
                    },
                }
            )

    def _log_usage(self, response: dict[str, Any]) -> None:
        usage = response.get("usage")
        if not usage:
            return
        record = {
            "timestamp": time.time(),
            "model": self.model,
            "response_id": response.get("id"),
            "usage": usage,
            "latency_seconds": (
                round(time.monotonic() - self._turn_started_at, 3)
                if self._turn_started_at is not None
                else None
            ),
        }
        try:
            self.usage_log.parent.mkdir(parents=True, exist_ok=True)
            with self.usage_log.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")
        except OSError:
            logger.warning("Unable to write Realtime usage log", exc_info=True)
