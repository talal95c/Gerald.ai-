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
      {id: 1, filename: "Cours — Second degré.pdf", status: "ready", error: "", folder: "Polynômes du second degré"},
      {id: 2, filename: "TD 4 — Polynômes du second degré.pdf", status: "ready", error: "", folder: "Polynômes du second degré"},
      {id: 3, filename: "Fiche discriminant.md", status: "indexing", error: "", folder: "Polynômes du second degré"},
      {id: 4, filename: "Cours — Fonctions affines.pdf", status: "ready", error: "", folder: "Fonctions affines"},
      {id: 5, filename: "Exercices corrigés.pdf", status: "ready", error: "", folder: "Fonctions affines"},
      {id: 6, filename: "Cours — Suites.pdf", status: "ready", error: "", folder: "Suites numériques"}
    ],
    conversations: [
      {id: 1, title: "Résoudre une équation du second degré", source: "chat", updated_at: "2025-02-15T12:00:00+00:00"},
      {id: 2, title: "Méthode du discriminant", source: "agent", updated_at: "2025-02-14T12:00:00+00:00"}
    ],
    session_open: false, recap_pending: false
  };
  const signals = {
    stateChanged: signal(), modeChanged: signal(), answer: signal(),
    answerError: signal(), recapReady: signal(), agentStatus: signal()
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
    ask: question => {
      signals.agentStatus.emit("thinking");
      const td = /TD|exercice|exo/i.test(question);
      setTimeout(() => {
        signals.agentStatus.emit("speaking");
        signals.answer.emit(JSON.stringify({
          text: td
            ? "Ici, x² − 5x + 6 = 0 est un polynôme du second degré : on ne peut pas l’isoler comme une fonction affine. Repère a = 1, b = −5 et c = 6, puis calcule Δ = b² − 4ac. Viens, on va au tableau, je t’explique pas à pas."
            : "Le discriminant vaut Δ = b² − 4ac. Ici, Δ = 1, donc l’équation possède deux racines réelles.",
          sources: [{document: td ? "TD 4 — Polynômes du second degré.pdf" : "Polynômes du second degré.md", page: 1}]
        }));
        setTimeout(() => signals.agentStatus.emit("idle"), 2600);
      }, 900);
    },
    documentText: (id, callback) => callback(id === 1
      ? "Polynômes du second degré\n\nUn polynôme du second degré s’écrit f(x) = ax² + bx + c avec a ≠ 0.\n\nDiscriminant\nOn pose Δ = b² − 4ac.\n• Si Δ > 0 : deux racines x₁ = (−b − √Δ) / 2a et x₂ = (−b + √Δ) / 2a.\n• Si Δ = 0 : une racine double x₀ = −b / 2a.\n• Si Δ < 0 : pas de racine réelle.\n\nExemple\nx² − 5x + 6 = 0 : a = 1, b = −5, c = 6, Δ = 25 − 24 = 1, donc x₁ = 2 et x₂ = 3."
      : "Aperçu de démonstration de ce document."),
    messages: (_id, callback) => callback(JSON.stringify([
      {role: "assistant", text: "On commence par calculer le discriminant."},
      {role: "user", text: "Je ne comprends pas cette étape."}
    ])),
    addDocuments: () => {},
    deleteDocument: () => {},
    openBoard: (title, lines) => { if (location.protocol !== "file:") location.href = "board.html?title=" + encodeURIComponent(title) + "&lines=" + encodeURIComponent(lines); },
    openTd: () => { if (location.protocol !== "file:") location.href = "td.html"; },
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
        def notch(name: str, size: tuple[int, int], *scripts: str) -> None:
            shot = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=2)
            shot.add_init_script(MOCK_BRIDGE)
            shot.goto(url, wait_until="networkidle")
            for script in scripts:
                shot.evaluate(script)
                shot.wait_for_timeout(350)
            shot.screenshot(path=str(DOCS / f"{name}.png"), omit_background=True)
            shot.close()

        emit = "window.__mockSignals.{}.emit('{}')".format
        notch("notch-greeting", (240, 36))
        notch("notch-listening", (240, 36), emit("modeChanged", "collapsed"), emit("agentStatus", "listening"))
        notch("notch-panel", (760, 72), emit("modeChanged", "panel"))
        notch("notch-settings-documents", (760, 440), emit("modeChanged", "settings"))
        page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2, color_scheme="light")
        page.add_init_script(MOCK_BRIDGE)
        page.goto((WEBUI / "td.html").as_uri(), wait_until="networkidle")
        page.locator(".paper").wait_for()
        page.screenshot(path=str(DOCS / "td-exercises.png"), full_page=True)
        page.locator(".exercise").first.hover()
        page.wait_for_timeout(200)
        page.screenshot(path=str(DOCS / "td-hover.png"), full_page=True)
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
        "td-hover.png",
        "board-exercise.png",
    ):
        print(DOCS / path)


if __name__ == "__main__":
    main()
