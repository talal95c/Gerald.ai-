from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

from gerald.capture.screen import Capture
from gerald.config import load_settings, set_physical_dpi_awareness

logger = logging.getLogger(__name__)
AUDIO_BYTES_FOR_100MS = 24000 * 2 // 10
PTT_KEY_CONFLICT_WINDOW_SECONDS = 0.4
PTT_REALTIME_START_DELAY_MS = 450


def _has_audio_to_commit(audio_sent_bytes: int) -> bool:
    return audio_sent_bytes >= AUDIO_BYTES_FOR_100MS


def _should_hide_overlay_for_capture(capture_excluded: bool, platform: str | None = None) -> bool:
    return (platform or os.name) != "nt" or not capture_excluded


def _reset_failed_capture(app_state: dict, generation: int) -> bool:
    if generation != app_state["capture_generation"] or not app_state["active"]:
        return False
    request = app_state.get("capture_request")
    if request is not None:
        request.cancel()
    app_state.update(
        capture_generation=generation + 1,
        capture=None,
        capture_request=None,
        active=False,
        released=False,
        audio_sent_bytes=0,
    )
    return True


def _dispatch_key_after_hold_conflict(
    app_state: dict,
    name: str,
    pressed_at: float,
    cancel_hold,
    dispatch,
) -> bool:
    if name == "esc":
        dispatch()
        return True
    if app_state.get("active") and not app_state.get("typed") and name not in {
        "ctrl",
        "shift",
        "alt",
        "altgr",
    }:
        if app_state.get("released"):
            return False
        if pressed_at - app_state["started"] >= PTT_KEY_CONFLICT_WINDOW_SECONDS:
            return False
        cancel_hold()
    dispatch()
    return True


def _cancel_turn_for_escape(app_state: dict, mic, audio_lock, cancel_turn) -> None:
    with audio_lock:
        request = app_state.get("capture_request")
        app_state.update(
            active=False,
            released=True,
            response_active=False,
            capture_generation=app_state["capture_generation"] + 1,
            capture=None,
            capture_request=None,
            audio_sent_bytes=0,
            realtime_turn_started=False,
            recap_pending=False,
        )
        app_state.get("pending_audio", []).clear()
    if request is not None:
        request.cancel()
    mic.stop()
    cancel_turn()


def _discard_early_hold(app_state: dict, mic, overlay, audio_lock) -> None:
    with audio_lock:
        request = app_state.get("capture_request")
        app_state.update(
            capture_generation=app_state["capture_generation"] + 1,
            capture=None,
            capture_request=None,
            active=False,
            released=False,
            audio_sent_bytes=0,
            realtime_turn_started=False,
        )
        app_state["pending_audio"].clear()
    if request is not None:
        request.cancel()
    mic.stop()
    overlay.set_status("idle")


def _activate_hold_turn(
    app_state: dict,
    generation: int,
    audio_lock,
    start_turn,
    send_audio,
) -> bool:
    with audio_lock:
        if (
            not app_state["active"]
            or app_state["typed"]
            or app_state["capture_generation"] != generation
            or app_state["realtime_turn_started"]
        ):
            return False
        start_turn()
        pending_audio = app_state["pending_audio"]
        app_state["pending_audio"] = []
        app_state["realtime_turn_started"] = True
        app_state["audio_sent_bytes"] += sum(len(audio) for audio in pending_audio)
        for audio in pending_audio:
            send_audio(audio)
    return True


def _restore_capture_visual_state(app_state: dict, overlay, set_capture_overlay_visibility) -> None:
    if app_state.get("capture_overlay_hidden"):
        app_state["capture_overlay_hidden"] = False
        set_capture_overlay_visibility(True)
    if app_state.get("capture_marks_hidden"):
        app_state["capture_marks_hidden"] = False
        overlay.set_marks_visible(True)


def _show_offline_status(overlay) -> None:
    overlay.show()
    overlay.set_status("offline")


def _show_runtime_error(
    overlay,
    message: str,
    app_state: dict | None = None,
    set_capture_overlay_visibility=None,
) -> None:
    if app_state is not None:
        _restore_capture_visual_state(app_state, overlay, set_capture_overlay_visibility)
    overlay.show()
    if overlay.show_timed_error(message):
        logger.warning("Runtime capture/audio error: %s", message)


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
    codepoint = ord(char) if isinstance(char, str) and len(char) == 1 else None
    if char is None or (codepoint is not None and (codepoint < 32 or 127 <= codepoint <= 159)):
        virtual_key = getattr(key, "vk", None)
        if isinstance(virtual_key, int):
            if 0x41 <= virtual_key <= 0x5A:
                return chr(virtual_key).lower()
            if 0x30 <= virtual_key <= 0x39:
                return chr(virtual_key)
        if codepoint is not None and 0x01 <= codepoint <= 0x1A:
            return chr(codepoint + 0x60)
    if char:
        return char.lower()
    return value.removeprefix("key.").removeprefix("key.")


def _include_board_ink(elements, capture: Capture, board_rects: list[tuple[int, int, int, int]]):
    from gerald.perception.elements import Element

    result = list(elements)
    next_id = max((element.id for element in result), default=-1) + 1
    for index, rect in enumerate(board_rects):
        result.append(
            Element(
                next_id + index,
                "ink",
                f"ink {index + 1}",
                capture.rect_to_image(rect),
                "board",
            )
        )
    return result


def _finalize_board_collection(
    elements,
    capture: Capture,
    board_rects: list[tuple[int, int, int, int]],
    partial_capture: dict[str, object],
):
    final_elements = _include_board_ink(elements, capture, board_rects)
    partial_capture["elements"] = final_elements
    return final_elements


def main() -> int:
    set_physical_dpi_awareness()
    from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QApplication,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QLineEdit,
        QMenu,
        QMessageBox,
        QStyle,
        QSystemTrayIcon,
        QVBoxLayout,
    )
    from pynput import keyboard

    from gerald.audio.mic import Microphone
    from gerald.board import BoardWindow
    from gerald.brain.realtime import RealtimeClient
    from gerald.capture.session import CaptureRequest
    from gerald.capture.screen import capture_screen
    from gerald.overlay.window import OverlayWindow
    from gerald.perception.grounder import (
        load_moondream_cloud_settings,
        save_moondream_cloud_settings,
        set_runtime_grounder_backend,
    )
    from gerald.perception.elements import collect_elements_detailed, serialize_context
    from gerald.library import Indexer, OpenAIEmbedder, Store
    from gerald.library.context import course_search_results, profile_block
    try:
        from gerald.home import open_home
    except ImportError:
        open_home = None

    settings = load_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not settings.api_key:
        QMessageBox.critical(None, "Gerald", "Clé API manquante : définissez OPENAI_API_KEY dans .env.")
        return 1
    store = Store()
    embedder = OpenAIEmbedder(settings.api_key)
    indexer = Indexer(store, embedder)

    class Bridge(QObject):
        key_down = pyqtSignal(str, float)
        key_up = pyqtSignal(str)
        realtime_event = pyqtSignal(dict)
        commands = pyqtSignal(list)
        capture_ready = pyqtSignal(object)
        capture_failed = pyqtSignal(str)
        capture_terminal_failed = pyqtSignal(object)
        capture_overlay = pyqtSignal(object)
        action_confirmation = pyqtSignal(object)
        confirmation_expired = pyqtSignal(str)
        board_tool = pyqtSignal(object)
        board_snapshot = pyqtSignal(object)
        mic_level = pyqtSignal(float)
        output_level = pyqtSignal(float)
        audio_unavailable = pyqtSignal()
        action_marks_visible = pyqtSignal(object)

    bridge = Bridge()
    overlay = OverlayWindow()
    board = BoardWindow()
    overlay.show()

    def request_board_snapshot():
        completed = threading.Event()
        result = {}
        bridge.board_snapshot.emit((completed, result))
        if not completed.wait(5):
            raise TimeoutError("Board capture timed out")
        return result.get("snapshot")

    def execute_board_tool(name, args):
        completed = threading.Event()
        result = {}
        bridge.board_tool.emit((name, args, completed, result))
        if not completed.wait(15):
            return '{"ok":false,"error":"board tool timed out"}'
        return result.get("output", '{"ok":false,"error":"board tool failed"}')

    def set_capture_overlay_visibility(visible: bool, *, clear: bool = False) -> None:
        if clear:
            overlay.clear()
        if visible:
            overlay.show()
        else:
            overlay.hide()
        app.processEvents()

    def set_action_marks_visible(visible: bool) -> None:
        completed = threading.Event()
        bridge.action_marks_visible.emit((visible, completed))
        if not completed.wait(5):
            if not visible:
                raise TimeoutError("Overlay mark hide timed out")
            logger.warning("Overlay mark restore timed out")
        else:
            app_state["capture_marks_hidden"] = not visible

    def capture_after_action():
        ready = threading.Event()
        hide_overlay = _should_hide_overlay_for_capture(overlay.capture_excluded)
        if hide_overlay:
            bridge.capture_overlay.emit((False, False, ready))
            if not ready.wait(5):
                raise TimeoutError("Overlay capture hide timed out")
        try:
            snapshot = request_board_snapshot()
            return collect_capture(time.monotonic(), snapshot)
        finally:
            if hide_overlay:
                restored = threading.Event()
                bridge.capture_overlay.emit((True, False, restored))
                if not restored.wait(5):
                    logger.warning("Overlay capture restore timed out")

    def request_action_confirmation(text, point, timeout) -> bool:
        import uuid

        token = uuid.uuid4().hex
        completion = threading.Event()
        result = {"approved": False, "expired": False}
        bridge.action_confirmation.emit((text, point, completion, result, token))
        if not completion.wait(timeout):
            result["expired"] = True
            bridge.confirmation_expired.emit(token)
            return False
        return bool(result["approved"]) and not result["expired"]

    prompt = (Path(__file__).parent / "prompts" / "system_prompt.md").read_text(encoding="utf-8")

    def current_agent_instructions() -> str:
        return f"{prompt.rstrip()}\n\n{profile_block(store)}"

    def search_course_documents(query: str, course: str | None = None) -> str:
        return json.dumps(
            course_search_results(store, embedder, query, course),
            ensure_ascii=False,
        )

    client = RealtimeClient(
        settings.api_key,
        settings.model,
        settings.voice,
        current_agent_instructions(),
        require_confirmation=settings.require_confirmation,
        request_action_confirmation=request_action_confirmation,
        on_board_tool=execute_board_tool,
        on_course_search=search_course_documents,
        capture_after_action=capture_after_action,
        on_marks_visible=set_action_marks_visible,
        store=store,
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

    def on_library_changed() -> None:
        schedule(client.update_instructions(current_agent_instructions()))

    home_window = {"widget": None}

    def open_home_window() -> None:
        if open_home is None:
            return
        if home_window["widget"] is None:
            home_window["widget"] = open_home(
                store,
                indexer,
                settings,
                on_library_changed,
            )
        home_window["widget"].show()
        home_window["widget"].raise_()
        home_window["widget"].activateWindow()

    app_state = {
        "pressed": set(),
        "active": False,
        "released": False,
        "started": 0.0,
        "audio_sent_bytes": 0,
        "capture": None,
        "capture_request": None,
        "capture_generation": 0,
        "capture_overlay_hidden": False,
        "capture_marks_hidden": False,
        "connected": False,
        "typed": False,
        "response_active": False,
        "recap_pending": False,
        "pending_audio": [],
        "realtime_turn_started": False,
    }
    audio_buffer_lock = threading.Lock()

    def show_runtime_error(message: str) -> None:
        if app_state["connected"]:
            _show_runtime_error(
                overlay,
                message,
                app_state,
                set_capture_overlay_visibility,
            )
        else:
            _restore_capture_visual_state(
                app_state,
                overlay,
                set_capture_overlay_visibility,
            )
            _show_offline_status(overlay)

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
    partial_capture: dict[str, object] = {"capture": None, "elements": [], "board_mode": False}

    def collect_capture(started_at: float | None, board_snapshot=None):
        if board_snapshot is None:
            capture = capture_screen(settings.max_image_width)
            board_rects = []
        else:
            capture, board_rects = board_snapshot
        with partial_capture_lock:
            partial_capture.update(capture=capture, elements=[], board_mode=board_snapshot is not None)

        def publish_elements(elements) -> None:
            with partial_capture_lock:
                partial_capture["elements"] = _include_board_ink(elements, capture, board_rects)

        collection = collect_elements_detailed(
            capture,
            budget=settings.ocr_budget,
            started_at=started_at,
            on_update=publish_elements,
        )
        with partial_capture_lock:
            elements = _finalize_board_collection(
                collection.elements,
                capture,
                board_rects,
                partial_capture,
            )
        if not collection.complete:
            logger.warning(
                "OCR collection incomplete; using %d collected screen elements",
                len(elements),
            )
        context = serialize_context(
            elements,
            capture.image_width,
            capture.image_height,
        )
        if board_snapshot is not None:
            context = f"BOARD MODE\n{context}"
        return capture, elements, context

    def on_microphone_audio(audio: bytes, level: float) -> None:
        bridge.mic_level.emit(level)
        with audio_buffer_lock:
            if (
                not app_state["active"]
                or not app_state["connected"]
                or app_state["typed"]
            ):
                return
            if not app_state["realtime_turn_started"]:
                app_state["pending_audio"].append(audio)
                return
            schedule(client.send_audio(audio))
            app_state["audio_sent_bytes"] += len(audio)

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
        board_snapshot = board.capture() if board.isVisible() else None
        hide_overlay = _should_hide_overlay_for_capture(overlay.capture_excluded)
        app_state["capture_overlay_hidden"] = hide_overlay
        if hide_overlay:
            set_capture_overlay_visibility(False, clear=True)
        else:
            overlay.clear()
            app.processEvents()
        request = CaptureRequest(
            capture_executor,
            lambda: collect_capture(request.started_at, board_snapshot),
        )
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
                    board_mode = bool(partial_capture["board_mode"])
                if capture is None:
                    bridge.capture_terminal_failed.emit(
                        (generation, "Capture d'écran indisponible après expiration du budget OCR.")
                    )
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
                if board_mode:
                    context = f"BOARD MODE\n{context}"
                captured = capture, elements, context
            except Exception as error:
                bridge.capture_terminal_failed.emit((generation, str(error)))
                return
            bridge.capture_ready.emit((generation, captured))

        asyncio.run_coroutine_threadsafe(wait_for_capture(), loop)

    def start_hold(pressed_at: float) -> None:
        if app_state["active"]:
            return
        if not app_state["connected"]:
            bridge.capture_failed.emit("Gerald attend la connexion Realtime. Réessayez dans un instant.")
            return
        with audio_buffer_lock:
            app_state.update(
                active=True,
                started=pressed_at,
                audio_sent_bytes=0,
                released=False,
                typed=False,
                recap_pending=False,
                pending_audio=[],
                realtime_turn_started=False,
            )
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
        generation = app_state["capture_generation"]
        QTimer.singleShot(
            PTT_REALTIME_START_DELAY_MS,
            lambda: _activate_hold_turn(
                app_state,
                generation,
                audio_buffer_lock,
                lambda: schedule(client.start_turn()),
                lambda audio: schedule(client.send_audio(audio)),
            ),
        )

    def send_captured_if_ready() -> None:
        captured = app_state["capture"]
        if captured is None or not app_state["released"]:
            return
        capture, elements, context = captured
        app_state["capture"] = None
        has_audio = _has_audio_to_commit(app_state["audio_sent_bytes"])
        duration = time.monotonic() - app_state["started"]
        question = app_state.pop("question", "")
        if not has_audio and not question and duration < 0.3:
            question = "explique ce que je regarde"
        with audio_buffer_lock:
            app_state.update(active=False, realtime_turn_started=False)
            app_state["pending_audio"].clear()
        overlay.set_status("thinking" if audio_capability["available"] else "error")
        schedule(client.finish_turn(capture, elements, context, question, has_audio))

    def release_hold() -> None:
        if not app_state["active"] or app_state["typed"]:
            return
        mic.stop()
        _activate_hold_turn(
            app_state,
            app_state["capture_generation"],
            audio_buffer_lock,
            lambda: schedule(client.start_turn()),
            lambda audio: schedule(client.send_audio(audio)),
        )
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
            with audio_buffer_lock:
                app_state["pending_audio"].clear()
                if not app_state["realtime_turn_started"]:
                    schedule(client.start_turn())
                    app_state["realtime_turn_started"] = True
                app_state.update(started=time.monotonic(), audio_sent_bytes=0, released=False, typed=True)
        else:
            with audio_buffer_lock:
                app_state.update(
                    active=True,
                    started=time.monotonic(),
                    audio_sent_bytes=0,
                    released=False,
                    typed=True,
                    pending_audio=[],
                    realtime_turn_started=True,
                )
            schedule(client.start_turn())
        overlay.set_status("thinking" if audio_capability["available"] else "error")
        if not already_active:
            begin_capture(True)
        overlay.open_text_input(submit_typed_question, cancel_typed_question)

    def open_grounder_settings() -> None:
        current = load_moondream_cloud_settings()
        dialog = QDialog()
        dialog.setWindowTitle("Grounder")
        dialog.setMinimumWidth(420)
        dialog.setStyleSheet(
            "QDialog { background: #F5F5F7; color: #1D1D1F; }"
            "QLineEdit { background: white; border: 1px solid #D2D2D7; "
            "border-radius: 8px; padding: 8px; }"
            "QPushButton { background: #FF9F0A; color: #1D1D1F; border: none; "
            "border-radius: 8px; padding: 8px 16px; }"
        )
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        endpoint = QLineEdit(current["endpoint"])
        api_key = QLineEdit(current["api_key"])
        api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Endpoint", endpoint)
        form.addRow("API key", api_key)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            save_moondream_cloud_settings(endpoint.text(), api_key.text())
            set_runtime_grounder_backend("moondream-cloud")

    def submit_typed_question(question: str) -> None:
        if not question.strip() or not app_state["active"] or not app_state["typed"]:
            return
        app_state["question"] = question.strip()
        client.record_user_message(question.strip())
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

    def toggle_board() -> None:
        if app_state["active"]:
            mic.stop()
            request = app_state.get("capture_request")
            if request is not None:
                request.cancel()
            app_state["capture_generation"] += 1
            app_state.update(active=False, released=False, capture=None, capture_request=None)
            schedule(client.cancel())
        if board.isVisible():
            board.close()
            return
        from PyQt6.QtGui import QCursor

        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is not None:
            board.open_on_screen(screen)

    def cancel_short_hold() -> None:
        capture_overlay_hidden = app_state["capture_overlay_hidden"]
        _discard_early_hold(app_state, mic, overlay, audio_buffer_lock)
        if capture_overlay_hidden:
            set_capture_overlay_visibility(True)
            app_state["capture_overlay_hidden"] = False

    def dispatch_key(name: str, pressed_at: float) -> None:
        if name == "esc":
            if overlay.dismiss_confirmation():
                client.abort_actions()
                overlay.clear()
                return
            if app_state["active"] and app_state["typed"]:
                cancel_typed_question()
                overlay.clear()
                return
            if not (app_state["active"] or app_state["response_active"] or app_state["recap_pending"]):
                if board.isVisible():
                    board.close()
                    return
                overlay.clear()
                return
            capture_overlay_hidden = app_state["capture_overlay_hidden"]
            _cancel_turn_for_escape(
                app_state,
                mic,
                audio_buffer_lock,
                lambda: schedule(client.cancel()),
            )
            if capture_overlay_hidden:
                set_capture_overlay_visibility(True)
                app_state["capture_overlay_hidden"] = False
            overlay.clear()
            if not audio_capability["available"]:
                overlay.set_status("error")
            return
        if {"ctrl", "shift", "b"} <= app_state["pressed"]:
            toggle_board()
            return
        if (required | {"r"}) <= app_state["pressed"]:
            open_lesson_recap()
            return
        if typed_hotkey <= app_state["pressed"]:
            open_typed_question()
        elif (
            name in required
            and required <= app_state["pressed"]
            and "enter" not in app_state["pressed"]
        ):
            start_hold(pressed_at)

    def key_press(name: str, pressed_at: float) -> None:
        app_state["pressed"].add(name)
        _dispatch_key_after_hold_conflict(
            app_state,
            name,
            pressed_at,
            cancel_short_hold,
            lambda: dispatch_key(name, pressed_at),
        )

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

    def handle_terminal_capture_failure(generation: int, message: str) -> None:
        if not _reset_failed_capture(app_state, generation):
            return
        schedule(client.cancel())
        show_runtime_error(message)

    class UiRequestSlots(QObject):
        @pyqtSlot(object)
        def capture_overlay(self, request) -> None:
            set_capture_overlay_visibility(request[0], clear=request[1])
            request[2].set()

        @pyqtSlot(object)
        def action_confirmation(self, request) -> None:
            overlay.show_confirmation(*request)

        @pyqtSlot(str)
        def confirmation_expired(self, token) -> None:
            overlay.expire_confirmation(token)

        @pyqtSlot(object)
        def board_tool(self, request) -> None:
            name, args, completed, result = request
            result["output"] = (
                board.execute_tool(name, args)
                if board.isVisible()
                else '{"ok":false,"error":"Board mode is not active"}'
            )
            completed.set()

        @pyqtSlot(object)
        def board_snapshot(self, request) -> None:
            completed, result = request
            result["snapshot"] = board.capture() if board.isVisible() else None
            completed.set()

        @pyqtSlot(list)
        def commands(self, commands) -> None:
            if board.isVisible():
                board.add_commands(commands)
            else:
                overlay.add_commands(commands)

        @pyqtSlot(object)
        def action_marks_visible(self, request) -> None:
            overlay.set_marks_visible(request[0])
            request[1].set()

        @pyqtSlot(object)
        def terminal_capture_failed(self, failure) -> None:
            handle_terminal_capture_failure(*failure)

    ui_request_slots = UiRequestSlots()
    bridge.capture_ready.connect(capture_ready)
    bridge.capture_overlay.connect(ui_request_slots.capture_overlay)
    bridge.action_confirmation.connect(ui_request_slots.action_confirmation)
    bridge.confirmation_expired.connect(ui_request_slots.confirmation_expired)
    bridge.board_tool.connect(ui_request_slots.board_tool)
    bridge.board_snapshot.connect(ui_request_slots.board_snapshot)
    bridge.commands.connect(ui_request_slots.commands)
    bridge.action_marks_visible.connect(ui_request_slots.action_marks_visible)
    bridge.capture_terminal_failed.connect(ui_request_slots.terminal_capture_failed)
    bridge.capture_failed.connect(show_runtime_error)
    bridge.mic_level.connect(
        lambda level: overlay.set_status(
            "listening" if audio_capability["available"] else "error",
            mic_level=level,
            level_only=True,
        )
    )
    bridge.output_level.connect(
        lambda level: overlay.set_status(
            "speaking" if audio_capability["available"] else "error",
            output_level=level,
            level_only=True,
        )
    )

    caption = {"text": ""}

    def on_realtime_event(event: dict) -> None:
        event_type = event.get("type")
        if event_type == "session.updated":
            was_connected = app_state["connected"]
            app_state["connected"] = True
            if not was_connected:
                overlay.show()
                overlay.set_status("idle" if audio_capability["available"] else "error")
            return
        if not app_state["connected"]:
            if event_type == "connection.lost":
                if overlay._status != "offline":
                    overlay.show()
                    overlay.set_status("offline")
            return
        if event_type == "response.created":
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
            if overlay._status != "offline":
                overlay.show()
                overlay.set_status("offline")
        elif event_type in {"response.output_audio_transcript.delta", "response.audio_transcript.delta"}:
            caption["text"] += event.get("delta", "")
            overlay.set_caption(caption["text"])
        elif event_type == "conversation.item.input_audio_transcription.completed":
            caption["text"] = event.get("transcript", "")
            overlay.set_caption(caption["text"])

    bridge.realtime_event.connect(on_realtime_event)
    tray = QSystemTrayIcon(QIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)), app)
    menu = QMenu()
    if open_home is not None:
        home_action = menu.addAction("Ouvrir Gerald")
        home_action.triggered.connect(open_home_window)
    text_action = menu.addAction("Poser une question…")
    text_action.triggered.connect(open_typed_question)
    recap_action = menu.addAction("Récap de la leçon")
    recap_action.triggered.connect(open_lesson_recap)
    board_action = menu.addAction("Tableau")
    board_action.triggered.connect(toggle_board)
    grounder_action = menu.addAction("Grounder…")
    grounder_action.triggered.connect(open_grounder_settings)
    menu.addSeparator()
    quit_action = menu.addAction("Quitter Gerald")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.setToolTip("Gerald — maintenez Ctrl+Maj pour parler")
    if open_home is not None:
        tray.activated.connect(
            lambda reason: open_home_window()
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick
            else None
        )
    tray.show()
    if open_home is not None and os.getenv("GERALD_START_HIDDEN") != "1":
        open_home_window()

    def on_press(key) -> None:
        bridge.key_down.emit(_key_name(key), time.monotonic())

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
        indexer.close()
        board.close()
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
