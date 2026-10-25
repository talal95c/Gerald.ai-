from __future__ import annotations

from collections.abc import Callable


class Microphone:
    def __init__(self, on_audio: Callable[[bytes, float], None]) -> None:
        self.on_audio = on_audio
        self._stream = None

    @property
    def available(self) -> bool:
        try:
            import sounddevice as sd

            return sd.query_devices(kind="input") is not None
        except Exception:
            return False

    def start(self) -> None:
        if self._stream is not None:
            return
        try:
            import numpy as np
            import sounddevice as sd

            def callback(indata, frames, time_info, status) -> None:
                del frames, time_info, status
                audio = bytes(indata)
                samples = np.frombuffer(audio, dtype=np.int16)
                level = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) / 32768 if samples.size else 0
                self.on_audio(audio, min(1.0, level * 5))

            self._stream = sd.RawInputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
                blocksize=2400,
                callback=callback,
            )
            self._stream.start()
        except Exception as error:
            self._stream = None
            raise RuntimeError(f"Microphone unavailable: {error}") from error

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
