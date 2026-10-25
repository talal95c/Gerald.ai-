from types import SimpleNamespace

from gerald.proactive import ProactiveWatcher, Suggestion


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeStore:
    def list_courses(self):
        return [SimpleNamespace(title="La photosynthèse", subject="SVT")]

    def get_profile(self):
        return SimpleNamespace(subjects=["Biologie"])


def _watcher(clock, probe, suggestions, **kwargs):
    return ProactiveWatcher(probe, clock, kwargs.pop("is_busy", lambda: False), suggestions.append, **kwargs)


def test_four_second_dwell_and_global_cooldown():
    clock, suggestions = FakeClock(), []
    current = ["chrome.exe", "Hacker News — Google Chrome"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)

    watcher.poll()
    clock.advance(3.9)
    watcher.poll()
    assert suggestions == []
    clock.advance(0.2)
    watcher.poll()
    assert len(suggestions) == 1

    current[1] = "Another page"
    clock.advance(4)
    watcher.poll()
    assert len(suggestions) == 1
    clock.advance(116)
    watcher.poll()
    assert len(suggestions) == 2


def test_normalized_title_is_suggested_once():
    clock, suggestions = FakeClock(), []
    current = ["browser", "Électricité"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    current[1] = "electricite"
    clock.advance(5)
    watcher.poll()
    assert len(suggestions) == 1


def test_two_non_choices_mute_the_app_for_the_run():
    clock, suggestions = FakeClock(), []
    current = ["chrome.exe", "First page"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    watcher.resolve(suggestions[-1], "Non")

    clock.advance(120)
    current[1] = "Second page"
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    watcher.resolve(suggestions[-1], "Non")

    current[1] = "Third page"
    clock.advance(4)
    watcher.poll()
    assert len(suggestions) == 2


def test_busy_windows_do_not_trigger_until_idle():
    clock, suggestions = FakeClock(), []
    busy = [True]
    watcher = _watcher(clock, lambda: ("browser", "A lesson"), suggestions, is_busy=lambda: busy[0])
    watcher.poll()
    clock.advance(5)
    watcher.poll()
    assert suggestions == []
    busy[0] = False
    watcher.poll()
    assert len(suggestions) == 1


def test_own_and_ignored_windows_and_empty_titles_are_skipped():
    clock, suggestions = FakeClock(), []
    current = ["Gerald.exe", "Gerald"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)
    for app, title in [
        ("Gerald.exe", "Gerald"),
        ("explorer.exe", "Downloads"),
        ("taskmgr.exe", "Task Manager"),
        ("LockApp.exe", "Windows lock screen"),
        ("browser", ""),
    ]:
        current[:] = [app, title]
        watcher.poll()
        clock.advance(5)
        watcher.poll()
    assert suggestions == []


def test_course_match_and_question_length():
    clock, suggestions = FakeClock(), []
    current = ["chrome.exe", "Photosynthèse — Google Chrome"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions, store=FakeStore())
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    suggestion = suggestions[0]
    assert suggestion.course_title == "La photosynthèse"
    assert "ton cours" in suggestion.question
    assert len(suggestion.question) <= 70


def test_generic_title_cleans_suffix_and_caps_question():
    clock, suggestions = FakeClock(), []
    current = ["chrome.exe", "A very long page title with useful content " * 3 + " - Google Chrome"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    suggestion = suggestions[0]
    assert "Google Chrome" not in suggestion.question
    assert "…" in suggestion.question
    assert len(suggestion.question) <= 70


def test_disabled_watcher_does_not_probe():
    clock = FakeClock()
    watcher = ProactiveWatcher(
        lambda: (_ for _ in ()).throw(AssertionError("probe called")),
        clock,
        lambda: False,
        lambda _suggestion: None,
        enabled=False,
    )
    watcher.poll()


def test_yes_resets_cooldown_from_choice_time():
    clock, suggestions = FakeClock(), []
    current = ["browser", "first"]
    watcher = _watcher(clock, lambda: tuple(current), suggestions)
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    watcher.resolve(suggestions[0], "Oui")
    assert isinstance(suggestions[0], Suggestion)
    current[1] = "second"
    clock.advance(4)
    watcher.poll()
    clock.advance(115)
    watcher.poll()
    assert len(suggestions) == 1
    clock.advance(1)
    watcher.poll()
    assert len(suggestions) == 2


def test_timeout_choice_is_recorded_as_none():
    clock, suggestions = FakeClock(), []
    watcher = _watcher(clock, lambda: ("browser", "A lesson"), suggestions)
    watcher.poll()
    clock.advance(4)
    watcher.poll()
    suggestion = suggestions[0]
    watcher.resolve(suggestion, None)
    assert watcher._choices[("browser", "a lesson")] is None
