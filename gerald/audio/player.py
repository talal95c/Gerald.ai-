from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self, on_unavailable: Callable[[], None] | None = None) -> None:
        self._chunks: queue.Queue[bytes] = queue.Queue()
        self._stream = None
        self._pending = b""
        self._lock = threading.Lock()
        self._available: bool | None = None
        self._warned = False
        self.on_unavailable = on_unavailable
        self.on_level: Callable[[float], None] | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                import sounddevice as sd

                if sd.query_devices(kind="output") is None:
                    raise RuntimeError("no output device")
            except Exception as error:
                self._disable(error)
            else:
                self._available = True
        return self._available is True

    def _disable(self, error: Exception) -> None:
        self._available = False
        if self._warned:
            return
        self._warned = True
        logger.warning("Audio output unavailable; playback disabled: %s", error)
        if self.on_unavailable is not None:
            try:
                self.on_unavailable()
            except Exception:
                logger.debug("Audio unavailable callback failed", exc_info=True)

    def start(self) -> bool:
        if self._stream is not None:
            return True
        if self._available is False:
            return False

        stream = None
        try:
            import sounddevice as sd

            def callback(outdata, frames, time_info, status) -> None:
                del frames, time_info, status
                needed = len(outdata)
                outdata[:] = b"\0" * needed
                written = 0
                with self._lock:
                    while written < needed:
                        if not self._pending:
                            try:
                                self._pending = self._chunks.get_nowait()
                            except queue.Empty:
                                break
                        count = min(needed - written, len(self._pending))
                        outdata[written : written + count] = self._pending[:count]
                        self._pending = self._pending[count:]
                        written += count

            stream = sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                callback=callback,
            )
            stream.start()
        except Exception as error:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    logger.debug("Unable to close failed output stream", exc_info=True)
            self._stream = None
            self._disable(error)
            return False
        self._stream = stream
        self._available = True
        return True

    def enqueue(self, audio: bytes) -> None:
        if audio:
            if self.start():
                self._chunks.put(audio)
                if self.on_level is not None and len(audio) >= 2:
                    peak = max(
                        (
                            abs(int.from_bytes(audio[index : index + 2], "little", signed=True))
                            for index in range(0, len(audio) - 1, 2)
                        ),
                        default=0,
                    )
                    self.on_level(peak / 32768)

    def stop(self) -> None:
        with self._lock:
            self._pending = b""
            while True:
                try:
                    self._chunks.get_nowait()
                except queue.Empty:
                    break

    def close(self) -> None:
        self.stop()
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
