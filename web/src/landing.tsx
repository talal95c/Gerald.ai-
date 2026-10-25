/// <reference types="vite/client" />
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./landing.css";
import { GeraldMark } from "./logo";

const DEMO_HREF = "./td.html";
const LIVE_HREF = "./td.html?voice=1";

function useReveal() {
  useEffect(() => {
    const io = new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), {threshold: .15});
    document.querySelectorAll(".rv").forEach(el => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function useInView<T extends Element>(): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!ref.current) return;
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), {threshold: .3});
    io.observe(ref.current);
    return () => io.disconnect();
  }, []);
  return [ref, on];
}

const Arrow = () => <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>;
const Check = () => <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>;

function Badge({icon, children}: {icon: string; children: React.ReactNode}) {
  return <span className="badge rv"><span className="badge-i" aria-hidden="true">{icon}</span>{children}</span>;
}

function Head({badge, icon, title, sub, left}: {badge: string; icon: string; title: React.ReactNode; sub: string; left?: boolean}) {
  return <div className={`head${left ? " left" : ""}`}>
    <Badge icon={icon}>{badge}</Badge>
    <h2 className="rv">{title}</h2>
    <p className="rv">{sub}</p>
  </div>;
}

function Orb({size = 28}: {size?: number}) {
  return <span className="orb" style={{width: size, height: size}} aria-hidden="true"/>;
}

function Nav() {
  const [solid, setSolid] = useState(false);
  useEffect(() => {
    const f = () => setSolid(scrollY > 12);
    f(); addEventListener("scroll", f, {passive: true});
    return () => removeEventListener("scroll", f);
  }, []);
  return <header className={`nav${solid ? " solid" : ""}`}>
    <a className="brand" href="#top"><span className="brand-mark"><GeraldMark size={12}/></span>Gerald</a>
    <nav className="links">
      <a href="#how">How it works</a><a href="#features">Features</a><a href="#capabilities">Capabilities</a><a href="#faq">FAQ</a>
    </nav>
    <div className="nav-cta">
      <a className="btn ghost sm" href={DEMO_HREF}>Try the demo</a>
      <a className="btn primary sm" href={LIVE_HREF}>Learn live</a>
    </div>
  </header>;
}

function HeroBoard() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep(s => (s + 1) % 5), 2200);
    return () => clearInterval(id);
  }, []);
  return <div className="board-card">
    <div className="ex">
      <span className="ex-tag">TD 4 · Exercise 1</span>
      <div className="ex-eq">Solve <b>x² − 5x + 6 = 0</b></div>
    </div>
    <div className="ink">
      <div className="ink-line">Δ = <span className={`mk${step >= 1 ? " on" : ""}`}>b²</span> − <span className={`mk${step >= 1 ? " on" : ""}`}>4ac</span></div>
      <div className={`ink-line hand${step >= 2 ? " on" : ""}`}>Δ = 25 − 24 = 1</div>
      <div className={`ink-line hand${step >= 3 ? " on" : ""}`}>x₁ = 2 &nbsp;·&nbsp; x₂ = 3</div>
    </div>
    <div className="think"><Check/> Looked at your attempt</div>
    <div className={`say${step >= 4 ? " on" : ""}`}>
      <Orb size={20}/>
      <span>{step >= 4 ? "Bravo! Both roots are right. Want a revision sheet?" : "Look at b² first. What is (−5)²?"}</span>
    </div>
    <div className="chips">
      <span className="chip">Give me a hint</span>
      <span className="chip">Why Δ?</span>
      <span className="chip">Show the parabola</span>
    </div>
    <div className="talk">
      <Orb size={22}/>
      <span className="talk-t">Hold <kbd>Ctrl</kbd> + <kbd>Shift</kbd> to talk</span>
      <span className="wave" aria-hidden="true">{Array.from({length: 14}, (_, i) => <i key={i} style={{animationDelay: `${i * 70}ms`}}/>)}</span>
    </div>
  </div>;
}

function Hero() {
  return <section className="hero" id="top">
    <span className="badge pop"><span className="badge-i dot" aria-hidden="true"/>Voice tutor for students · Beta</span>
    <h1 className="pop d1">A tutor that explains<br/>it at your board</h1>
    <p className="lead pop d2">Gerald sees your exercise, talks you through the method<br className="br"/> and draws on your screen — without giving away the answer.</p>
    <div className="cta pop d3">
      <a className="btn ghost" href={DEMO_HREF}>Try the demo</a>
      <a className="btn primary" href={LIVE_HREF}>Learn live <Arrow/></a>
    </div>
    <div className="stage pop d4"><HeroBoard/></div>
  </section>;
}

function Subjects() {
  const s = ["Mathematics", "Physics", "Chemistry", "Computer science", "Economics", "Biology"];
  return <section className="subjects">
    <p className="rv">Works with the courses you already have</p>
    <div className="marquee"><div className="track">
      {[...s, ...s].map((x, i) => <span key={i}>{x}</span>)}
    </div></div>
  </section>;
}

function Typing({lines}: {lines: string[]}) {
  const [ref, on] = useInView<HTMLDivElement>();
  const [t, setT] = useState("");
  const [li, setLi] = useState(0);
  useEffect(() => {
    if (!on) return;
    const full = lines[li];
    if (t.length < full.length) { const id = setTimeout(() => setT(full.slice(0, t.length + 1)), 45); return () => clearTimeout(id); }
    const id = setTimeout(() => { setT(""); setLi((li + 1) % lines.length); }, 1600);
    return () => clearTimeout(id);
  }, [on, t, li, lines]);
  return <div className="type" ref={ref}><span>{t}</span><i className="caret"/><div className="type-f">↻ Drop another file</div></div>;
}

function Hub() {
  const n = ["Your screen", "Course PDFs", "Your voice", "The board", "History", "Revision sheets"];
  return <div className="hub">
    <svg className="hub-l" viewBox="0 0 300 200" preserveAspectRatio="none" aria-hidden="true">
      {[[60, 40], [60, 100], [60, 160], [240, 40], [240, 100], [240, 160]].map(([x, y], i) =>
        <path key={i} d={`M150 100 C ${(150 + x) / 2} 100, ${(150 + x) / 2} ${y}, ${x} ${y}`} className="hub-p" style={{animationDelay: `${i * .35}s`}}/>)}
    </svg>
    <span className="hub-c"><Orb size={34}/></span>
    {n.map((x, i) => <span key={x} className={`hub-n n${i}`}>{x}</span>)}
  </div>;
}

function Running() {
  const items = ["Reading exercise 1", "Finding a, b and c", "Waiting for your attempt", "Underlining b² and 4ac", "Writing today's revision sheet"];
  const [ref, on] = useInView<HTMLDivElement>();
  const [k, setK] = useState(0);
  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => setK(v => (v + 1) % (items.length + 2)), 900);
    return () => clearInterval(id);
  }, [on]);
  return <div className="run" ref={ref}>
    <div className="run-h"><span className="dots" aria-hidden="true"><i/><i/><i/><i/><i/><i/></span>Gerald is with you</div>
    {items.map((x, i) => <div key={x} className={`run-i${i < k ? " done" : ""}`}>
      <span className="run-s">{i < k ? <Check/> : <i className="spin"/>}</span>{x}
    </div>)}
  </div>;
}

function How() {
  return <section className="sec" id="how">
    <Head badge="How it works" icon="⌘" title={<>From homework to<br/>“got it”, in 3 steps.</>} sub="Drop your course, ask out loud, and work it out together at the board."/>
    <div className="steps">
      <div className="step rv"><div className="tex"><Typing lines={["TD 4 — Second-degree polynomials.pdf", "Chapter 3 — Kinematics.pdf", "Lecture notes — Recursion.pdf"]}/></div>
        <h3>Drop your courses</h3><p>Your name, your subjects, your PDFs. No account, no setup.</p></div>
      <div className="step rv"><div className="tex"><Hub/></div>
        <h3>Ask out loud</h3><p>Hold Ctrl + Shift from any app. Gerald sees what you see and knows your course.</p></div>
      <div className="step rv"><div className="tex"><Running/></div>
        <h3>Practise, then review</h3><p>You write, Gerald nudges. Each session ends with a revision sheet.</p></div>
    </div>
  </section>;
}

const FEATURES = [
  {t: "Sees your screen", h: "Points at what matters", p: "Gerald reads the exercise you have open and underlines the part you should look at — on top of any app."},
  {t: "Explains at the board", h: "A blank board, on demand", p: "When a drawing helps, Gerald opens a board, writes the method in clean math and plots the curve only when it’s useful."},
  {t: "Lets you make mistakes", h: "Hints, not answers", p: "Gerald waits while you try. Stuck for about ten seconds? It nudges you with the next step instead of the solution."},
  {t: "Revision sheets", h: "Keep what you learned", p: "End the session and get a one-page sheet with the method, your mistakes and the key formula, filed under Fiches."},
];

function FeatureVisual({i}: {i: number}) {
  if (i === 0) return <div className="fv"><div className="fv-doc"><span>Exercise 2</span><b>2x² + 3x − 2 = 0</b><em className="fv-u"/></div><span className="cursor"><Orb size={16}/> Gerald</span></div>;
  if (i === 1) return <div className="fv"><div className="fv-board"><svg viewBox="0 0 220 120" aria-hidden="true"><path d="M10 110 H210 M110 8 V116" stroke="#c9cfdb" strokeWidth="1"/><path className="para" d="M30 20 Q110 190 190 20" fill="none" stroke="#3d2bff" strokeWidth="2.2"/><circle cx="88" cy="74" r="3.5" fill="#3d2bff"/><circle cx="132" cy="74" r="3.5" fill="#3d2bff"/></svg><span>y = x² − 5x + 6</span></div></div>;
  if (i === 2) return <div className="fv"><div className="fv-hint"><div className="hint-a">Δ = 25 + 24 <s>= 49</s></div><div className="hint-b"><Orb size={16}/> Careful with the sign of 4ac.</div><div className="hint-t"><i/></div></div></div>;
  return <div className="fv"><div className="fv-sheet"><b>Fiche · 25 Oct</b><span>Δ = b² − 4ac</span><span>Δ &gt; 0 → two roots</span><span>Watch out: sign of c</span></div></div>;
}

function Features() {
  const [a, setA] = useState(0);
  const [hold, setHold] = useState(false);
  useEffect(() => {
    if (hold) return;
    const id = setInterval(() => setA(v => (v + 1) % FEATURES.length), 4200);
    return () => clearInterval(id);
  }, [hold]);
  const f = FEATURES[a];
  return <section className="sec" id="features">
    <Head left badge="Features" icon="▦" title={<>Powerful tutor.<br/>Simple to use.</>} sub="It sees, explains, waits and remembers, so you actually learn the method."/>
    <div className="feat">
      <div className="tabs" onMouseEnter={() => setHold(true)} onMouseLeave={() => setHold(false)}>
        {FEATURES.map((x, i) => <button key={x.t} className={`tab${i === a ? " on" : ""}`} onClick={() => setA(i)}>
          <span className="num">0{i + 1}</span>{x.t}{i === a && !hold && <i className="prog"/>}
        </button>)}
      </div>
      <div className="panel" key={a}>
        <div className="panel-t"><h3>{f.h}</h3><p>{f.p}</p></div>
        <div className="panel-v tex"><FeatureVisual i={a}/></div>
      </div>
    </div>
  </section>;
}

function DotStack() {
  return <svg className="dotstack" viewBox="0 0 120 90" aria-hidden="true">
    {[0, 1, 2].map(l => Array.from({length: 13}, (_, c) => Array.from({length: 5}, (_, r) => {
      const x = 12 + c * 8, y = 14 + l * 24 + r * 3 + Math.abs(c - 6) * -1.6 + 10;
      return <circle key={`${l}${c}${r}`} cx={x} cy={y} r="1.6" style={{animationDelay: `${(l * 13 + c) * 25}ms`}}/>;
    })))}
  </svg>;
}

function Capabilities() {
  const fmts = ["PDF", "Slides", "Handwriting", "Screenshots", "LaTeX", "Graphs", "Voice", "Exercises"];
  return <section className="sec" id="capabilities">
    <Head badge="Capabilities" icon="⚓" title={<>Built for real<br/>coursework.</>} sub="Advanced reasoning for understanding your course, your attempt and what to explain next."/>
    <div className="bento">
      <div className="cell"><div className="cell-v"><div className="mq"><div className="mq-t">{[...fmts, ...fmts].map((x, i) => <span key={i} className="pill">{x}</span>)}</div></div><div className="mq r"><div className="mq-t">{[...fmts].reverse().concat([...fmts].reverse()).map((x, i) => <span key={i} className="pill">{x}</span>)}</div></div></div>
        <h3>Understands every format</h3><p>Course PDFs, slides, screenshots and your handwriting in one shared context.</p></div>
      <div className="cell wide"><div className="cell-v glow"><DotStack/></div>
        <h3>Remembers your courses</h3><p>Your subjects, chapters and past sessions, so every explanation starts from where you are.</p></div>
      <div className="cell wide"><div className="cell-v"><div className="ladder">{["Method", "Hint", "Next step", "Your answer"].map((x, i) => <span key={x} style={{animationDelay: `${i * .5}s`}}>{x}</span>)}</div></div>
        <h3>Guides, never just solves</h3><p>Method first, then hints that get more precise only if you need them.</p></div>
      <div className="cell"><div className="cell-v"><div className="states">{["Listening", "Thinking", "Speaking"].map((x, i) => <span key={x} className={`st s${i}`}><Orb size={14}/>{x}</span>)}</div></div>
        <h3>Real-time voice</h3><p>Talk naturally and interrupt anytime. It answers out loud while it draws.</p></div>
    </div>
  </section>;
}

function Facts() {
  const f = [["10 s", "Gerald waits before nudging"], ["1 hotkey", "Ctrl + Shift, from any app"], ["0 accounts", "Just your name and subjects"], ["1 sheet", "Revision sheet per session"]];
  return <section className="sec facts">
    <div className="facts-l">
      <Badge icon="∿">By design</Badge>
      <h2 className="rv">What learning with<br/>Gerald feels like</h2>
      <p className="rv">Patient, out loud, on your own exercises. You do the thinking; Gerald keeps you moving.</p>
      <div className="fact-g">{f.map(([n, l]) => <div key={n} className="fact rv"><b>{n}</b><span>{l}</span></div>)}</div>
    </div>
    <svg className="curve" viewBox="0 0 600 400" preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id="cf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6d8bff" stopOpacity=".28"/><stop offset="1" stopColor="#6d8bff" stopOpacity="0"/></linearGradient>
        <pattern id="vl" width="9" height="400" patternUnits="userSpaceOnUse"><path d="M0 0V400" stroke="#6d8bff" strokeOpacity=".25"/></pattern></defs>
      <path d="M0 400 C 240 390, 420 300, 600 40 L600 400Z" fill="url(#cf)"/>
      <path d="M0 400 C 240 390, 420 300, 600 40 L600 400Z" fill="url(#vl)"/>
      <path className="curve-l" d="M0 400 C 240 390, 420 300, 600 40" fill="none" stroke="#4f6bff" strokeWidth="3"/>
    </svg>
  </section>;
}

const PIX: Record<string, string[]> = {
  math: ["..XXXXX..", ".X.....X.", "....XXX..", "...X.....", "..X......", ".XXXXXXX.", ".........", "...X.X...", "....X...."],
  phys: ["....X....", "..XXXXX..", ".X..X..X.", "X..XXX..X", "XXXX.XXXX", "X..XXX..X", ".X..X..X.", "..XXXXX..", "....X...."],
  chem: ["..XXXXX..", "...X.X...", "...X.X...", "..X...X..", ".X.....X.", "X.XXXXX.X", "X.XXXXX.X", "X.......X", ".XXXXXXX."],
  cs: ["XXXXXXXXX", "X.......X", "X.X.....X", "X..X....X", "X.X..XX.X", "X.......X", "XXXXXXXXX", "...XXX...", ".XXXXXXX."],
  eco: [".......XX", "......X.X", "X....X...", "X...X....", "X..X.....", "X.X...X..", "XX...XXX.", "X...XXXXX", "XXXXXXXXX"],
  lang: [".XXXXXXX.", "X.......X", "X.XX.XX.X", "X.......X", "X.XXXX..X", "X.......X", ".XXXX.XX.", ".....X...", "....X...."],
};
function Pix({k}: {k: string}) {
  return <svg className="pix" viewBox="0 0 9 9" aria-hidden="true">
    <defs><linearGradient id={`g${k}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4ea8ff"/><stop offset="1" stopColor="#3d2bff"/></linearGradient></defs>
    {PIX[k].flatMap((row, y) => [...row].map((c, x) => c === "X" ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={`url(#g${k})`}/> : null))}
  </svg>;
}

function Subjectsdark() {
  const s = [["math", "Mathematics", "Polynomials, functions, sequences — explained step by step at the board."],
    ["phys", "Physics", "Forces, kinematics and circuits, with the diagram drawn while you talk."],
    ["chem", "Chemistry", "Balancing equations and moles, one coefficient at a time."],
    ["cs", "Computer science", "Algorithms and recursion traced line by line on your screen."],
    ["eco", "Economics", "Curves, elasticities and graphs plotted only when they help."],
    ["lang", "Any course you drop", "If it’s in your PDFs, Gerald can work through it with you."]];
  return <section className="dark">
    <Head badge="Subjects" icon="◇" title={<>Built for the way<br/>every subject works.</>} sub="The same tutor, adapted to your courses, exercises and level."/>
    <div className="subj">{s.map(([k, t, p]) => <div key={k} className="subj-i rv"><Pix k={k}/><h3>{t}</h3><p>{p}</p></div>)}</div>
  </section>;
}

function Privacy() {
  const p = [["No account", "Your name and subjects. That’s it."], ["Push-to-talk", "The mic only listens while you hold Ctrl + Shift."], ["You’re in control", "Press Esc to stop Gerald at any time."], ["Keys stay server-side", "No API key ever ships to your browser."]];
  return <section className="dark priv">
    <Head badge="Privacy" icon="◎" title={<>Calm, private,<br/>and on your terms.</>} sub="A tutor that only speaks when you ask, and only sees what you show it."/>
    <div className="lock rv" aria-hidden="true"><svg viewBox="0 0 24 24">{Array.from({length: 24 * 24}, (_, i) => {
      const x = i % 24, y = Math.floor(i / 24);
      const body = y >= 11 && y <= 21 && x >= 4 && x <= 19 && !(x >= 11 && x <= 12 && y >= 14 && y <= 18);
      const r = Math.hypot(x - 11.5, y - 10.5), arc = y <= 11 && r >= 5 && r <= 7;
      return body || arc ? <circle key={i} cx={x + .5} cy={y + .5} r=".32"/> : null;
    })}</svg></div>
    <div className="priv-g">{p.map(([t, d]) => <div key={t} className="rv"><h3>{t}</h3><p>{d}</p></div>)}</div>
  </section>;
}

const FAQ = [
  ["Is Gerald a chatbot?", "No. Gerald is a voice tutor that lives on your screen: you talk, it points, underlines and explains at a board. There is no chat window to type into."],
  ["Will it just give me the answer?", "No. It explains the method first, lets you try, and only gives hints when you’re stuck. You get the full solution once you’ve made a real attempt."],
  ["Which subjects does it cover?", "Maths, physics, chemistry, computer science and more. Gerald works from the course documents you drop in, so it follows your teacher’s notation."],
  ["Do I need an account?", "No. On first launch you enter your name, optionally your level, then your subjects."],
  ["How do I talk to it?", "Hold Ctrl + Shift from any app, ask your question, and release. Gerald answers out loud and can draw on your screen."],
  ["What’s the difference between Demo and Live?", "The demo walks you through a sample exercise. Live starts a real voice session with Gerald on your own question."],
];
function Faq() {
  const [o, setO] = useState(0);
  return <section className="sec" id="faq">
    <Head badge="FAQs" icon="△" title={<>Questions about<br/>Gerald, answered.</>} sub="How it teaches, what it sees, and how to get started."/>
    <div className="faq">{FAQ.map(([q, a], i) => <div key={q} className={`qa rv${o === i ? " open" : ""}`}>
      <button onClick={() => setO(o === i ? -1 : i)} aria-expanded={o === i}><span>{q}</span><i className="pm"/></button>
      <div className="ans"><p>{a}</p></div>
    </div>)}</div>
  </section>;
}

function Final() {
  return <section className="final">
    <div className="final-in tex">
      <h2 className="rv">You’ve seen how Gerald works.<br/>Now open your homework.</h2>
      <p className="rv">Pick an exercise, hold Ctrl + Shift, and work it out together.</p>
      <div className="cta rv"><a className="btn ghost light" href={DEMO_HREF}>Try the demo</a><a className="btn primary" href={LIVE_HREF}>Learn live <Arrow/></a></div>
    </div>
  </section>;
}

function Footer() {
  return <footer className="foot">
    <div><a className="brand" href="#top"><span className="brand-mark"><GeraldMark size={12}/></span>Gerald</a><p>The tutor that explains it at your board.</p></div>
    <div className="foot-l"><b>Product</b><a href="#how">How it works</a><a href="#features">Features</a><a href="#capabilities">Capabilities</a><a href="#faq">FAQ</a></div>
    <small>© 2026 Gerald. All rights reserved.</small>
  </footer>;
}

function Landing() {
  useReveal();
  return <>
    <Nav/>
    <main>
      <Hero/><Subjects/><How/><Features/><Capabilities/><Facts/><Subjectsdark/><Privacy/><Faq/><Final/>
    </main>
    <Footer/>
  </>;
}

createRoot(document.getElementById("root")!).render(<Landing/>);
