import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { AppState, getBridge } from "./bridge";
import "./style.css";
import { Orb } from "./orb";
import { Reveal } from "./reveal";

const bridge = getBridge();
const tabs = ["Tableau", "Documents", "Historique", "Raccourcis"];
type Recap = {path: string; title: string; created_at: string};
type NotchState = AppState & {recaps?: Recap[]; recap_error?: string | null};
type HistoryMessage = {role: string; text: string; created_at?: string};
const emptyState: NotchState = {
  greeting: "Bonjour.", hotkey_label: "CTRL + SHIFT", documents: [],
  conversations: [], session_open: false, recap_pending: false, last_exercise: null, recaps: []
};
const statusText: Record<string, string> = {listening: "J’écoute", thinking: "Je réfléchis", speaking: "Je parle", error: "Micro indisponible", offline: "Hors ligne"};

function localTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("fr-FR", {hour:"2-digit", minute:"2-digit"});
}

function dayLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date inconnue";
  const now = new Date();
  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
  if (dateDay === today) return "Aujourd’hui";
  if (dateDay === yesterday) return "Hier";
  return new Intl.DateTimeFormat("fr-FR", {weekday:"short", day:"numeric", month:"short"}).format(date);
}

function groupedHistory(conversations: AppState["conversations"]) {
  return conversations.slice().sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
    .reduce<Record<string, AppState["conversations"]>>((groups, conversation) => {
      (groups[dayLabel(conversation.updated_at)] ??= []).push(conversation);
      return groups;
    }, {});
}

const icons: Record<string, React.ReactNode> = {
  "Tableau": <><rect x="3" y="4" width="14" height="10" rx="2"/><path className="cut" d="M6 11.2c1.4-3.6 2.6-3.6 4 0s2.6 3.6 4 0M7 17h6M10 14v3"/></>,
  "Documents": <><path d="M6 3h5.6L15 6.4V16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path className="cut" d="M11.4 3v3.6H15M7.6 10.2h4.8M7.6 13h3.4"/></>,
  "Historique": <><circle cx="10" cy="10" r="6.6"/><path className="cut" d="M10 6.4V10l2.6 1.6"/></>,
  "Raccourcis": <><rect x="3" y="5.5" width="14" height="9" rx="2.2"/><path className="cut" d="M6 8.6h.01M8.7 8.6h.01M11.3 8.6h.01M14 8.6h.01M7 11.6h6"/></>,
};

function NavIcon({name, active}: {name: string; active: boolean}) {
  const id = `g-${tabs.indexOf(name)}`;
  return <svg className="nav-icon" viewBox="0 0 20 20" aria-hidden="true">
    <defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#FFFDBD"/><stop offset="1" stopColor="#E8C547"/></linearGradient></defs>
    <g fill={active ? `url(#${id})` : "none"} stroke={active ? "#FFFDBD" : "#262626"} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round">{icons[name]}</g>
  </svg>;
}

function NavBar({active, onChange}: {active: string; onChange: (tab: string) => void}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [thumb, setThumb] = useState({left: 0, width: 0});
  useEffect(() => {
    const el = refs.current[active];
    if (el) setThumb({left: el.offsetLeft, width: el.offsetWidth});
  }, [active]);
  return <nav className="navbar" role="tablist">
    <span className="nav-thumb" style={{transform:`translateX(${thumb.left}px)`, width: thumb.width}} />
    {tabs.map(x=><button key={x} ref={el=>{refs.current[x]=el;}} role="tab" aria-selected={active===x} className={active===x?"active":""} onClick={()=>onChange(x)}><NavIcon name={x} active={active===x}/><span>{x}</span></button>)}
  </nav>;
}




function DocView({doc, folder, hotkey, onBack}: {doc: AppState["documents"][number]; folder: string; hotkey: string; onBack: () => void}) {
  const [text, setText] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{q: string; text: string} | null>(null);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => { bridge.documentText(doc.id, setText); }, [doc.id]);
  useEffect(() => {
    const done = (json: string) => { setWaiting(false); setAnswer(a => ({q: a?.q ?? "", text: JSON.parse(json).text})); };
    const fail = (message: string) => { setWaiting(false); setAnswer(a => ({q: a?.q ?? "", text: message})); };
    bridge.answer.connect(done); bridge.answerError.connect(fail);
    return () => { bridge.answer.disconnect?.(done); bridge.answerError.disconnect?.(fail); };
  }, []);
  const send = () => {
    const q = question.trim(); if (!q) return;
    setAnswer({q, text: ""}); setWaiting(true); setQuestion("");
    bridge.ask(`À propos du document « ${doc.filename} » : ${q}`);
  };
  const isTd = /^TD\b/i.test(doc.filename);
  return <div className="doc-view">
    <div className="doc-head"><button className="add" onClick={onBack}>← {folder}</button><b>{doc.filename}</b></div>
    <article className="doc-page">{text ? text.split("\n").map((l,i)=><p key={i}>{l || "\u00a0"}</p>) : <p className="muted">{doc.status === "ready" ? "Aperçu indisponible." : "Indexation en cours…"}</p>}</article>
    {answer && <div className="doc-answer"><small>{answer.q}</small><p>{waiting ? <span className="thinking"><i/><i/><i/></span> : <Reveal text={answer.text}/>}</p></div>}
    {isTd && <button className="doc-open-td" onClick={()=>bridge.openTd()}>Ouvrir le TD</button>}
    <form className="doc-ask" onSubmit={e=>{e.preventDefault();send();}}>
      <i className="dot-live"/><input onFocus={()=>bridge.requestFocus(true)} onBlur={()=>bridge.requestFocus(false)} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Une question sur ce document ?"/><kbd>{hotkey}</kbd>
    </form>
  </div>;
}

function Folders({docs, recaps, hotkey, uploadError, onDocumentOpen, onBack}: {
  docs: AppState["documents"]; recaps: Recap[]; hotkey: string;
  uploadError?: string; onDocumentOpen: (id: number) => void; onBack: () => void;
}) {
  const [doc, setDoc] = useState<AppState["documents"][number] | null>(null);
  const onOpen = (d: AppState["documents"][number]) => {
    if (bridge.openDocument) onDocumentOpen(d.id);
    else { setDoc(d); onDocumentOpen(d.id); }
  };
  const [open, setOpen] = useState<string | null>(null);
  const groups = docs.reduce<Record<string, AppState["documents"]>>((acc, d) => { (acc[d.folder || "Mes cours"] ??= []).push(d); return acc; }, {});
  if (doc) return <DocView doc={doc} folder={doc.folder || "Mes cours"} hotkey={hotkey} onBack={()=>{setDoc(null);onBack();}}/>;
  if (open === "Fiches") return <div className="folder-open">
    <button className="add" onClick={()=>setOpen(null)}>← Dossiers</button><span className="folder-title">Fiches</span>
    <div className="fan">{recaps.map(recap=><button className="recap-card" key={recap.path} onClick={()=>bridge.openRecap(recap.path)}>
      <b>{recap.title}</b><small>Fiche du {new Date(recap.created_at).toLocaleDateString("fr-FR",{day:"numeric",month:"short"})}</small>
    </button>)}</div>
  </div>;
  if (open && groups[open]) return <div className="folder-open">
    <button className="add" onClick={()=>setOpen(null)}>← Dossiers</button><span className="folder-title">{open}</span>
    <div className="fan">{groups[open].map((doc,i)=><article className="sheet-card" key={doc.id} onClick={()=>onOpen(doc)} style={{animationDelay:`${i*45}ms`}}>
      <i className={`dot ${doc.status}`} /><b>{doc.filename}</b><small>{doc.status === "ready" ? "Prêt" : doc.error || "Indexation…"}</small>
      {doc.id >= 0 && <button aria-label={`Supprimer ${doc.filename}`} onClick={e=>{e.stopPropagation();bridge.deleteDocument(doc.id);}}>×</button>}</article>)}</div>
  </div>;
  return <div className="folders">
    {uploadError && <p className="upload-error" role="alert">{uploadError}</p>}
    {Object.entries(groups).map(([name, items])=><button className="folder" key={name} onClick={()=>setOpen(name)}>
      <span className="papers">{items.slice(0,3).map((d,i)=><i key={d.id} style={{"--i":i} as React.CSSProperties}/>)}</span>
      <span className="pocket"/><span className="folder-name">{name}</span><span className="folder-count">{items.length} fichier{items.length>1?"s":""}</span>
    </button>)}
    {recaps.length > 0 && <button className="folder" onClick={()=>setOpen("Fiches")}><span className="papers"><i style={{"--i":0} as React.CSSProperties}/></span><span className="pocket"/><span className="folder-name">Fiches</span><span className="folder-count">{recaps.length} fiche{recaps.length>1?"s":""}</span></button>}
    <button className="folder add-folder" onClick={()=>bridge.addDocuments()}><span className="plus">+</span><span className="folder-name">Ajouter</span></button>
  </div>;
}

function App() {
  const [mode, setMode] = useState(window.qt || !/(td|board|fiche)\.html$/.test(location.pathname) ? "greeting" : "collapsed");
  const [state, setState] = useState<NotchState>(emptyState);
  const [status, setStatus] = useState("idle");
  const [tab, setTab] = useState("Documents");
  const [recap, setRecap] = useState("");
  const [historyMessages, setHistoryMessages] = useState<HistoryMessage[] | null>(null);
  const timer = useRef<number | null>(null);
  const go = (next: string) => { setMode(next); bridge.setMode(next); };
  const clear = () => { if (timer.current !== null) window.clearTimeout(timer.current); };
  const later = (next: string, ms: number) => { clear(); timer.current = window.setTimeout(() => go(next), ms); };
  useEffect(() => {
    const connect = () => {
      const applyState = (json: string) => {
        const next = JSON.parse(json) as NotchState;
        setState(next);
        if (typeof next.recap === "string") setRecap(next.recap);
      };
      bridge.state(applyState);
      bridge.stateChanged.connect(applyState);
      bridge.modeChanged.connect(next => { clear(); setMode(next); });
      bridge.recapReady.connect(setRecap);
      bridge.agentStatus?.connect(setStatus);
    };
    if (window.qt && !window.bridge) window.addEventListener("gerald-bridge-ready", connect, {once:true});
    else connect();
    later("collapsed", 2600);
    return clear;
  }, []);
  useEffect(() => {
    document.body.classList.toggle("qt-notch", Boolean(window.qt));
    document.body.classList.toggle("notch-document-open", mode === "document");
  }, [mode]);
  const pick = (name: string) => {
    if (name === "Tableau") {
      bridge.openBoard(
        state.last_exercise?.title ?? "",
        JSON.stringify(state.last_exercise?.lines ?? []),
      );
      go("collapsed");
      return;
    }
    if (mode === "document" && name === "Documents") return;
    setHistoryMessages(null);
    if (mode === "settings" && tab === name) { go("panel"); return; }
    setTab(name); go("settings");
  };
  const active = status !== "idle";
  const pillLabel = active ? statusText[status] ?? status : mode === "greeting" ? state.greeting : `Maintiens ${state.hotkey_label}`;
  if (mode === "greeting" || mode === "collapsed") return <button className={`notch pill-notch m-${mode} s-${status}`} onClick={()=>{clear();go("panel");}}>
    <Orb status={status} size={24}/><span key={pillLabel}><Reveal text={pillLabel}/></span>
  </button>;
  return <section className={`notch sheet m-${mode}`} onMouseEnter={clear} onMouseLeave={()=>{ if (mode !== "document" && document.activeElement?.tagName !== "INPUT") later("collapsed", 700); }} onKeyDown={e=>{if(e.key==="Escape")go("collapsed");}}>
    <div className="bar">
      <span className="status"><Orb status={status} size={28}/><span>{active ? statusText[status] ?? status : state.hotkey_label}</span></span>
      <NavBar active={mode === "settings" ? tab : mode === "document" ? "Documents" : ""} onChange={pick}/>
      {state.session_open ? <button className="end" title={state.recap_error || undefined} onClick={()=>bridge.endSession()}>{state.recap_pending ? "Fiche…" : state.recap_error ? "Réessayer la fiche" : "Fin de session"}</button>
        : recap ? <button className="end" onClick={()=>bridge.openRecap(recap)}>Fiche →</button>
        : <button className="quit" onClick={()=>bridge.quit()} aria-label="Quitter">⏻</button>}
    </div>
    {state.session_open && state.recap_error && !state.recap_pending && <p className="recap-error" role="status">{state.recap_error}</p>}
    {(mode === "settings" || mode === "document") && <div className={`content ${mode === "document" ? "document-content" : ""}`} key={tab}>
      {(mode === "document" || tab === "Documents") && <Folders
        docs={state.documents} recaps={state.recaps ?? []} hotkey={state.hotkey_label} uploadError={state.upload_error}
        onDocumentOpen={id=>{
          if (bridge.openDocument) { bridge.openDocument(id); go("collapsed"); }
          else go("document");
        }} onBack={()=>go("settings")}
      />}
      {mode === "settings" && tab === "Historique" && (historyMessages
        ? <><button className="add" onClick={()=>setHistoryMessages(null)}>← Retour</button>{historyMessages.map((m,i)=><p className={`msg ${m.role}`} key={i}><span>{m.text}</span>{m.created_at && <time>{localTime(m.created_at)}</time>}</p>)}</>
        : Object.entries(groupedHistory(state.conversations)).map(([day, conversations])=><section className="history-group" key={day}><h3>{day}</h3>{conversations.map(c=><button className="row link history-row" key={c.id} onClick={()=>bridge.messages(c.id,json=>setHistoryMessages(JSON.parse(json)))}><i className={`tag ${c.source}`}>{c.source === "agent" ? "Voix" : "Écrit"}</i><span>{c.title}</span><time>{localTime(c.updated_at)}</time></button>)}</section>))}
      {tab === "Raccourcis" && <div className="shortcuts">
        {[[state.hotkey_label, "Maintiens pour parler", "Relâche : il te répond à voix haute et montre à l’écran."],
          ["Échap", "Ferme l’encoche", "Revient à la petite pilule."],
          ["Clic", "Ouvre l’encoche", "Tableau, documents, historique."]].map(([k, t, d], i)=>
          <div className="shortcut" key={t} style={{animationDelay:`${i*50}ms`}}><span className="keys">{k.split("+").map(x=><kbd key={x}>{x.trim()}</kbd>)}</span><b>{t}</b><small>{d}</small></div>)}
      </div>}
    </div>}
  </section>;
}

export function mountNotch(el: HTMLElement) {
  createRoot(el).render(<App />);
}
