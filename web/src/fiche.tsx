import React from "react";
import { createRoot } from "react-dom/client";
import { getBridge } from "./bridge";
import { mountNotch } from "./notch";
import "katex/dist/katex.min.css";
import "./style.css";

const bridge = getBridge();
function Fiche() {
  return <main className="td-root"><article className="paper">
    <header className="td-head"><div className="td-meta"><span>Lycée — Mathématiques</span><span>Révision</span></div>
      <h1>Fiche de révision — Polynômes du second degré</h1>
      <div className="td-student"><span>Nom : ________</span><span>Date : ________</span></div>
    </header>
    <section className="reminder"><h2>Méthode</h2>
      <p>Un trinôme s’écrit <strong>ax² + bx + c</strong>, avec a ≠ 0 : a est le coefficient de x², b celui de x, et c le terme constant.</p>
      <p>On calcule le discriminant : <strong>Δ = b² − 4ac</strong>.</p>
      <p>Si Δ &gt; 0 : deux racines x₁ = (−b − √Δ)/(2a) et x₂ = (−b + √Δ)/(2a).</p>
      <p>Si Δ = 0 : une racine double x₀ = −b/(2a). Si Δ &lt; 0 : aucune racine réelle.</p>
    </section>
    <section className="exercise"><h2>Ce que tu as fait</h2>
      <p>x² − 5x + 6 = 0 : a = 1, b = −5, c = 6, Δ = 1, x₁ = 2, x₂ = 3.</p>
    </section>
    <section className="reminder"><h2>Point de vigilance</h2>
      <p>Ne pas inverser a et b ; dans la formule −b, respecter le signe de b.</p>
    </section>
    <button className="td-go" onClick={()=>bridge.openTd()}>Retour au TD</button>
  </article></main>;
}
createRoot(document.getElementById("root")!).render(<Fiche/>);
if (!window.qt) {
  const host = document.createElement("div"); host.className = "preview-notch-host";
  document.body.appendChild(host); mountNotch(host);
}
