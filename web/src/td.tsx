import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import katex from "katex";
import "katex/dist/katex.min.css";
import "./style.css";
import { getBridge } from "./bridge";
import { Orb } from "./orb";
import { Reveal } from "./reveal";
const bridge = getBridge();

const exercises = [
  { title:"Exercice 1", lines:["Résous dans ℝ : x² − 5x + 6 = 0"], math:"x^2 - 5x + 6 = 0", instruction:"Résous l’équation et vérifie tes solutions." },
  { title:"Exercice 2", lines:["Résous dans ℝ : 2x² + 3x − 2 = 0"], math:"2x^2 + 3x - 2 = 0", instruction:"Résous l’équation et vérifie tes solutions." },
  { title:"Exercice 3", lines:["Écris sous forme canonique : x² − 4x + 1"], math:"x^2 - 4x + 1", instruction:"Écris l’expression sous forme canonique." },
  { title:"Exercice 4", lines:["Étudie le signe de −x² + x + 6"], math:"-x^2 + x + 6", instruction:"Dresse le tableau de signes." }
];

function exerciseIn(text: string) {
  const match = text.match(/(?:exercice|exo)\s*(\d)/i);
  return exercises[(match ? Number(match[1]) : 1) - 1] ?? exercises[0];
}

function AskBar() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{q: string; text: string; ex: typeof exercises[number]} | null>(null);
  const [status, setStatus] = useState("idle");
  useEffect(() => {
    const onAnswer = (json: string) => {
      const text = JSON.parse(json).text ?? "";
      setAnswer(current => current && {...current, text});
      setStatus("speaking");
      window.setTimeout(() => setStatus("idle"), Math.min(6000, text.split(/\s+/).length * 40 + 1200));
    };
    const onError = () => setStatus("idle");
    bridge.answer.connect(onAnswer);
    bridge.answerError.connect(onError);
    return () => { bridge.answer.disconnect?.(onAnswer); bridge.answerError.disconnect?.(onError); };
  }, []);
  const send = () => {
    const q = question.trim();
    if (!q) return;
    setAnswer({q, text: "", ex: exerciseIn(q)});
    setStatus("thinking");
    setQuestion("");
    bridge.ask(`TD 4 — Polynômes du second degré. ${q}`);
  };
  return <div className="td-assist">
    {answer && <div className="td-answer" key={answer.q}>
      <span className="td-q">{answer.q}</span>
      {answer.text ? <p><Reveal text={answer.text}/></p> : <p><span className="thinking"><i/><i/><i/></span></p>}
      {answer.text && <button className="td-go" style={{animationDelay:`${answer.text.split(/\s+/).length*80}ms`}} onClick={()=>bridge.openBoard(answer.ex.title, JSON.stringify(answer.ex.lines))}>Viens, on va au tableau · {answer.ex.title} →</button>}
    </div>}
    <form className="td-ask" onSubmit={e=>{e.preventDefault(); send();}}>
      <Orb status={status} size={30}/>
      <input value={question} onChange={e=>setQuestion(e.target.value)} onFocus={()=>bridge.requestFocus(true)} onBlur={()=>bridge.requestFocus(false)} placeholder="Une question sur le TD ? Je t’explique."/>
      <kbd>CTRL + SHIFT</kbd>
    </form>
  </div>;
}

function TD(){return <main className="td-root"><article className="paper"><header className="td-head"><div className="td-meta"><span>Lycée — Mathématiques</span><span>TD 4</span></div><h1>Polynômes du second degré</h1><div className="td-student"><span>Nom : __________________</span><span>Date : ________________</span></div></header>
  <section className="reminder"><h2>Rappel de cours</h2><p>Pour <span dangerouslySetInnerHTML={{__html:katex.renderToString("ax^2+bx+c=0")}} />, le discriminant vaut <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta=b^2-4ac")}} />. Si <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta>0")}} />, l’équation possède deux racines réelles.</p></section>
  {exercises.map(ex=><section className="exercise" key={ex.title} onClick={()=>bridge.openBoard(ex.title,JSON.stringify(ex.lines))}><p className="exercise-lead"><strong>{ex.title}.</strong><span dangerouslySetInnerHTML={{__html:katex.renderToString(ex.math)}}/></p><p>{ex.instruction}</p><button className="open-ex">Ouvrir au tableau →</button></section>)}
  </article><AskBar/></main>}
createRoot(document.getElementById("root")!).render(<TD/>);
