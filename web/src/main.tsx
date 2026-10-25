import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AppState, getBridge } from "./bridge";
import "./style.css";

const bridge = getBridge();
const settingSections = ["Général", "Documents", "Historique", "Raccourcis"];
const emptyState: AppState = {
  greeting: "Bonjour.", hotkey_label: "CTRL + SHIFT", documents: [],
  conversations: [], session_open: false, recap_pending: false
};

function Reveal({text}: {text: string}) {
  const words = text.split(/(\s+)/);
  return <>{words.map((word,index)=>/^\s+$/.test(word)?word:<span className="reveal-word" style={{animationDelay:`${index*40}ms`}} key={`${word}-${index}`}>{word}</span>)}</>;
}

function App() {
  const [mode, setMode] = useState("greeting");
  const [state, setState] = useState(emptyState);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<{document: string; page?: number}[]>([]);
  const [error, setError] = useState("");
  const [recap, setRecap] = useState("");
  const [settingsTab, setSettingsTab] = useState("Général");
  const [historyFilter, setHistoryFilter] = useState("Toutes");
  const [historyMessages, setHistoryMessages] = useState<{role: string; text: string}[] | null>(null);
  const idleTimer = useRef<number | null>(null);
  const pointerInside = useRef(false);
  const modeRef = useRef(mode);
  const scheduleCollapse = () => {
    if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => {
      if (!pointerInside.current && modeRef.current === "greeting") {
        setMode("collapsed"); bridge.setMode("collapsed");
      }
    }, 6000);
  };
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => {
    const connect = () => {
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
    };
    if (window.qt && !window.bridge) {
      window.addEventListener("gerald-bridge-ready", connect, {once:true});
    } else {
      connect();
    }
    scheduleCollapse();
    return () => {
      if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
      window.removeEventListener("gerald-bridge-ready", connect);
    };
  }, []);
  const open = () => {
    if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
    setMode("panel"); bridge.setMode("panel");
  };
  const settings = () => {
    pointerInside.current = false;
    if (idleTimer.current !== null) window.clearTimeout(idleTimer.current);
    setMode("settings"); bridge.setMode("settings");
  };
  const close = () => { setMode("greeting"); bridge.setMode("greeting"); scheduleCollapse(); };
  const send = () => { if (question.trim()) { bridge.ask(question.trim()); setQuestion(""); } };
  const openConversation = (id: number) => bridge.messages(id, json => setHistoryMessages(JSON.parse(json)));
  if (mode === "collapsed") return <button className="collapsed" onMouseEnter={open} onClick={open}>Gerald <i /></button>;
  if (mode === "settings") return <section className="settings window">
    <aside><div className="eyebrow"><b /> GERALD</div>{settingSections.map(x=><button key={x} className={settingsTab===x?"active":""} onClick={()=>{setSettingsTab(x);setHistoryMessages(null);}}>{x}</button>)}<button className="quit" onClick={()=>bridge.quit()}>Quitter Gerald</button></aside>
    <main onKeyDown={event=>{if(event.key==="Escape")close();}}><header><button className="back" onClick={close}>←</button><h1>{settingsTab}</h1></header>
      {settingsTab==="Général"&&<div className="setting-grid"><article><div className="eyebrow"><b/> APERÇU</div><h2>{state.greeting}</h2><p>Maintiens {state.hotkey_label} et demande-moi ce que tu veux.</p></article></div>}
      {settingsTab==="Documents"&&<div className="setting-grid"><article><div className="eyebrow"><b/> DOCUMENTS</div>{state.documents.map(doc=><p className="row" key={doc.id}><i className={`dot ${doc.status}`} /><span>{doc.filename}{doc.error&&<small>{doc.error}</small>}</span><button aria-label={`Supprimer ${doc.filename}`} onClick={()=>bridge.deleteDocument(doc.id)}>×</button></p>)}<button className="pill dark" onClick={()=>bridge.addDocuments()}>Ajouter des documents →</button></article></div>}
      {settingsTab==="Historique"&&<div className="setting-grid"><article><div className="eyebrow"><b/> HISTORIQUE</div><nav className="filters">{["Toutes","Chat","Agent"].map(x=><button className={historyFilter===x?"active":""} key={x} onClick={()=>setHistoryFilter(x)}>{x}</button>)}</nav>{historyMessages?<><button className="history-back" onClick={()=>setHistoryMessages(null)}>← Retour</button>{historyMessages.map((message,index)=><p className={`history-message ${message.role}`} key={index}>{message.text}</p>)}</>:state.conversations.filter(c=>historyFilter==="Toutes"||c.source.toLowerCase()===historyFilter.toLowerCase()).map(c=><button className="history" key={c.id} onClick={()=>openConversation(c.id)}>{c.title}</button>)}</article></div>}
      {settingsTab==="Raccourcis"&&<div className="setting-grid"><article><div className="eyebrow"><b/> RACCOURCIS</div><p>Maintenir pour parler</p><kbd>{state.hotkey_label}</kbd></article></div>}
    </main>
  </section>;
  if (mode === "panel") return <section className="panel window" onKeyDown={event=>{if(event.key==="Escape")close();}} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node))close();}}>
    <header><div className="eyebrow"><b/> GERALD</div><button className="gear" onClick={settings} aria-label="Réglages">⚙</button></header>
    <h1><Reveal text="Dis bonjour à"/> <em><Reveal text="Gerald."/></em></h1><p className="sub">Tout ce que tu demandes, à la voix ou à l’écrit, se retrouve ici.</p>
    <div className="messages">{answer && <article className="answer"><Reveal text={answer}/>{sources.length>0&&<div className="sources">{sources.map((s,i)=><span key={i}>{s.document}{s.page?` · p. ${s.page}`:""}</span>)}</div>}</article>}{error&&<article>{error}</article>}</div>
    <footer>{state.session_open && <button className="pill accent" onClick={()=>bridge.endSession()}>{state.recap_pending?"Fiche de révision en préparation…":"Fin de session"}</button>}{recap&&<button className="pill accent" onClick={()=>bridge.openRecap(recap)}>Ouvrir la fiche →</button>}
      <button className="pill accent">{`Maintiens ${state.hotkey_label} pour parler`}</button><input value={question} placeholder="Demande à Gerald…" onFocus={()=>bridge.requestFocus(true)} onBlur={()=>bridge.requestFocus(false)} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();send();}}}/><button className="send" onClick={send}>↑</button></footer>
  </section>;
  return <section className="greeting window" onMouseEnter={()=>{pointerInside.current=true;if(idleTimer.current!==null)window.clearTimeout(idleTimer.current);setMode("greeting");}} onMouseLeave={()=>{pointerInside.current=false;scheduleCollapse();}} onClick={open}>
    <div className="greeter"><h2><Reveal text={state.greeting}/></h2><p>Maintiens {state.hotkey_label} et demande-moi ce que tu veux.</p></div>
    <button className="pill accent" onClick={event=>{event.stopPropagation();bridge.openBoard("Exercice", "[]");}}>Tableau →</button>
    {state.session_open && <button className="pill accent session" onClick={event=>{event.stopPropagation();bridge.endSession();}}>{state.recap_pending?"Fiche en préparation…":"Fin de session"}</button>}
    {recap&&<button className="pill accent session" onClick={event=>{event.stopPropagation();bridge.openRecap(recap);}}>Ouvrir la fiche →</button>}
    <button className="gear" onClick={event=>{event.stopPropagation();settings();}}>⚙</button>
  </section>;
}
createRoot(document.getElementById("root")!).render(<App />);
