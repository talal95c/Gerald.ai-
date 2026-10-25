import asyncio
from concurrent.futures import Future

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
