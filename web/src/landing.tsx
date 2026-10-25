/// <reference types="vite/client" />
import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import "./landing.css";
import bg from "./assets/landing-bg.jpg";
import { GeraldMark } from "./logo";

const DEMO_HREF = "./td.html";
const LIVE_HREF = "./td.html?voice=1";

const lines = ["Le prof qui", "voit ton écran", "et t’explique", "au tableau"];

function Clip() {
  return <svg className="clip" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
    <path d="M8 12.5 13.6 6.9a3 3 0 0 1 4.2 4.2l-7.1 7.1a4.6 4.6 0 0 1-6.5-6.5L11 4.9"/>
  </svg>;
}

function Sticker({label, tone, icon, className}: {label: React.ReactNode; tone: string; icon: React.ReactNode; className: string}) {
  return <div className={`sticker ${className}`} style={{"--tone": tone} as React.CSSProperties}>
    <span className="sticker-icon">{icon}</span><Clip/>
    <span className="sticker-label">{label}</span><i className="sticker-fold"/>
  </div>;
}

function Landing() {
  const scene = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scene.current;
    if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const move = (event: PointerEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--mx", String(event.clientX / innerWidth - .5));
        el.style.setProperty("--my", String(event.clientY / innerHeight - .5));
      });
    };
    addEventListener("pointermove", move);
    return () => { removeEventListener("pointermove", move); cancelAnimationFrame(frame); };
  }, []);

  return <main className="hero" ref={scene}>
    <div className="hero-bg" style={{backgroundImage: `url(${bg})`}}/>
    <div className="hero-grain"/>

    <header className="brand"><GeraldMark size={18}/><span>GERALD<sup>®</sup></span></header>

    <div className="glass status-card">
      <span className="mini-orb" aria-hidden="true"/>
      <div><p className="status-live"><i/>En ligne · voix en direct</p><p className="status-name">GERALD — TUTEUR À L’ÉCRAN</p></div>
    </div>

    <h1 className="headline" aria-label={lines.join(" ")}>
      {lines.map((line, i) => <span key={line} className="headline-line" style={{"--i": i} as React.CSSProperties}>{line}</span>)}
      <Sticker className="s1" tone="#8B5CF6" label="Voix en direct" icon={<svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>}/>
      <Sticker className="s2" tone="#E8C547" label={<>Δ = b² − 4ac</>} icon={<svg viewBox="0 0 24 24" fill="none" stroke="#161616" strokeWidth="2" strokeLinecap="round"><path d="M4 20 16 8M14 4l6 6M4 20l1.5-5L16 4.5"/></svg>}/>
      <Sticker className="s3" tone="#3B82F6" label="Il te montre" icon={<svg viewBox="0 0 24 24" fill="#fff"><path d="M5 3l14 7-6 2-2 6z"/></svg>}/>
    </h1>

    <p className="tagline"><span className="dash"/>Pas un chatbot.<br/>un prof qui t’aide<br/>pas à pas</p>

    <nav className="dock" aria-label="Commencer">
      <a className="cta cta-demo" href={DEMO_HREF}><span className="cta-kicker">Tester</span><span className="cta-title">La démo</span></a>
      <a className="cta cta-live" href={LIVE_HREF}><span className="cta-kicker"><i className="live-dot"/>Session live</span><span className="cta-title">Apprendre</span></a>
    </nav>

    <a className="cards" href={DEMO_HREF}>
      <span className="glass card c3"/><span className="glass card c2"/>
      <span className="glass card c1">
        <span className="card-thumb"><b>x² − 5x + 6</b><em>= 0</em></span>
        <span className="card-body"><span className="card-meta"><span>TD 4</span><span>2026</span></span><span className="card-title">POLYNÔMES</span><span className="card-link">OUVRIR LA DÉMO <span>→</span></span></span>
      </span>
    </a>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Landing/>);
