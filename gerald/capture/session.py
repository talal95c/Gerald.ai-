from __future__ import annotations

import asyncio
from concurrent.futures import Executor, Future
from typing import Any, Callable


class CaptureRequest:
    def __init__(self, executor: Executor, capture: Callable[[], Any]) -> None:
        self.executor = executor
        self.capture = capture
        self.future: Future[Any] | None = None

    def start_on_press(self) -> Future[Any]:
        if self.future is not None:
            raise RuntimeError("capture already started")
        self.future = self.executor.submit(self.capture)
        return self.future

    async def wait_on_release(self) -> Any:
        if self.future is None:
            raise RuntimeError("capture was not started")
        return await asyncio.wrap_future(self.future)

    def cancel(self) -> None:
        if self.future is not None:
            self.future.cancel()
