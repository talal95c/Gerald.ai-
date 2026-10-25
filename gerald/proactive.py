from __future__ import annotations

import re
import unicodedata
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable


_STOPWORDS = {
    "avec", "dans", "des", "les", "une", "pour", "sur", "the", "and", "from", "that",
    "this", "your", "have", "about", "into", "when", "what", "where", "which",
}
_SUFFIXES = (
    "Google Chrome", "Mozilla Firefox", "Microsoft Edge", "Visual Studio Code",
    "Google Docs", "Safari", "Notepad++",
)


@dataclass(frozen=True)
class Suggestion:
    app: str
    title: str
    question: str
    course_title: str | None = None


def _words(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return {word for word in re.findall(r"[a-z0-9]+", normalized) if len(word) > 3 and word not in _STOPWORDS}


def _normalize_title(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def _clean_title(title: str) -> str:
    result = title.strip()
    for suffix in _SUFFIXES:
        result = re.sub(rf"\s+[-—]\s+{re.escape(suffix)}\s*$", "", result, flags=re.IGNORECASE)
    result = " ".join(result.split())
    return result if len(result) <= 40 else result[:39].rstrip() + "…"


def _question(title: str, course_title: str | None) -> str:
    if course_title:
        prefix, suffix = "Ça ressemble à ton cours « ", " ». Je t'aide ?"
        budget = 70 - len(prefix) - len(suffix)
        course = course_title if len(course_title) <= budget else course_title[: budget - 1].rstrip() + "…"
        return f"{prefix}{course}{suffix}"
    cleaned = _clean_title(title) or "cette page"
    prefix, suffix = "Je t'explique « ", " » ?"
    budget = 70 - len(prefix) - len(suffix)
    cleaned = cleaned if len(cleaned) <= budget else cleaned[: budget - 1].rstrip() + "…"
    return f"{prefix}{cleaned}{suffix}"


class ProactiveWatcher:
    def __init__(
        self,
        probe: Callable[[], tuple[str, str]],
        clock: Callable[[], float],
        is_busy: Callable[[], bool],
        on_suggest: Callable[[Suggestion], None],
        store=None,
        enabled: bool = True,
        threaded_probe: bool = False,
    ) -> None:
        self.probe = probe
        self.clock = clock
        self.is_busy = is_busy
        self.on_suggest = on_suggest
        self.store = store
        self.enabled = enabled
        self.threaded_probe = threaded_probe
        self._executor = ThreadPoolExecutor(max_workers=1) if threaded_probe else None
        self._future: Future | None = None
        self._current: tuple[str, str] | None = None
        self._since = clock()
        self._last_suggestion = float("-inf")
        self._seen: set[tuple[str, str]] = set()
        self._declines: dict[str, int] = {}
        self._muted_apps: set[str] = set()
        self._pending: dict[tuple[str, str], Suggestion] = {}
        self._choices: dict[tuple[str, str], str | None] = {}

    def _read_probe(self) -> tuple[str, str] | None:
        if self._executor is None:
            try:
                return self.probe()
            except Exception:
                return None
        if self._future is None:
            self._future = self._executor.submit(self.probe)
            return None
        if not self._future.done():
            return None
        try:
            return self._future.result()
        except Exception:
            return None
        finally:
            self._future = None

    @staticmethod
    def _ignored(app: str, title: str) -> bool:
        a, t = app.casefold(), title.casefold()
        return (
            not title.strip()
            or "gerald" in a
            or "gerald" in t
            or a in {
                "explorer.exe", "explorer", "taskmgr.exe", "taskmgr", "task manager",
                "lockapp.exe", "logonui.exe", "shellexperiencehost.exe",
                "searchhost.exe", "startmenuexperiencehost.exe",
            }
            or "task manager" in t
            or "program manager" in t
            or "lock screen" in t
        )

    def _course_match(self, title: str) -> str | None:
        title_words = _words(title)
        if not title_words or self.store is None:
            return None
        candidates = []
        try:
            for course in self.store.list_courses():
                candidates.append((course.title, course.title))
                candidates.append((course.subject, course.subject))
            profile = self.store.get_profile()
            if profile:
                candidates.extend((subject, subject) for subject in profile.subjects)
        except Exception:
            return None
        best = None
        best_score = 0.0
        for label, subject in candidates:
            overlap = title_words & _words(label or "")
            if overlap:
                score = len(overlap) / max(len(title_words), len(_words(label or "")))
                if score > best_score:
                    best, best_score = (label or subject), score
        return best

    def poll(self) -> None:
        if not self.enabled:
            return
        value = self._read_probe()
        if value is None:
            return
        app, title = (str(value[0]).strip(), str(value[1]).strip())
        identity = (app.casefold(), _normalize_title(title))
        now = self.clock()
        if identity != self._current:
            self._current, self._since = identity, now
        if (
            self._ignored(app, title)
            or app.casefold() in self._muted_apps
            or self.is_busy()
            or now - self._since < 4
            or now - self._last_suggestion < 120
            or identity in self._seen
        ):
            return
        match = self._course_match(title)
        suggestion = Suggestion(app, title, _question(title, match), match)
        self._seen.add(identity)
        self._last_suggestion = now
        self._pending[identity] = suggestion
        self.on_suggest(suggestion)

    def resolve(self, suggestion: Suggestion, choice: str | None) -> None:
        identity = (suggestion.app.casefold(), _normalize_title(suggestion.title))
        self._pending.pop(identity, None)
        self._choices[identity] = choice
        app = suggestion.app.casefold()
        if choice == "Oui":
            self._last_suggestion = self.clock()
        elif choice == "Non":
            self._declines[app] = self._declines.get(app, 0) + 1
            if self._declines[app] >= 2:
                self._muted_apps.add(app)

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
