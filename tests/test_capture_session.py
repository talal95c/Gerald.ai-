import asyncio
from concurrent.futures import Future

import pytest

from gerald.capture.session import CaptureRequest


def test_capture_starts_on_press_and_elements_finish_is_awaited_on_release():
    completed = Future()
    submitted = []

    class FakeExecutor:
        def submit(self, capture):
            submitted.append(capture)
            return completed

    request = CaptureRequest(FakeExecutor(), lambda: ("capture", ["elements"]))
    request.start_on_press()
    assert len(submitted) == 1

    async def await_release():
        waiting = asyncio.create_task(request.wait_on_release())
        await asyncio.sleep(0)
        assert not waiting.done()
        result = ("capture", ["elements"])
        completed.set_result(result)
        assert await waiting == result

    asyncio.run(await_release())


def test_capture_wait_respects_remaining_ocr_budget():
    completed = Future()

    class FakeExecutor:
        def submit(self, _capture):
            return completed

    request = CaptureRequest(FakeExecutor(), lambda: "capture")
    request.start_on_press()

    async def await_release():
        with pytest.raises(TimeoutError):
            await request.wait_on_release(timeout=0.001)
        completed.set_result("capture")

    asyncio.run(await_release())
