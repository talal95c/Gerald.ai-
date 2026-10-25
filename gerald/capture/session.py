from __future__ import annotations

import asyncio
from concurrent.futures import Executor, Future
import time
from typing import Any, Callable


class CaptureRequest:
    def __init__(self, executor: Executor, capture: Callable[[], Any]) -> None:
        self.executor = executor
        self.capture = capture
        self.future: Future[Any] | None = None
        self.started_at: float | None = None

    def start_on_press(self) -> Future[Any]:
        if self.future is not None:
            raise RuntimeError("capture already started")
        self.started_at = time.monotonic()
        self.future = self.executor.submit(self.capture)
        return self.future

    async def wait_on_release(self, timeout: float | None = None) -> Any:
        if self.future is None:
            raise RuntimeError("capture was not started")
        wrapped = asyncio.wrap_future(self.future)
        if timeout is None:
            return await wrapped
        return await asyncio.wait_for(asyncio.shield(wrapped), timeout=max(0.0, timeout))

    def cancel(self) -> None:
        if self.future is not None:
            self.future.cancel()
