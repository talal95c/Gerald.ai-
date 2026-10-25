from gerald.app import (
    AUDIO_BYTES_FOR_100MS,
    _has_audio_to_commit,
    _reset_failed_capture,
    _should_hide_overlay_for_capture,
)


def test_quiet_audio_commits_after_100ms_of_pcm_was_sent():
    assert AUDIO_BYTES_FOR_100MS == 4800
    assert not _has_audio_to_commit(4798)
    assert _has_audio_to_commit(4800)


def test_terminal_capture_failure_invalidates_and_resets_the_turn():
    class Request:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    request = Request()
    state = {
        "capture_generation": 5,
        "capture_request": request,
        "capture": object(),
        "active": True,
        "released": True,
        "audio_sent_bytes": 5000,
    }

    assert _reset_failed_capture(state, 5)
    assert request.cancelled
    assert state["capture_generation"] == 6
    assert state["capture_request"] is None
    assert state["capture"] is None
    assert not state["active"]
    assert not state["released"]
    assert state["audio_sent_bytes"] == 0
    assert not _reset_failed_capture(state, 5)


def test_failed_capture_exclusion_uses_overlay_hide_fallback():
    assert _should_hide_overlay_for_capture(False, "nt")
    assert not _should_hide_overlay_for_capture(True, "nt")
    assert _should_hide_overlay_for_capture(True, "linux")
