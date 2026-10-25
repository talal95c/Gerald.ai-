import React from "react";
import { createRoot } from "react-dom/client";
import katex from "katex";
import "katex/dist/katex.min.css";
import "./style.css";
import { getBridge } from "./bridge";
const bridge = getBridge();

const exercises = [
  { title:"Exercice 1", lines:["Résous dans ℝ : x² − 5x + 6 = 0"], math:"x^2 - 5x + 6 = 0", instruction:"Résous l’équation et vérifie tes solutions." },
  { title:"Exercice 2", lines:["Résous dans ℝ : 2x² + 3x − 2 = 0"], math:"2x^2 + 3x - 2 = 0", instruction:"Résous l’équation et vérifie tes solutions." },
  { title:"Exercice 3", lines:["Écris sous forme canonique : x² − 4x + 1"], math:"x^2 - 4x + 1", instruction:"Écris l’expression sous forme canonique." },
  { title:"Exercice 4", lines:["Étudie le signe de −x² + x + 6"], math:"-x^2 + x + 6", instruction:"Dresse le tableau de signes." }
];
function TD(){return <main className="td-root"><article className="paper"><header className="td-head"><p>Lycée — Mathématiques · TD 4 · Polynômes du second degré</p><h1>Travaux dirigés</h1><p>Nom : ____________________　　Date : ______________</p></header>
  <section className="reminder"><h2>Rappel de cours</h2><p>Pour <span dangerouslySetInnerHTML={{__html:katex.renderToString("ax^2+bx+c=0")}} />, le discriminant vaut <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta=b^2-4ac")}} />. Si <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta>0")}} />, l’équation possède deux racines réelles.</p></section>
  {exercises.map(ex=><section className="exercise" key={ex.title}><h2>{ex.title}</h2><p dangerouslySetInnerHTML={{__html:katex.renderToString(ex.math)}}/><p>{ex.instruction}</p><button className="open-ex" onClick={()=>bridge.openBoard(ex.title,JSON.stringify(ex.lines))}>Ouvrir au tableau →</button></section>)}
  </article></main>}
createRoot(document.getElementById("root")!).render(<TD/>);
