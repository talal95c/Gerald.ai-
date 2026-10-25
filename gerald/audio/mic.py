from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class Microphone:
    def __init__(
        self,
        on_audio: Callable[[bytes, float], None],
        on_unavailable: Callable[[], None] | None = None,
    ) -> None:
        self.on_audio = on_audio
        self.on_unavailable = on_unavailable
        self._stream = None
        self._available: bool | None = None
        self._warned = False

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                import sounddevice as sd

                if sd.query_devices(kind="input") is None:
                    raise RuntimeError("no input device")
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
        logger.warning("Microphone unavailable; capture disabled: %s", error)
        if self.on_unavailable is not None:
            try:
                self.on_unavailable()
            except Exception:
                logger.debug("Microphone unavailable callback failed", exc_info=True)

    def start(self) -> None:
        if self._stream is not None:
            return
        if not self.available:
            return
        stream = None
        try:
            import numpy as np
            import sounddevice as sd

            def callback(indata, frames, time_info, status) -> None:
                del frames, time_info, status
                audio = bytes(indata)
                samples = np.frombuffer(audio, dtype=np.int16)
                level = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) / 32768 if samples.size else 0
                self.on_audio(audio, min(1.0, level * 5))

            stream = sd.RawInputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                blocksize=2400,
                callback=callback,
            )
            stream.start()
        except Exception as error:
            self._stream = None
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    logger.debug("Unable to close failed input stream", exc_info=True)
            self._disable(error)
            return
        self._stream = stream
        self._available = True

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
