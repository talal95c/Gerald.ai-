# Architecture

Gerald keeps device- and Qt-specific choices inside adapters, so that the reasoning about
coordinates and tools stays testable without a native UI. The same brain and tool semantics run
in two shells: the **desktop app** (Python / PyQt6, overlay over any application) and the
**web demo** (browser, WebRTC, served by `scripts/web_voice_board.py`).

## Desktop app (`gerald/`)

| Module | Responsibility |
| --- | --- |
| `config.py` | Loads `.env`, settings and the Windows DPI scale before Qt starts. |
| `capture/screen.py` | Picks the monitor under the cursor, keeps its physical origin, resizes and JPEG-encodes one capture. |
| `perception/elements.py` | Queries UI Automation and OCR when available, filters and serialises the on-screen context. |
| `perception/grounding.py` | Resolves an element id or a point to a physical rectangle, Qt-free. |
| `perception/grounder.py` | Optional visual point models (Moondream Cloud / local, OpenRouter), called with a time budget. |
| `board.py` | Whiteboard; keeps the user's ink and Gerald's ink in separate layers and captures the widget on demand. |
| `tools/registry.py` | Declares the Realtime tool schemas and turns calls into plain drawing commands. |
| `tools/plot.py`, `tools/diagram.py` | Exact function plots (safe AST parser) and schema diagrams. |
| `actions/input.py` | Runs confirmed desktop actions with a per-turn limit, Esc abort and takeover detection. |
| `tools/recap.py` | Writes the Markdown revision sheet to `~/Gerald/lessons` and opens it. |
| `brain/realtime.py` | Realtime WebSocket session, push-to-talk turns, tool loop, transcripts and usage. |
| `audio/` | Mono 24 kHz PCM capture and playback. |
| `overlay/window.py` | Draws annotations, Gerald's cursor and bubbles in a transparent window above the desktop. |
| `library/` | Course library: ingest PDF / DOCX / Markdown, embeddings, search and Q&A (see [LIBRARY_API.md](LIBRARY_API.md)). |
| `home/` | Companion notch (React build shown in QWebEngine) and demo documents. |
| `proactive.py` | Opt-in suggestions based only on the foreground app and window title. |
| `app.py` | Wires Qt, global hotkeys, the tray icon and the asyncio loop. |
| `scripts/live_check.py` | Runs one real question against an image, without a microphone. |

## Web demo (`web/` + `scripts/web_voice_board.py`)

- `web/` is a React + Vite multi-page app: `landing`, `desktop` (fake OS with Notes and a
  Photoshop-like editor), `td` (worksheet), `board`, `fiche`, `app` (notch). `npm run build`
  writes to `gerald/home/webui/`, which is committed so neither Render nor the desktop app needs Node.
- The browser opens one `RTCPeerConnection`; the Python server only swaps the SDP with OpenAI
  `/v1/realtime/calls`, so the API key stays server-side. `/api/session` is rate-limited
  (`GERALD_MAX_SESSIONS_*`), `/healthz` serves Render's probe.
- Tools (`underline`, `circle`, `arrow`, `point`, `write`, `write_math`, `plot`, `open_board`, …)
  execute in the page against DOM elements exposed with id + text + rect; handwriting is exposed as
  geometric ink clusters (ids ≥ 10000), so `target_text` such as « + 24 » is matched by span geometry.
- In the editor (vendored miniPaint), Gerald points at one control per turn and the user clicks;
  tool results return `{shown, say}` so the spoken caption always names the marked control.

## Key decisions

- **One-shot vision, not continuous.** A capture is taken when the hotkey is pressed or a typed
  question explicitly asks for it, resized and sent with the elements visible at that moment.
  No capture loop runs at rest. *Why*: privacy and cost; the student decides when Gerald looks.
- **Reusable UI anchors.** Element providers (UIA, OCR, DOM, ink) report observations with their
  provenance; tool calls prefer `element_id` / `target_text` over estimated coordinates. Points are
  expressed in image pixels, then converted to the monitor's physical coordinates. *Why*: raw model
  pointing was ~90 px off; grounded targets reach a 2.4 px median error.
- **Non-interactive overlay excluded from capture.** Drawing commands never drive the target app.
  On Windows the overlay is click-through / no-activate with `WDA_EXCLUDEFROMCAPTURE`; other systems
  hide it during a capture. *Why*: Gerald must not see or block its own marks.
- **I/O separation.** The Qt thread keeps the UI responsive; asyncio owns the WebSocket and audio
  events. Overlay commands are Qt-free dataclasses (testable offscreen).
- **Graceful degradation.** UIA, OCR, the active window and audio devices may be missing; adapters
  log the failure instead of failing the whole question.

## Realtime loop and actions

The client uses the GA Realtime interface documented by OpenAI
([Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)).
The session keeps the history; tools are returned as `function_call_output` before a single
continuation per completed response.

Mouse and keyboard actions ask for permission in a Qt « Allow / Cancel » capsule on the first
gesture of each turn (`GERALD_REQUIRE_CONFIRMATION=1`). The model's `confirmed` field never
authorises an action on its own. The request expires after 15 s. Handlers run outside the asyncio
loop; a click first shows a marker, then hides the marks during input. Esc cancels the request or
clears the marks. At most eight actions are allowed per turn, and a manual mouse move above 40 px
interrupts the sequence. After an action the overlay is hidden for the new capture, and the element
context precedes the continuation so the model can check the result.

`Ctrl+Shift+R` and the tray action send a text-only recap request (no capture). The `save_recap`
tool writes Markdown to `~/Gerald/lessons/` and opens it with the associated application
(Notepad on Windows when `.md` has no association).

`Ctrl+Shift+B` opens the board on the monitor under the cursor. The board accepts pen and mouse;
it is rendered to an image only when a Gerald turn starts. User strokes are grouped as `ink`
elements; Gerald's ink stays in a separate layer and board tools cannot erase the user's ink. If the
board was used, the recap can include a PNG of it.

The visual point model is off by default (`GERALD_GROUNDER=none`). OpenRouter uses
`OPENROUTER_API_KEY`; local Moondream is installed with the `grounder-local` extra and runs on CPU;
Moondream Cloud uses `MOONDREAM_API_KEY` (or the Colab notebook endpoint).
