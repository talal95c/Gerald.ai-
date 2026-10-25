import asyncio
import json

from PIL import Image
import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from gerald.brain.realtime import RealtimeClient
from gerald.capture.screen import MonitorRect, capture_from_image
from gerald.perception.elements import Element
from gerald.tools.registry import ClearCommand


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
