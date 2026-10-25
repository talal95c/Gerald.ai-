from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import sys
import threading
import time
from pathlib import Path

from gerald.config import load_settings, set_physical_dpi_awareness

logger = logging.getLogger(__name__)


def _key_name(key: object) -> str:
    value = str(key).lower()
    if value.endswith("enter"):
        return "enter"
    if "alt_gr" in value:
        return "altgr"
    if "ctrl" in value:
        return "ctrl"
    if "shift" in value:
        return "shift"
    if "alt" in value:
        return "alt"
    char = getattr(key, "char", None)
    if char:
        return char.lower()
    return value.removeprefix("key.").removeprefix("key.")


def main() -> int:
    set_physical_dpi_awareness()
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QApplication,
        QMenu,
        QMessageBox,
        QStyle,
        QSystemTrayIcon,
    )
    from pynput import keyboard

    from gerald.audio.mic import Microphone
    from gerald.brain.realtime import RealtimeClient
    from gerald.capture.session import CaptureRequest
    from gerald.capture.screen import capture_screen
    from gerald.overlay.window import OverlayWindow
    from gerald.perception.elements import collect_elements_detailed, serialize_context

    settings = load_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not settings.api_key:
        QMessageBox.critical(None, "Gerald", "Clé API manquante : définissez OPENAI_API_KEY dans .env.")
        return 1

    class Bridge(QObject):
        key_down = pyqtSignal(str)
        key_up = pyqtSignal(str)
        realtime_event = pyqtSignal(dict)
        commands = pyqtSignal(list)
        capture_ready = pyqtSignal(object)
        capture_failed = pyqtSignal(str)
        mic_level = pyqtSignal(float)
        output_level = pyqtSignal(float)
        audio_unavailable = pyqtSignal()
        action_marks_visible = pyqtSignal(bool)

    bridge = Bridge()
    overlay = OverlayWindow()
    overlay.show()
    def capture_after_action():
        capture = capture_screen(settings.max_image_width)
        collection = collect_elements_detailed(capture)
        context = serialize_context(
            collection.elements,
            capture.image_width,
            capture.image_height,
        )
        return capture, collection.elements, context

    prompt = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
    client = RealtimeClient(
        settings.api_key,
        settings.model,
        settings.voice,
        prompt,
        require_confirmation=settings.require_confirmation,
        capture_after_action=capture_after_action,
        on_marks_visible=bridge.action_marks_visible.emit,
    )
    client.on_event = bridge.realtime_event.emit
    client.on_commands = bridge.commands.emit
    client.player.on_unavailable = bridge.audio_unavailable.emit
    client.player.on_level = bridge.output_level.emit

    loop = asyncio.new_event_loop()

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        loop.create_task(client.run())
        loop.run_forever()

    threading.Thread(target=run_loop, name="gerald-realtime", daemon=True).start()

    def schedule(coroutine) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)

        def report(error_future) -> None:
            try:
                error_future.result()
            except Exception as error:
                logger.warning("Realtime action failed: %s", error)
                bridge.capture_failed.emit(str(error))

        future.add_done_callback(report)

    app_state = {
        "pressed": set(),
        "active": False,
        "released": False,
        "started": 0.0,
        "audio_bytes": 0,
        "capture": None,
        "capture_request": None,
        "capture_generation": 0,
        "connected": False,
        "typed": False,
        "response_active": False,
        "recap_pending": False,
    }
    required = {part.strip().lower() for part in settings.hotkey.split("+") if part.strip()}
    if "altgr" in required or {"ctrl", "alt"} <= required:
        QMessageBox.critical(None, "Gerald", "Alt et Ctrl+Alt ne sont pas pris en charge comme raccourci.")
        return 1
    if not required or "enter" in required:
        QMessageBox.critical(None, "Gerald", "GERALD_HOTKEY doit être un raccourci de maintien, par exemple ctrl+shift.")
        return 1
    typed_hotkey = required | {"enter"}
    capture_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gerald-capture")
    partial_capture_lock = threading.Lock()
    partial_capture: dict[str, object] = {"capture": None, "elements": []}

    def collect_capture(started_at: float | None):
        capture = capture_screen(settings.max_image_width)
        with partial_capture_lock:
            partial_capture.update(capture=capture, elements=[])

        def publish_elements(elements) -> None:
            with partial_capture_lock:
                partial_capture["elements"] = list(elements)

        collection = collect_elements_detailed(
            capture,
            budget=settings.ocr_budget,
            started_at=started_at,
            on_update=publish_elements,
        )
        publish_elements(collection.elements)
        if not collection.complete:
            logger.warning(
                "OCR collection incomplete; using %d collected screen elements",
                len(collection.elements),
            )
        context = serialize_context(
            collection.elements,
            capture.image_width,
            capture.image_height,
        )
        return capture, collection.elements, context

    def on_microphone_audio(audio: bytes, level: float) -> None:
        bridge.mic_level.emit(level)
        if not app_state["active"] or not app_state["connected"]:
            return
        schedule(client.send_audio(audio))
        if level > 0.015:
            app_state["audio_bytes"] += len(audio)

    audio_capability = {"available": True}

    def audio_unavailable() -> None:
        audio_capability["available"] = False
        overlay.set_status("error")

    bridge.audio_unavailable.connect(audio_unavailable)
    mic = Microphone(on_microphone_audio, bridge.audio_unavailable.emit)
    audio_capability["available"] = mic.available and client.player.available
    if not audio_capability["available"]:
        overlay.set_status("error")

    def begin_capture(typed: bool = False, question: str = "") -> None:
        app_state["typed"] = typed
        app_state["question"] = question
        app_state["released"] = False
        app_state["capture"] = None
        with partial_capture_lock:
            partial_capture.update(capture=None, elements=[])
        previous_request = app_state.get("capture_request")
        if previous_request is not None:
            previous_request.cancel()
        app_state["capture_generation"] += 1
        generation = app_state["capture_generation"]
        overlay.clear()
        overlay.hide()
        app.processEvents()
        request = CaptureRequest(capture_executor, lambda: collect_capture(request.started_at))
        request.start_on_press()
        app_state["capture_request"] = request
        app_state["capture_generation_for_request"] = generation

    def await_capture_after_release() -> None:
        request = app_state.get("capture_request")
        if request is None:
            return
        generation = app_state["capture_generation_for_request"]

        async def wait_for_capture() -> None:
            try:
                started_at = request.started_at or time.monotonic()
                remaining = max(0.0, settings.ocr_budget - (time.monotonic() - started_at))
                captured = await request.wait_on_release(timeout=remaining)
            except asyncio.CancelledError:
                return
            except TimeoutError:
                with partial_capture_lock:
                    capture = partial_capture["capture"]
                    elements = list(partial_capture["elements"])
                if capture is None:
                    bridge.capture_failed.emit("Capture d'écran indisponible après expiration du budget OCR.")
                    return
                logger.warning(
                    "OCR collection exceeded the remaining budget; using %d completed elements",
                    len(elements),
                )
                context = serialize_context(
                    elements,
                    capture.image_width,
                    capture.image_height,
                )
                captured = capture, elements, context
            except Exception as error:
                bridge.capture_failed.emit(str(error))
                return
            bridge.capture_ready.emit((generation, captured))

        asyncio.run_coroutine_threadsafe(wait_for_capture(), loop)

    def start_hold() -> None:
        if app_state["active"]:
            return
        if not app_state["connected"]:
            bridge.capture_failed.emit("Gerald attend la connexion Realtime. Réessayez dans un instant.")
            return
        app_state.update(
            active=True,
            started=time.monotonic(),
            audio_bytes=0,
            released=False,
            typed=False,
            recap_pending=False,
        )
        schedule(client.start_turn())
        overlay.clear()
        overlay.set_status("listening" if audio_capability["available"] else "error")
        try:
            mic.start()
        except RuntimeError as error:
            bridge.capture_failed.emit(str(error))
            app_state["active"] = False
            overlay.set_status("idle")
            return
        begin_capture()

    def send_captured_if_ready() -> None:
        captured = app_state["capture"]
        if captured is None or not app_state["released"]:
            return
        capture, elements, context = captured
        app_state["capture"] = None
        has_audio = app_state["audio_bytes"] > 0
        duration = time.monotonic() - app_state["started"]
        question = app_state.pop("question", "")
        if not has_audio and not question and duration < 0.3:
            question = "explique ce que je regarde"
        app_state["active"] = False
        overlay.set_status("thinking" if audio_capability["available"] else "error")
        schedule(client.finish_turn(capture, elements, context, question, has_audio))

    def release_hold() -> None:
        if not app_state["active"] or app_state["typed"]:
            return
        mic.stop()
        app_state["released"] = True
        await_capture_after_release()

    def open_typed_question() -> None:
        if app_state["active"] and app_state["typed"]:
            return
        if not app_state["connected"]:
            bridge.capture_failed.emit("Gerald attend la connexion Realtime. Réessayez dans un instant.")
            return
        already_active = app_state["active"]
        if already_active:
            mic.stop()
            app_state.update(started=time.monotonic(), audio_bytes=0, released=False, typed=True)
        else:
            app_state.update(active=True, started=time.monotonic(), audio_bytes=0, released=False, typed=True)
            schedule(client.start_turn())
        overlay.set_status("thinking" if audio_capability["available"] else "error")
        if not already_active:
            begin_capture(True)
        overlay.open_text_input(submit_typed_question, cancel_typed_question)

    def submit_typed_question(question: str) -> None:
        if not question.strip() or not app_state["active"] or not app_state["typed"]:
            return
        app_state["question"] = question.strip()
        app_state["released"] = True
        overlay.close_text_input()
        await_capture_after_release()

    def cancel_typed_question() -> None:
        if not app_state["active"] or not app_state["typed"]:
            return
        request = app_state.get("capture_request")
        if request is not None:
            request.cancel()
        app_state["capture_generation"] += 1
        app_state.update(active=False, released=False, capture=None, capture_request=None)
        schedule(client.cancel())
        overlay.close_text_input()
        overlay.show()
        overlay.set_status("idle" if audio_capability["available"] else "error")

    def open_lesson_recap() -> None:
        if app_state["recap_pending"]:
            return
        mic.stop()
        request = app_state.get("capture_request")
        if request is not None:
            request.cancel()
        app_state["capture_generation"] += 1
        app_state.update(
            active=False,
            released=False,
            capture=None,
            capture_request=None,
            typed=False,
            recap_pending=True,
            response_active=False,
        )
        overlay.close_text_input()
        schedule(client.send_recap())

    def key_press(name: str) -> None:
        app_state["pressed"].add(name)
        if name == "esc" and app_state["active"] and app_state["typed"]:
            cancel_typed_question()
            return
        if name == "esc" and (
            app_state["active"] or app_state["response_active"] or app_state["recap_pending"]
        ):
            mic.stop()
            app_state.update(active=False, released=True, response_active=False)
            request = app_state.get("capture_request")
            if request is not None:
                request.cancel()
            app_state["capture_generation"] += 1
            app_state["capture"] = None
            app_state["recap_pending"] = False
            schedule(client.cancel())
            overlay.clear()
            if not audio_capability["available"]:
                overlay.set_status("error")
            return
        if (required | {"r"}) <= app_state["pressed"]:
            open_lesson_recap()
            return
        if typed_hotkey <= app_state["pressed"]:
            open_typed_question()
        elif required <= app_state["pressed"] and "enter" not in app_state["pressed"]:
            start_hold()

    def key_release(name: str) -> None:
        app_state["pressed"].discard(name)
        if app_state["active"] and required - app_state["pressed"]:
            release_hold()

    bridge.key_down.connect(key_press)
    bridge.key_up.connect(key_release)
    def capture_ready(result) -> None:
        generation, captured = result
        if generation == app_state["capture_generation"] and app_state["active"]:
            app_state["capture"] = captured
            overlay.set_capture(captured[0])
            overlay.show()
            send_captured_if_ready()

    bridge.capture_ready.connect(capture_ready)
    bridge.capture_failed.connect(
            lambda message: (
                overlay.show(),
                overlay.set_status("idle" if audio_capability["available"] else "error"),
                logger.warning("Capture/audio error: %s", message),
            QMessageBox.warning(None, "Gerald", message),
        )
    )
    bridge.commands.connect(overlay.add_commands)
    bridge.action_marks_visible.connect(overlay.set_marks_visible)
    bridge.mic_level.connect(
        lambda level: overlay.set_status(
            "listening" if audio_capability["available"] else "error",
            mic_level=level,
        )
    )
    bridge.output_level.connect(
        lambda level: overlay.set_status(
            "speaking" if audio_capability["available"] else "error",
            output_level=level,
        )
    )

    caption = {"text": ""}

    def on_realtime_event(event: dict) -> None:
        event_type = event.get("type")
        if event_type == "session.updated":
            app_state["connected"] = True
        elif event_type == "response.created":
            overlay.set_status("thinking" if audio_capability["available"] else "error")
            caption["text"] = ""
            app_state["response_active"] = True
            app_state["recap_pending"] = False
        elif event_type in {"response.output_audio.delta", "response.audio.delta"}:
            overlay.set_status("speaking" if audio_capability["available"] else "error")
        elif event_type in {"response.output_audio.done", "response.audio.done", "response.done"}:
            overlay.set_status("idle" if audio_capability["available"] else "error")
            app_state["response_active"] = client._response_active
            if event_type == "response.done" and not client._response_active:
                app_state["recap_pending"] = False
        elif event_type == "connection.lost":
            app_state["connected"] = False
        elif event_type in {"response.output_audio_transcript.delta", "response.audio_transcript.delta"}:
            caption["text"] += event.get("delta", "")
            overlay.set_caption(caption["text"])
        elif event_type == "conversation.item.input_audio_transcription.completed":
            caption["text"] = event.get("transcript", "")
            overlay.set_caption(caption["text"])

    bridge.realtime_event.connect(on_realtime_event)
    tray = QSystemTrayIcon(QIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)), app)
    menu = QMenu()
    text_action = menu.addAction("Poser une question…")
    text_action.triggered.connect(open_typed_question)
    recap_action = menu.addAction("Récap de la leçon")
    recap_action.triggered.connect(open_lesson_recap)
    menu.addSeparator()
    quit_action = menu.addAction("Quitter Gerald")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.setToolTip("Gerald — maintenez Ctrl+Maj pour parler")
    tray.show()

    def on_press(key) -> None:
        bridge.key_down.emit(_key_name(key))

    def on_release(key) -> None:
        bridge.key_up.emit(_key_name(key))

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    cleanup_done = {"value": False}

    def cleanup() -> None:
        if cleanup_done["value"]:
            return
        cleanup_done["value"] = True
        listener.stop()
        mic.stop()
        capture_executor.shutdown(wait=False, cancel_futures=True)
        overlay.close()
        try:
            asyncio.run_coroutine_threadsafe(client.close(), loop).result(timeout=2)
        except Exception:
            logger.debug("Realtime client cleanup did not finish", exc_info=True)
        loop.call_soon_threadsafe(loop.stop)

    app.aboutToQuit.connect(cleanup)
    try:
        return app.exec()
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
