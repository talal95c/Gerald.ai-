import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AppState, getBridge } from "./bridge";
import "./style.css";

const bridge = getBridge();
const emptyState: AppState = {
  greeting: "Bonjour.", hotkey_label: "CTRL + SHIFT", documents: [],
  conversations: [], session_open: false, recap_pending: false
};

function App() {
  const [mode, setMode] = useState("greeting");
  const [state, setState] = useState(emptyState);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<{document: string; page?: number}[]>([]);
  const [error, setError] = useState("");
  const [recap, setRecap] = useState("");
  useEffect(() => {
    bridge.state(json => setState(JSON.parse(json)));
    bridge.stateChanged.connect(json => setState(JSON.parse(json)));
    bridge.modeChanged.connect(setMode);
    bridge.answer.connect(json => {
      const result = JSON.parse(json);
      setAnswer(result.text);
      setSources(result.sources || []);
      setError("");
    });
    bridge.answerError.connect(setError);
    bridge.recapReady.connect(setRecap);
    const idle = window.setTimeout(() => { setMode("collapsed"); bridge.setMode("collapsed"); }, 6000);
    return () => window.clearTimeout(idle);
  }, []);
  const open = () => { setMode("panel"); bridge.setMode("panel"); };
  const settings = () => { setMode("settings"); bridge.setMode("settings"); };
  const close = () => { setMode("greeting"); bridge.setMode("greeting"); };
  const send = () => { if (question.trim()) { bridge.ask(question.trim()); setQuestion(""); } };
  if (mode === "collapsed") return <button className="collapsed" onMouseEnter={open} onClick={open}>Gerald <i /></button>;
  if (mode === "settings") return <section className="settings window">
    <aside><div className="eyebrow"><b /> GERALD</div>{["Général","Documents","Historique","Raccourcis"].map((x,i)=><button key={x} className={i===0?"active":""}>{x}</button>)}<button className="quit" onClick={()=>bridge.quit()}>Quitter Gerald</button></aside>
    <main><header><button className="back" onClick={close}>←</button><h1>Réglages</h1></header>
      <div className="setting-grid">
        <article><div className="eyebrow"><b/> GÉNÉRAL</div><h2>{state.greeting}</h2><p>Maintiens {state.hotkey_label} et demande-moi ce que tu veux.</p></article>
        <article><div className="eyebrow"><b/> DOCUMENTS</div>{state.documents.map(doc=><p className="row" key={doc.id}><i className={`dot ${doc.status}`} />{doc.filename}<button onClick={()=>bridge.deleteDocument(doc.id)}>×</button></p>)}<button className="pill dark" onClick={()=>bridge.addDocuments()}>Ajouter des documents →</button></article>
        <article><div className="eyebrow"><b/> HISTORIQUE</div><nav className="filters"><button>Toutes</button><button>Chat</button><button>Agent</button></nav>{state.conversations.map(c=><button className="history" key={c.id} onClick={()=>bridge.messages(c.id, setAnswer)}>{c.title}</button>)}</article>
        <article><div className="eyebrow"><b/> RACCOURCIS</div><p>Maintenir pour parler</p><kbd>{state.hotkey_label}</kbd></article>
      </div></main>
  </section>;
  if (mode === "panel") return <section className="panel window" onKeyDown={event=>{if(event.key==="Escape")close();}}>
    <header><div className="eyebrow"><b/> GERALD</div><button className="gear" onClick={settings} aria-label="Réglages">⚙</button></header>
    <h1>Dis bonjour à <em>Gerald.</em></h1><p className="sub">Tout ce que tu demandes, à la voix ou à l’écrit, se retrouve ici.</p>
    <div className="messages">{answer && <article className="answer">{answer}{sources.length>0&&<div className="sources">{sources.map((s,i)=><span key={i}>{s.document}{s.page?` · p. ${s.page}`:""}</span>)}</div>}</article>}{error&&<article>{error}</article>}</div>
    <footer>{state.session_open && <button className="pill accent" onClick={()=>bridge.endSession()}>{state.recap_pending?"Fiche de révision en préparation…":"Fin de session"}</button>}{recap&&<button className="pill accent" onClick={()=>bridge.openRecap(recap)}>Ouvrir la fiche →</button>}
      <button className="pill accent">{`Maintiens ${state.hotkey_label} pour parler`}</button><input value={question} placeholder="Demande à Gerald…" onFocus={()=>bridge.requestFocus(true)} onBlur={()=>bridge.requestFocus(false)} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();send();}}}/><button className="send" onClick={send}>↑</button></footer>
  </section>;
  return <section className="greeting window" onMouseEnter={()=>setMode("greeting")} onClick={open}>
    <div className="greeter"><h2>{state.greeting}</h2><p>Maintiens {state.hotkey_label} et demande-moi ce que tu veux.</p></div>
    <button className="pill accent" onClick={event=>{event.stopPropagation();bridge.openBoard("Exercice", "[]");}}>Tableau →</button>
    {state.session_open && <button className="pill accent session" onClick={event=>{event.stopPropagation();bridge.endSession();}}>{state.recap_pending?"Fiche en préparation…":"Fin de session"}</button>}
    <button className="gear" onClick={event=>{event.stopPropagation();settings();}}>⚙</button>
  </section>;
}
createRoot(document.getElementById("root")!).render(<App />);
