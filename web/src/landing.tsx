/// <reference types="vite/client" />
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./landing.css";
import { GeraldMark } from "./logo";

const DEMO_HREF = "./td.html";
const LIVE_HREF = "./td.html?voice=1";
const WORD = "Gerald";

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);
  return <time className="clock">{now.toLocaleTimeString("en-US")}</time>;
}

function Ruler() {
  return <div className="ruler" aria-hidden="true">
    {Array.from({length: 40}, (_, i) => <span key={i} style={{left: i * 100}}>{i ? i * 100 : ""}</span>)}
  </div>;
}

function Arrow({color}: {color: string}) {
  return <svg className="arrow" viewBox="0 0 32 32" aria-hidden="true"><path d="M3 3l26 10-11 3.5L13.5 29z" fill={color} stroke="#111212" strokeWidth="2" strokeLinejoin="round"/></svg>;
}

function Cursor({label, className, children}: {label: string; className: string; children: React.ReactNode}) {
  return <div className={`peer ${className}`}><span className="peer-bubble">{children}</span><span className="peer-name">{label}</span></div>;
}

function Landing() {
  const you = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = you.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const move = (e: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--dx", `${(e.clientX / innerWidth - .5) * 40}px`);
        el.style.setProperty("--dy", `${(e.clientY / innerHeight - .5) * 30}px`);
      });
    };
    addEventListener("pointermove", move);
    return () => { removeEventListener("pointermove", move); cancelAnimationFrame(frame); };
  }, []);

  return <div className="page">
    <header className="nav">
      <a className="nav-logo" href="./landing.html" aria-label="Gerald"><GeraldMark size={16}/></a>
      <span className="nav-sep"/>
      <span className="nav-tab"><GeraldMark size={10}/>HOME</span>
      <span className="nav-spacer"/>
      <span className="kbd"><kbd>CTRL</kbd>+<kbd>SHIFT</kbd> to talk</span>
      <a className="nav-cta" href={LIVE_HREF}><i className="live-dot"/>LEARN LIVE</a>
    </header>
    <Ruler/>

    <main className="hero">
      <Clock/>
      <div className="stage">
        <p className="hello">say hi to<svg viewBox="0 0 80 12" aria-hidden="true"><path d="M2 5c22-3 50-3 76-1M8 10c20-2 44-2 64-1" fill="none" stroke="#111212" strokeWidth="1.4" strokeLinecap="round"/></svg></p>
        <span className="tag tag-green">Sees your screen</span>
        <span className="tag tag-yellow">Explains at the board</span>
        <h1 className="select" aria-label={WORD}>
          {[...WORD].map((c, i) => <span key={i} className="glyph" style={{"--i": i} as React.CSSProperties}>{c}</span>)}
          <i className="h tl"/><i className="h tr"/><i className="h bl"/><i className="h br"/>
        </h1>
        <p className="status"><i className="status-dot"/>YOUR AI TUTOR, READY WHEN YOU ARE</p>
      </div>

      <Cursor label="Gerald" className="peer-gerald"><span className="mini-orb"/></Cursor>
      <div className="peer-you-wrap" ref={you}><Cursor label="You" className="peer-you"><GeraldMark size={12}/></Cursor></div>

      <div className="pill pill-pink"><Arrow color="#E11D63"/><span>Δ = b² − 4ac</span></div>
      <div className="pill pill-yellow"><span>MATH · PHYSICS · CS</span><Arrow color="#E8B425"/></div>

      <p className="tagline">The tutor <span className="ico ico-ring"/> that draws<br/>on your screen <span className="ico ico-pen">✎</span>.</p>

      <nav className="ctas" aria-label="Get started">
        <a className="cta" href={DEMO_HREF}><span className="cta-ico cta-ico-blue">»</span>TRY THE DEMO</a>
        <a className="cta cta-live" href={LIVE_HREF}><span className="cta-ico cta-ico-violet"><i className="live-dot"/></span>LEARN LIVE</a>
      </nav>
    </main>
    <span className="corner-chip">BETA · VOICE</span>
  </div>;
}

createRoot(document.getElementById("root")!).render(<Landing/>);
