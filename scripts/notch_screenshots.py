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
  const storageKey = "gerald-preview-state";
  const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
  const persist = () => sessionStorage.setItem(storageKey, JSON.stringify({
    session_open: state.session_open, recap_pending: state.recap_pending,
    recap: state.recap, last_exercise: state.last_exercise
  }));
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
    session_open: saved.session_open ?? false, recap_pending: saved.recap_pending ?? false,
    recap: saved.recap ?? "", last_exercise: saved.last_exercise ?? null
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
      const normalized = String(question).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
      const match = normalized.match(/(?:exercice|exo)\s*(\d)/);
      const number = Math.min(4, Math.max(1, Number(match?.[1] || 1)));
      const coefficients = ["a = 1, b = −5 et c = 6", "a = 2, b = 3 et c = −2", "a = 1, b = −4 et c = 1", "a = −1, b = 1 et c = 6"];
      const equations = ["x² − 5x + 6 = 0", "2x² + 3x − 2 = 0", "x² − 4x + 1", "−x² + x + 6"];
      const broad = /exercice|exo|td|methode|comprends|bloque/.test(normalized);
      const text = /delta|discriminant/.test(normalized)
        ? "Le discriminant se calcule avec Δ = b² − 4ac. Ici, Δ = 25 − 24 = 1."
        : /racine|solution/.test(normalized)
          ? "Les solutions viennent de x = (−b ± √Δ) / 2a. Ici, x₁ = 2 et x₂ = 3."
          : /canonique/.test(normalized)
            ? "La forme canonique est a(x − α)² + β, avec α = −b/2a. Pour l’exercice 3, α = 2 et β = −3."
            : /signe/.test(normalized)
              ? "Le signe du trinôme est celui de a à l’extérieur des racines. Pour l’exercice 4, elles sont −2 et 3."
              : broad
                ? `Ici, ${equations[number - 1]} est un polynôme du second degré : on ne l’isole pas comme une fonction affine. Repère d’abord ${coefficients[number - 1]}, puis calcule Δ = b² − 4ac. Viens, on va au tableau, je t’explique pas à pas.`
                : "Je regarde ça avec toi : dis-moi sur quel exercice tu bloques, ou ouvre le TD.";
      const td = broad;
      setTimeout(() => {
        signals.agentStatus.emit("speaking");
        signals.answer.emit(JSON.stringify({
          text,
          sources: [{document: td ? "TD 4 — Polynômes du second degré.pdf" : "Polynômes du second degré.md", page: 1}]
        }));
        setTimeout(() => signals.agentStatus.emit("idle"), 2600);
      }, 900);
    },
    documentText: (id, callback) => callback(id === 1
      ? `Polynômes du second degré\n\nUn polynôme du second degré s’écrit f(x) = ax² + bx + c avec a ≠ 0.\n\nDiscriminant\nOn pose Δ = b² − 4ac.\n• Si Δ > 0 : deux racines x₁ = (−b − √Δ) / 2a et x₂ = (−b + √Δ) / 2a.\n• Si Δ = 0 : une racine double x₀ = −b / 2a.\n• Si Δ < 0 : pas de racine réelle.\n\nExemple\nx² − 5x + 6 = 0 : a = 1, b = −5, c = 6, Δ = 25 − 24 = 1, donc x₁ = 2 et x₂ = 3.`
      : "Aperçu de démonstration de ce document."),
    messages: (_id, callback) => callback(JSON.stringify([
      {role: "assistant", text: "On commence par calculer le discriminant."},
      {role: "user", text: "Je ne comprends pas cette étape."}
    ])),
    addDocuments: () => {},
    deleteDocument: () => {},
    openBoard: (title, lines) => {
      let parsed = [];
      try { parsed = JSON.parse(lines); } catch {}
      state.session_open = true;
      state.last_exercise = {title, lines: parsed};
      persist();
      if (location.protocol !== "file:") location.href = "board.html?title=" + encodeURIComponent(title) + "&lines=" + encodeURIComponent(lines);
    },
    openTd: () => { if (location.protocol !== "file:") location.href = "td.html"; },
    requestFocus: () => {},
    endSession: () => {
      state.recap_pending = true; persist(); signals.stateChanged.emit(JSON.stringify(state));
      setTimeout(() => {
        state.session_open = false; state.recap_pending = false; state.recap = "fiche.html";
        persist(); signals.recapReady.emit(state.recap); signals.stateChanged.emit(JSON.stringify(state));
      }, 1200);
    },
    openRecap: path => { if (location.protocol !== "file:") location.href = path; },
    quit: () => {}
  };
  let listening = false;
  window.addEventListener("keydown", event => {
    if (event.ctrlKey && event.shiftKey && !listening) {
      listening = true; signals.agentStatus.emit("listening");
    }
  });
  window.addEventListener("keyup", event => {
    if (listening && ["Control", "Shift"].includes(event.key)) {
      listening = false; signals.agentStatus.emit("thinking");
      setTimeout(() => signals.agentStatus.emit("speaking"), 900);
      setTimeout(() => signals.agentStatus.emit("idle"), 2600);
    }
  });
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
