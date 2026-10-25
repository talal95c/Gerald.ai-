import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import katex from "katex";
import "katex/dist/katex.min.css";
import "./board.css";

type Pt = {x: number; y: number; p: number};
type Stroke = {pts: Pt[]; erase: boolean};
type Win = {x: number; y: number; w: number; h: number};

const params = new URLSearchParams(location.search);
const title = params.get("title") || "Exercice 1";
const lines: string[] = (() => { try { const l = JSON.parse(params.get("lines") || "[]"); return l.length ? l : ["Résous dans ℝ : x² − 5x + 6 = 0"]; } catch { return ["Résous dans ℝ : x² − 5x + 6 = 0"]; } })();
const f = (x: number) => x * x - 5 * x + 6;
const X0 = -1, X1 = 6, Y0 = -2, Y1 = 12;

function Plot({w, h}: {w: number; h: number}) {
  const pad = {l: 36, r: 14, t: 14, b: 26};
  const gw = w - pad.l - pad.r, gh = h - pad.t - pad.b;
  const sx = (x: number) => pad.l + (x - X0) / (X1 - X0) * gw;
  const sy = (y: number) => pad.t + (Y1 - y) / (Y1 - Y0) * gh;
  const d = Array.from({length: 141}, (_, i) => X0 + i * (X1 - X0) / 140).map((x, i) => `${i ? "L" : "M"}${sx(x).toFixed(1)},${sy(f(x)).toFixed(1)}`).join("");
  const xs = Array.from({length: X1 - X0 + 1}, (_, i) => X0 + i);
  const ys = Array.from({length: (Y1 - Y0) / 2 + 1}, (_, i) => Y0 + i * 2);
  const pts = [{x: 2, y: 0, l: "x = 2"}, {x: 3, y: 0, l: "x = 3"}, {x: 2.5, y: -0.25, l: "S(2,5 ; −0,25)"}];
  return <svg width={w} height={h} className="plot-svg">
    <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 8 4 0 8z" fill="#262626"/></marker><clipPath id="graph"><rect x={pad.l} y={pad.t} width={gw} height={gh}/></clipPath></defs>
    {xs.map(x => <line key={`x${x}`} x1={sx(x)} x2={sx(x)} y1={pad.t} y2={pad.t + gh} className="grid"/>)}
    {ys.map(y => <line key={`y${y}`} y1={sy(y)} y2={sy(y)} x1={pad.l} x2={pad.l + gw} className="grid"/>)}
    <line x1={pad.l} x2={pad.l + gw} y1={sy(0)} y2={sy(0)} className="axis" markerEnd="url(#arr)"/>
    <line x1={sx(0)} x2={sx(0)} y1={pad.t + gh} y2={pad.t} className="axis" markerEnd="url(#arr)"/>
    {xs.filter(x => x !== 0).map(x => <text key={`tx${x}`} x={sx(x)} y={sy(0) + 15} className="tick" textAnchor="middle">{x}</text>)}
    {ys.filter(y => y !== 0).map(y => <text key={`ty${y}`} x={sx(0) - 6} y={sy(y) + 4} className="tick" textAnchor="end">{y}</text>)}
    <path d={d} className="curve" clipPath="url(#graph)" pathLength={1}/>
    {pts.map((p, i) => <g key={p.l} className="pt" style={{animationDelay: `${0.9 + i * 0.12}s`}}><circle cx={sx(p.x)} cy={sy(p.y)} r="5"/>
      <text x={sx(p.x) + (i === 0 ? -8 : 8)} y={sy(p.y) + (i === 2 ? 20 : -10)} textAnchor={i === 0 ? "end" : "start"} className="pt-label">{p.l}</text></g>)}
  </svg>;
}

function PlotWindow({onClose}: {onClose: () => void}) {
  const [win, setWin] = useState<Win>(() => ({x: Math.max(24, innerWidth / 2 - 260), y: 140, w: 520, h: 360}));
  const drag = (kind: "move" | "resize") => (e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    const start = {px: e.clientX, py: e.clientY, ...win};
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - start.px, dy = ev.clientY - start.py;
      setWin(kind === "move"
        ? {...start, x: Math.min(Math.max(0, start.x + dx), innerWidth - start.w), y: Math.min(Math.max(0, start.y + dy), innerHeight - start.h)}
        : {...start, w: Math.min(Math.max(260, start.w + dx), innerWidth - start.x), h: Math.min(Math.max(180, start.h + dy), innerHeight - start.y)});
    };
    const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
    addEventListener("pointermove", move); addEventListener("pointerup", up);
  };
  return <section className="plot-win" style={{left: win.x, top: win.y, width: win.w, height: win.h}} onPointerDown={e => e.stopPropagation()}>
    <header onPointerDown={drag("move")}><span className="dot" /><span>f(x) = x² − 5x + 6</span><button onPointerDown={e => e.stopPropagation()} onClick={onClose} aria-label="Fermer la courbe">×</button></header>
    <Plot w={win.w} h={win.h - 30}/>
    <div className="grip" onPointerDown={drag("resize")}><i/><i/><i/></div>
  </section>;
}

const tools = [
  {id: "pen", label: "Stylo", d: "M4 16l1-4L13.5 3.5a1.4 1.4 0 0 1 2 0l1 1a1.4 1.4 0 0 1 0 2L8 15z"},
  {id: "eraser", label: "Gomme", d: "M7.5 16h9M3.8 11.7l6.9-6.9a1.5 1.5 0 0 1 2.1 0l2.4 2.4a1.5 1.5 0 0 1 0 2.1L9.3 15.2a1.5 1.5 0 0 1-2.1 0z"},
  {id: "undo", label: "Annuler", d: "M7 5 3.5 8.5 7 12M4 8.5h7.5a4.5 4.5 0 0 1 0 9H9"},
  {id: "clear", label: "Effacer", d: "M4 6h12M8 6V4h4v2M6 6l.8 10h6.4L14 6"},
  {id: "plot", label: "Courbe", d: "M3 3v14h14M5.5 6c2 9 4 9 5.5 5s3-5 5.5-1"},
];

function Board() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const strokes = useRef<Stroke[]>([]);
  const [tool, setTool] = useState("pen");
  const [plot, setPlot] = useState(true);
  const [, tick] = useState(0);
  const redraw = () => {
    const c = canvas.current!; const ctx = c.getContext("2d")!; const r = devicePixelRatio;
    ctx.setTransform(r, 0, 0, r, 0, 0); ctx.clearRect(0, 0, c.width, c.height);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    for (const s of strokes.current) {
      ctx.globalCompositeOperation = s.erase ? "destination-out" : "source-over";
      ctx.strokeStyle = "#262626";
      for (let i = 1; i < s.pts.length; i++) {
        const a = s.pts[i - 1], b = s.pts[i];
        ctx.lineWidth = s.erase ? 26 : 1.4 + 2.6 * b.p;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
    ctx.globalCompositeOperation = "source-over";
  };
  useEffect(() => {
    const fit = () => { const c = canvas.current!; c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio; redraw(); };
    fit(); addEventListener("resize", fit); return () => removeEventListener("resize", fit);
  }, []);
  const down = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (e.button > 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    strokes.current.push({pts: [{x: e.clientX, y: e.clientY, p: e.pressure || .5}], erase: tool === "eraser"});
  };
  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
    const s = strokes.current[strokes.current.length - 1];
    for (const ev of e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent]) s.pts.push({x: ev.clientX, y: ev.clientY, p: ev.pressure || .5});
    redraw();
  };
  const act = (id: string) => {
    if (id === "undo") { strokes.current.pop(); redraw(); }
    else if (id === "clear") { strokes.current = []; redraw(); }
    else if (id === "plot") setPlot(p => !p);
    else setTool(id);
    tick(n => n + 1);
  };
  return <main className="board">
    <canvas ref={canvas} className={tool} onPointerDown={down} onPointerMove={move}/>
    <aside className="ex-card"><div className="ex-label"><i/>{title.toUpperCase()}</div>{lines.map((l, i) => <p key={i}>{l}</p>)}</aside>
    {plot && <PlotWindow onClose={() => setPlot(false)}/>}
    <nav className="board-tools">
      {tools.map(t => <button key={t.id} className={(t.id === tool || (t.id === "plot" && plot)) ? "on" : ""} onClick={() => act(t.id)} title={t.label} aria-label={t.label}>
        <svg viewBox="0 0 20 20"><path d={t.d}/></svg></button>)}
      <span className="sep"/>
      <button className="close" onClick={() => history.length > 1 ? history.back() : window.close()} aria-label="Fermer le tableau">Fermer</button>
    </nav>
  </main>;
}
void katex;
createRoot(document.getElementById("root")!).render(<Board/>);
