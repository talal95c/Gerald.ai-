import asyncio
import json
import threading

from PIL import Image
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from gerald.brain.realtime import RealtimeClient
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.elements import Element
from gerald.tools.registry import ClearCommand, TipCommand
from gerald.tools.diagram import DiagramCommand


class RecordingPlayer:
    def __init__(self):
        self.stops = 0

    def stop(self):
        self.stops += 1

    def close(self):
        pass

    def enqueue(self, data):
        pass


def make_client(player=None):
    capture = capture_from_image(Image.new("RGB", (64, 48)), MonitorRect(0, 0, 64, 48))
    client = RealtimeClient(
        "test-key",
        "gpt-realtime-2",
        "marin",
        "exact instructions",
        player=player or RecordingPlayer(),
        usage_log=None,
    )
    client.capture = capture
    client.elements = [Element(1, "Button", "Save", (10, 10, 15, 12), "uia")]
    return client, capture


async def connected_client(server_handler, player=None):
    server = await serve(server_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client, capture = make_client(player)

    async def local_connect(_url, **kwargs):
        return await connect(f"ws://127.0.0.1:{port}", **kwargs)

    await client.connect(local_connect)
    return server, client, capture


def test_push_to_talk_sends_audio_commit_image_and_response_in_order():
    async def scenario():
        received = asyncio.Queue()

        async def server_handler(websocket):
            await received.put(json.loads(await websocket.recv()))
            await websocket.send(json.dumps({"type": "session.updated"}))
            async for message in websocket:
                await received.put(json.loads(message))

        server, client, capture = await connected_client(server_handler)
        try:
            await client.send_audio(b"\x01\x00")
            await client.finish_turn(capture, client.elements, "screen context", has_audio=True)
            sent = [await asyncio.wait_for(received.get(), 2) for _ in range(5)]
            assert sent[0]["type"] == "session.update"
            assert sent[1]["type"] == "input_audio_buffer.append"
            assert sent[2]["type"] == "input_audio_buffer.commit"
            assert sent[3]["type"] == "conversation.item.create"
            assert [part["type"] for part in sent[3]["item"]["content"]] == ["input_image", "input_text"]
            assert sent[4]["type"] == "response.create"
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_non_board_turn_clears_previous_board_recap_image():
    async def scenario():
        client, capture = make_client()

        async def record_send(_event):
            return None

        client._send = record_send
        await client.finish_turn(capture, client.elements, "BOARD MODE", has_audio=False)
        assert client.last_board_image is capture.full_image

        await client.finish_turn(capture, client.elements, "screen context", has_audio=False)
        assert client.last_board_image is None

    asyncio.run(scenario())


def test_function_round_trip_sends_one_followup_after_output():
    async def scenario():
        received = asyncio.Queue()

        async def server_handler(websocket):
            await websocket.recv()
            await websocket.send(json.dumps({"type": "session.updated"}))
            async for message in websocket:
                await received.put(json.loads(message))

        server, client, capture = await connected_client(server_handler)
        try:
            await client.finish_turn(capture, client.elements, "context", has_audio=False)
            initial = [await asyncio.wait_for(received.get(), 2) for _ in range(3)]
            assert [event["type"] for event in initial] == [
                "input_audio_buffer.clear",
                "conversation.item.create",
                "response.create",
            ]
            drawn = []
            client.on_commands = drawn.extend
            await client.handle_event(
                {
                    "type": "response.function_call_arguments.done",
                    "response_id": "response-1",
                    "call_id": "call-1",
                    "name": "clear",
                    "arguments": "{}",
                }
            )
            assert drawn == [ClearCommand()]
            assert received.empty()
            await client.handle_event(
                {
                    "type": "response.done",
                    "response": {
                        "id": "response-1",
                        "status": "completed",
                        "output": [
                            {
                                "type": "function_call",
                                "name": "clear",
                                "call_id": "call-1",
                                "arguments": "{}",
                            }
                        ]
                    },
                }
            )
            output = await asyncio.wait_for(received.get(), 2)
            followup = await asyncio.wait_for(received.get(), 2)
            assert output["item"]["type"] == "function_call_output"
            assert output["item"]["call_id"] == "call-1"
            assert json.loads(output["item"]["output"]) == {"ok": True}
            assert followup["type"] == "response.create"
            assert drawn == [ClearCommand()]
            assert client._tool_rounds == 1
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_cancelled_tool_response_does_not_create_followup():
    async def scenario():
        received = asyncio.Queue()

        async def server_handler(websocket):
            await websocket.recv()
            await websocket.send(json.dumps({"type": "session.updated"}))
            async for message in websocket:
                await received.put(json.loads(message))

        server, client, capture = await connected_client(server_handler)
        try:
            await client.finish_turn(capture, client.elements, "context", has_audio=False)
            initial = [await asyncio.wait_for(received.get(), 2) for _ in range(3)]
            assert [event["type"] for event in initial] == [
                "input_audio_buffer.clear",
                "conversation.item.create",
                "response.create",
            ]
            await client.handle_event(
                {
                    "type": "response.done",
                    "response": {
                        "status": "cancelled",
                        "output": [
                            {
                                "type": "function_call",
                                "name": "clear",
                                "call_id": "cancelled-call",
                                "arguments": "{}",
                            }
                        ],
                    },
                }
            )
            output = await asyncio.wait_for(received.get(), 2)
            assert output["item"]["type"] == "function_call_output"
            assert json.loads(output["item"]["output"]) == {
                "ok": False,
                "error": "response cancelled",
            }
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(received.get(), 0.05)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_tool_round_cap_is_four():
    async def scenario():
        received = asyncio.Queue()

        async def server_handler(websocket):
            await websocket.recv()
            await websocket.send(json.dumps({"type": "session.updated"}))
            async for message in websocket:
                await received.put(json.loads(message))

        server, client, capture = await connected_client(server_handler)
        try:
            await client.finish_turn(capture, client.elements, "context", has_audio=False)
            initial = [await asyncio.wait_for(received.get(), 2) for _ in range(3)]
            assert [event["type"] for event in initial] == [
                "input_audio_buffer.clear",
                "conversation.item.create",
                "response.create",
            ]
            for round_number in range(4):
                await client.handle_event(
                    {
                        "type": "response.done",
                        "response": {
                            "output": [
                                {
                                    "type": "function_call",
                                    "name": "clear",
                                    "call_id": f"call-{round_number}",
                                    "arguments": "{}",
                                }
                            ]
                        },
                    }
                )
            followups = [await asyncio.wait_for(received.get(), 2) for _ in range(7)]
            assert sum(event["type"] == "response.create" for event in followups) == 3
            assert sum(
                event.get("item", {}).get("type") == "function_call_output" for event in followups
            ) == 4
            assert client._tool_rounds == 4
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_post_action_capture_precedes_the_followup_response():
    async def scenario():
        client, capture = make_client()
        sent = []

        async def fake_send(event):
            sent.append(event)

        fresh_elements = [Element(1, "Button", "Done", (20, 20, 10, 10), "uia")]
        client._send = fake_send
        client.capture_after_action = lambda: (capture, fresh_elements, "new context")
        client._executed_call_ids.add("click-1")
        client._tool_outputs["click-1"] = '{"ok":true,"action":"click"}'

        await client._handle_response_done(
            {
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "name": "click",
                        "call_id": "click-1",
                        "arguments": "{}",
                    }
                ],
            }
        )

        assert [event["type"] for event in sent] == [
            "conversation.item.create",
            "conversation.item.create",
            "response.create",
        ]
        assert sent[0]["item"]["type"] == "function_call_output"
        assert sent[1]["item"]["content"][0]["type"] == "input_image"
        assert sent[1]["item"]["content"][1]["text"] == "SCREEN AFTER YOUR ACTION\nnew context"
        assert client.elements == fresh_elements

    asyncio.run(scenario())


def test_lesson_recap_sends_a_text_only_request():
    async def scenario():
        client, _capture = make_client()
        sent = []

        async def fake_send(event):
            sent.append(event)

        client._send = fake_send
        await client.send_recap()

        assert [event["type"] for event in sent] == [
            "conversation.item.create",
            "response.create",
        ]
        assert sent[0]["item"]["content"] == [
            {
                "type": "input_text",
                "text": (
                    "Fais un récap écrit de cette leçon : ce qu'on a vu, les étapes clés, "
                    "3 points à retenir, et un mini exercice. Réponds par l'outil save_recap."
                ),
            }
        ]

    asyncio.run(scenario())


def test_barge_in_cancels_response_and_stops_player():
    async def scenario():
        received = asyncio.Queue()
        player = RecordingPlayer()

        async def server_handler(websocket):
            await websocket.recv()
            await websocket.send(json.dumps({"type": "session.updated"}))
            async for message in websocket:
                await received.put(json.loads(message))

        server, client, _capture = await connected_client(server_handler, player)
        try:
            client._response_active = True
            await client.start_turn()
            assert (await asyncio.wait_for(received.get(), 2))["type"] == "response.cancel"
            assert player.stops == 1
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_search_courses_dispatches_in_executor_and_returns_json_results():
    async def scenario():
        client, _capture = make_client()
        caller_thread = threading.get_ident()
        calls = []

        def search_courses(query, course):
            calls.append((threading.get_ident(), query, course))
            return {
                "ok": True,
                "results": [
                    {"course": "Biologie", "document": "cours.pdf", "page": 2, "text": "Cellules"}
                ],
            }

        client.on_course_search = search_courses
        output = await client._execute_function_call(
            "search-call",
            "search_courses",
            json.dumps({"query": "cellules", "course": "Biologie"}),
        )

        assert calls[0][0] != caller_thread
        assert calls[0][1:] == ("cellules", "Biologie")
        assert json.loads(output) == {
            "ok": True,
            "results": [
                {"course": "Biologie", "document": "cours.pdf", "page": 2, "text": "Cellules"}
            ],
        }

    asyncio.run(scenario())


def test_tip_and_diagram_tools_are_dispatched_to_overlay_commands():
    async def scenario():
        client, _capture = make_client()
        commands = []
        client.on_commands = commands.extend

        tip_output = await client._execute_function_call(
            "tip-call",
            "tip",
            json.dumps({"text": "Cherche le mot important"}),
        )
        diagram_output = await client._execute_function_call(
            "diagram-call",
            "diagram",
            json.dumps(
                {
                    "layout": "flow",
                    "nodes": [{"id": "a", "text": "Départ"}, {"id": "b", "text": "Arrivée"}],
                    "edges": [{"from": "a", "to": "b"}],
                },
                ensure_ascii=False,
            ),
        )

        assert json.loads(tip_output)["ok"] is True
        assert isinstance(commands[0], TipCommand)
        assert commands[0].text == "Cherche le mot important"
        assert json.loads(diagram_output)["ok"] is True
        assert isinstance(commands[1], DiagramCommand)
        assert commands[1].layout.nodes[0].id == "a"

    asyncio.run(scenario())


def test_plot_tool_is_dispatched_to_board_callback():
    async def scenario():
        client, _capture = make_client()
        calls = []
        client.on_board_tool = lambda name, args: calls.append((name, args)) or '{"ok":true}'
        args = {"functions": [{"expr": "x**2"}], "x_min": -1, "x_max": 1}

        output = await client._execute_function_call(
            "plot-call",
            "plot",
            json.dumps(args),
        )

        assert output == '{"ok":true}'
        assert calls == [("plot", args)]

    asyncio.run(scenario())


def test_agent_history_records_typed_and_transcribed_turns_but_not_recap(tmp_path):
    from gerald.library.store import Store

    store = Store(tmp_path / "library")
    client, _capture = make_client()
    client.store = store
    user_text = "Explique le rôle des mitochondries et donne un exemple concret pour mon cours."
    sent = []
    client._send = lambda event: asyncio.sleep(0, result=sent.append(event))

    async def scenario():
        await client.handle_event(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": user_text,
            }
        )
        client.record_user_message("Question tapée depuis le clavier.")
        await client.handle_event(
            {
                "type": "response.output_audio_transcript.done",
                "transcript": "Elles produisent l'énergie de la cellule.",
            }
        )
        await client.send_recap()

    asyncio.run(scenario())
    conversation = store.recent_conversations(source="agent")[0]
    messages = store.get_messages(conversation.id)

    assert conversation.title == user_text[:60]
    assert [message.role for message in messages] == ["user", "user", "assistant"]
    assert [message.text for message in messages] == [
        user_text,
        "Question tapée depuis le clavier.",
        "Elles produisent l'énergie de la cellule.",
    ]
    assert "Fais un récap écrit" in sent[0]["item"]["content"][0]["text"]
    store.close()


def test_update_instructions_sends_only_when_connected():
    class WebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, event):
            self.sent.append(json.loads(event))

    async def scenario():
        client, _capture = make_client()
        websocket = WebSocket()
        client.websocket = websocket

        assert not await client.update_instructions("new while offline")
        assert websocket.sent == []
        assert client.instructions == "new while offline"

        client._connected = True
        assert await client.update_instructions("updated profile")
        assert len(websocket.sent) == 1
        assert websocket.sent[0]["type"] == "session.update"
        assert websocket.sent[0]["session"]["instructions"] == "updated profile"

    asyncio.run(scenario())


def test_event_handler_exception_keeps_the_connection_open():
    async def scenario():
        incoming = asyncio.Queue()
        handled_second_event = asyncio.Event()
        player = RecordingPlayer()
        client = RealtimeClient(
            "test-key",
            "gpt-realtime-2",
            "marin",
            "exact instructions",
            player=player,
            usage_log=None,
        )
        connection_count = 0

        class FakeWebSocket:
            async def recv(self):
                return json.dumps(await incoming.get())

            async def close(self):
                pass

        async def connect_once():
            nonlocal connection_count
            connection_count += 1
            client.websocket = FakeWebSocket()

        async def handle_event(event):
            if event["type"] == "bad":
                raise RuntimeError("simulated handler failure")
            handled_second_event.set()

        client.connect = connect_once
        client.handle_event = handle_event
        await incoming.put({"type": "bad"})
        await incoming.put({"type": "good"})
        runner = asyncio.create_task(client.run())
        try:
            await asyncio.wait_for(handled_second_event.wait(), 2)
        finally:
            runner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await runner
            await client.close()

        assert connection_count == 1

    asyncio.run(scenario())
