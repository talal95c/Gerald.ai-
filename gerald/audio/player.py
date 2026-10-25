from __future__ import annotations

import queue
import threading


class AudioPlayer:
    def __init__(self) -> None:
        self._chunks: queue.Queue[bytes] = queue.Queue()
        self._stream = None
        self._pending = b""
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._stream is not None:
            return
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

        self._stream = sd.RawOutputStream(
            samplerate=24000,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def enqueue(self, audio: bytes) -> None:
        if audio:
            if self._stream is None:
                self.start()
            self._chunks.put(audio)

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
