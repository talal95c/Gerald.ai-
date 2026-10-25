from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

from playwright.sync_api import sync_playwright
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

from gerald.board import BoardWindow


ROOT = Path(__file__).resolve().parents[1]
WEBUI = ROOT / "gerald" / "home" / "webui"
DOCS = ROOT / "docs"

MOCK_BRIDGE = """
(() => {
  const signal = () => {
    const listeners = [];
    return { connect: fn => listeners.push(fn), emit: value => listeners.forEach(fn => fn(value)) };
  };
  const state = {
    greeting: "Bonjour.", hotkey_label: "CTRL + SHIFT",
    documents: [
      {id: 1, filename: "Polynômes du second degré.md", status: "ready", error: ""},
      {id: 2, filename: "Fonctions affines.md", status: "indexing", error: ""}
    ],
    conversations: [
      {id: 1, title: "Résoudre une équation du second degré", source: "chat", updated_at: "2025-02-15T12:00:00+00:00"},
      {id: 2, title: "Méthode du discriminant", source: "agent", updated_at: "2025-02-14T12:00:00+00:00"}
    ],
    session_open: false, recap_pending: false
  };
  const signals = {
    stateChanged: signal(), modeChanged: signal(), answer: signal(),
    answerError: signal(), recapReady: signal()
  };
  window.__mockSignals = signals;
  window.bridge = {
    ...signals,
    state: callback => {
      const json = JSON.stringify(state);
      if (callback) callback(json);
      return json;
    },
    setMode: mode => signals.modeChanged.emit(mode),
    ask: question => signals.answer.emit(JSON.stringify({
      text: "Le discriminant vaut Δ = b² − 4ac. Ici, Δ = 1, donc l’équation possède deux racines réelles.",
      sources: [{document: "Polynômes du second degré.md", page: 2}]
    })),
    messages: (_id, callback) => callback(JSON.stringify([
      {role: "assistant", text: "On commence par calculer le discriminant."},
      {role: "user", text: "Je ne comprends pas cette étape."}
    ])),
    addDocuments: () => {},
    deleteDocument: () => {},
    openBoard: () => {},
    requestFocus: () => {},
    endSession: () => {},
    openRecap: () => {},
    quit: () => {}
  };
})();
"""


def capture_web_screenshots() -> None:
    url = (WEBUI / "index.html").as_uri()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--allow-file-access-from-files"],
        )
        page = browser.new_page(
            viewport={"width": 1280, "height": 900},
            device_scale_factor=2,
            color_scheme="light",
        )
        page.add_init_script(MOCK_BRIDGE)
        page.goto(url, wait_until="networkidle")
        greeting = page.locator(".greeting")
        greeting.wait_for()
        page.wait_for_timeout(600)
        greeting.screenshot(path=str(DOCS / "notch-greeting.png"))

        page.mouse.move(1200, 850)
        page.wait_for_timeout(6200)
        page.locator(".collapsed").wait_for()
        collapsed = page.locator(".collapsed").bounding_box()
        page.screenshot(path=str(DOCS / "notch-collapsed.png"), clip=collapsed)
        page.evaluate("document.querySelector('.collapsed').click()")
        page.locator(".panel").wait_for()
        page.evaluate(
            """() => window.__mockSignals.answer.emit(JSON.stringify({
              text: "Le discriminant vaut Δ = b² − 4ac. Ici, Δ = 1, donc l’équation possède deux racines réelles.",
              sources: [{document: "Polynômes du second degré.md", page: 2}]
            }))"""
        )
        page.wait_for_timeout(2000)
        page.locator(".panel").screenshot(path=str(DOCS / "notch-panel.png"))
        page.evaluate(
            """() => window.__mockSignals.answer.emit(JSON.stringify({
              text: "La réponse est 42.",
              sources: []
            }))"""
        )
        page.wait_for_function("document.querySelector('.answer')?.textContent.includes('42')")
        if page.locator(".sources").count():
            raise AssertionError("An empty source list must not render a source-chip row")

        page.locator(".panel .gear").click()
        page.locator(".settings").wait_for()
        page.get_by_role("button", name="Documents").click()
        page.wait_for_timeout(200)
        page.locator(".settings").screenshot(path=str(DOCS / "notch-settings-documents.png"))

        page.get_by_role("button", name="Historique").click()
        page.wait_for_timeout(200)
        page.locator(".settings").screenshot(path=str(DOCS / "notch-settings-historique.png"))

        page.goto((WEBUI / "td.html").as_uri(), wait_until="networkidle")
        page.locator(".paper").wait_for()
        page.screenshot(path=str(DOCS / "td-exercises.png"), full_page=True)
        browser.close()


def capture_board_screenshot() -> None:
    app = QApplication.instance() or QApplication(["gerald-screenshot"])
    board = BoardWindow()
    board.setGeometry(0, 0, 1100, 720)
    board.set_exercise(
        "Exercice 1",
        ["Résous dans ℝ : x² − 5x + 6 = 0", "Puis trace la parabole et place ses racines."],
    )
    board.user_strokes = [[(150, 500, 1.0), (250, 470, 1.0), (360, 500, 1.0)]]
    board.add_path([(145, 420), (335, 420), (370, 455)])
    board.show()
    QTest.qWait(500)
    output = DOCS / "board-exercise.png"
    if not board.grab().save(str(output)):
        raise RuntimeError(f"Could not save {output}")
    board.close()
    app.processEvents()


def main() -> None:
    capture_web_screenshots()
    capture_board_screenshot()
    for path in (
        "notch-greeting.png",
        "notch-collapsed.png",
        "notch-panel.png",
        "notch-settings-documents.png",
        "notch-settings-historique.png",
        "td-exercises.png",
        "board-exercise.png",
    ):
        print(DOCS / path)


if __name__ == "__main__":
    main()
