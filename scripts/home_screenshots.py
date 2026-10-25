from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

from PyQt6.QtCore import QCoreApplication, QEvent

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "2"
os.environ["GERALD_REDUCE_MOTION"] = "1"

from PyQt6.QtWidgets import QApplication  # noqa: E402

from fakes_library import FakeIndexer, FakeStore, fake_ask, seed  # noqa: E402
from gerald.home.agents import save_mascot  # noqa: E402
from gerald.home.onboarding import OnboardingWindow  # noqa: E402
from gerald.home.window import HomeWindow  # noqa: E402


def capture(application, widget, name: str) -> None:
    widget.resize(1100, 720)
    widget.show()
    widget.ensurePolished()
    application.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    pixmap = widget.grab()
    if (pixmap.width(), pixmap.height()) != (2200, 1440):
        raise RuntimeError(
            f"{name} rendered at {pixmap.width()}×{pixmap.height()}, expected 2200×1440"
        )
    destination = ROOT / "docs" / name
    if not pixmap.save(str(destination)):
        raise RuntimeError(f"Could not save {destination}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="gerald-app-screenshots-") as home_dir:
        os.environ["GERALD_HOME"] = home_dir
        application = QApplication.instance() or QApplication([])
        settings = SimpleNamespace(
            api_key="screenshot-placeholder",
            hotkey="ctrl+shift",
            model="gpt-test",
        )
        onboarding_store = FakeStore()
        onboarding = OnboardingWindow(
            onboarding_store,
            FakeIndexer(onboarding_store),
            settings,
            lambda: None,
        )
        capture(application, onboarding, "app-onboarding-1-name.png")

        onboarding._select_mascot("zoe")
        onboarding._set_step(1)
        capture(application, onboarding, "app-onboarding-2-prof.png")

        onboarding._set_step(2)
        onboarding._select_level("Licence")
        capture(application, onboarding, "app-onboarding-3-level.png")

        onboarding.add_subject("Maths")
        onboarding.add_subject("Physique-Chimie")
        onboarding.add_subject("Informatique")
        onboarding._set_step(3)
        capture(application, onboarding, "app-onboarding-4-subjects.png")

        onboarding._set_step(4)
        onboarding.subject_combo.setCurrentText("Maths")
        onboarding.queue_files(["/Documents/Analyse — chapitre 3.pdf"])
        onboarding.subject_combo.setCurrentText("Physique-Chimie")
        onboarding.queue_files(["/Documents/Mécanique.docx"])
        capture(application, onboarding, "app-onboarding-5-documents.png")

        save_mascot("zoe")
        store = seed(FakeStore())
        indexer = FakeIndexer(store)
        home = HomeWindow(
            store,
            indexer,
            settings,
            lambda: None,
            ask_fn=fake_ask(store),
        )
        capture(application, home, "app-home.png")

        maths = store.list_courses()[0]
        home.open_course(maths.id)
        capture(application, home, "app-course.png")

        conversation = store.recent_conversations(source="chat")[0]
        home.open_chat(
            conversation_id=conversation.id,
            course_id=conversation.course_id,
        )
        capture(application, home, "app-chat.png")

        home.open_discussions()
        capture(application, home, "app-discussions.png")
        onboarding.close()
        home.close()
        application.processEvents()


if __name__ == "__main__":
    main()
