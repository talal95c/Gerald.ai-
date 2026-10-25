import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, staticFile, useVideoConfig } from "remotion";
import { Cap, Card, Counter, D, Em, Eyebrow, H2, Kbd, LABEL, Mark, Notch, R, SANS, Slide, useR } from "./deck";

export const Cover: React.FC = () => (
  <Slide>
    <Notch text="Gerald is listening…" />
    <Eyebrow at={0.2}>Pitch · Hackathon 2026</Eyebrow>
    <R at={0.4}><div style={{ display: "flex", alignItems: "center", gap: 40 }}><Mark size={150} /><div style={{ fontSize: 300, lineHeight: 0.9, letterSpacing: "-.07em", fontWeight: 500 }}>Gerald.</div></div></R>
    <R at={0.9} style={{ fontSize: 46, lineHeight: 1.18, letterSpacing: "-.035em", marginTop: 40, maxWidth: 1300 }}>The private tutor that lives on your screen. It sees, it talks, it draws. <Em>It doesn't give you the answer: it helps you find it.</Em></R>
    <R at={1.4} style={{ marginTop: 70, display: "flex", alignItems: "center", gap: 14, fontSize: 26 }}><Kbd>Ctrl</Kbd> + <Kbd>Shift</Kbd><small style={{ marginLeft: 16, font: `22px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted }}>hold to talk</small></R>
  </Slide>
);

export const Problem: React.FC = () => (
  <Slide>
    <Eyebrow>The problem</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>Learning alone in front of a screen means learning with <Em>nobody next to you.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 28 }}>
      <Card at={1.2} num="01" title="AI gives the answer">Chatbots solve the exercise for you. You copy it, you don't understand it.</Card>
      <Card at={2.8} num="02" title="It can't see your screen">Screenshots, copy-paste, re-explaining context on every question. The learning flow breaks.</Card>
      <Card at={4.6} num="03" title="A real tutor is rare">A tutor points, draws, makes you think. But not at 11 pm, and not for everyone.</Card>
    </div>
    <R at={6.4} style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 40, padding: "30px 40px", borderRadius: 28, background: D.dark, color: D.paper }}>
      <Counter from={495} to={474} at={6.6} style={{ fontSize: 110, fontWeight: 500, letterSpacing: "-.06em", color: D.yellow }} />
      <div style={{ fontSize: 28, lineHeight: 1.3, maxWidth: 1100 }}>Average maths score of French students in PISA 2022, −21 points vs 2018, a historic drop.<small style={{ display: "block", marginTop: 8, font: `18px ${LABEL}`, letterSpacing: ".05em", textTransform: "uppercase", color: "rgba(247,246,243,.5)" }}>Source: OECD, PISA 2022 results (Dec. 2023)</small></div>
    </R>
  </Slide>
);

export const Solution: React.FC = () => (
  <Slide>
    <Eyebrow>The solution</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>Hold a key. Speak. Gerald looks at your screen and explains, <Em>like a tutor sitting right next to you.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 24 }}>
      <Card at={2.0} icon title="It sees">One screenshot, only while you hold the shortcut.</Card>
      <Card at={3.4} icon title="It talks">Natural real-time voice, short sentences, in your language.</Card>
      <Card at={4.8} icon title="It draws">Circles, points, plots an exact curve on your board.</Card>
      <Card at={6.2} icon title="It guides">One step at a time, then “your turn”. It only acts if you allow it.</Card>
    </div>
    <R at={7.4} style={{ marginTop: "auto", font: `22px ${LABEL}`, letterSpacing: ".04em", textTransform: "uppercase", color: D.muted }}>Any app · Windows first · open source (MIT)</R>
  </Slide>
);

export const DemoIntro: React.FC = () => (
  <Slide>
    <Eyebrow>Demo · live recordings</Eyebrow>
    <H2 size={110}>Two features,<br />recorded live.</H2>
    <div style={{ display: "flex", gap: 24 }}>
      <Card at={0.8} num="01" title="Maths at the board">x² − 5x + 6 = 0 · the parabola, plotted by Gerald</Card>
      <Card at={1.6} num="02" title="Any app · Photoshop">“I need a red square” · guided step by step</Card>
    </div>
  </Slide>
);

const Clip: React.FC<{ src: string; trim?: number }> = ({ src, trim = 0 }) => {
  const { fps } = useVideoConfig();
  const p = useR(0, 0.8);
  return (
    <div style={{ position: "absolute", left: "50%", top: 150, translate: "-50% 0", width: 1360, height: 850, borderRadius: 28, overflow: "hidden", background: "#fff", border: `1px solid ${D.line}`, boxShadow: "0 30px 80px rgba(0,0,0,.12)", opacity: p, scale: `${0.97 + 0.03 * p}` }}>
      <Video src={staticFile(`footage/${src}`)} trimBefore={Math.round(trim * fps)} muted objectFit="contain" style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export const DemoMath: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <AbsoluteFill style={{ padding: "50px 150px 0" }}><Eyebrow>Demo 01 · Quadratic equations</Eyebrow></AbsoluteFill>
    <Clip src="clip2.mp4" />
    <Cap at={0.6} out={6.5}>The student opens exercise 1 and asks for help</Cap>
    <Cap at={7} out={14}>Gerald doesn't solve it — it opens the board and plots the exact parabola</Cap>
    <Cap at={14.5}>“Compute Δ and find the two roots. Your turn.”</Cap>
  </Slide>
);

export const DemoPs: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <AbsoluteFill style={{ padding: "50px 150px 0" }}><Eyebrow>Demo 02 · Any app — Photoshop</Eyebrow></AbsoluteFill>
    <Clip src="clip3.mp4" trim={2} />
    <Cap at={0.6} out={5}>“I need a red square”</Cap>
    <Cap at={5.5} out={13}>Gerald points at the Shapes panel, then the rectangle</Cap>
    <Cap at={13.5} out={25}>It guides to the fill colour: hex #ff0000</Cap>
    <Cap at={25.5}>The student drags the square — Gerald points, you click</Cap>
  </Slide>
);

const NODES = [
  ["01 · Trigger", "Push-to-talk", "24 kHz PCM mic + one capture of the screen under the cursor"],
  ["02 · Perception", "UIA · OCR · Moondream", "Visible elements with provenance, to anchor every gesture"],
  ["03 · Brain", "gpt-realtime-2", "Voice + image over a single WebSocket, context kept for the whole session"],
  ["04 · Tools", "point · circle · plot · diagram", "Validated function calls, turned into drawing commands"],
  ["05 · Render", "Overlay + board", "Transparent, click-through window, excluded from captures"],
];
export const Hood: React.FC = () => (
  <Slide>
    <Eyebrow>Under the hood</Eyebrow>
    <H2 size={72}>One voice turn, <Em>from keypress to ink.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 18 }}>
      {NODES.map(([k, t, d], i) => (
        <R key={k} at={1.2 + i * 1.6}>
          <div style={{ background: i === 2 ? D.dark : "#fff", color: i === 2 ? D.paper : D.ink, border: `1px solid ${D.line}`, borderRadius: 26, padding: 30, minHeight: 300 }}>
            <small style={{ font: `18px ${LABEL}`, letterSpacing: ".06em", textTransform: "uppercase", color: i === 2 ? "rgba(247,246,243,.6)" : D.muted }}>{k}</small>
            <div style={{ fontSize: 30, margin: "44px 0 14px", fontWeight: 500, letterSpacing: "-.03em", color: i === 2 ? D.yellow : D.ink }}>{t}</div>
            <p style={{ margin: 0, fontSize: 21, lineHeight: 1.35, color: i === 2 ? "rgba(247,246,243,.6)" : "#5e5e5b" }}>{d}</p>
          </div>
        </R>
      ))}
    </div>
    <R at={9.5} style={{ marginTop: 48, display: "flex", flexWrap: "wrap", gap: 12 }}>
      {["Python 3.11", "PyQt6", "asyncio", "OpenAI Realtime", "React · QWebEngine", "KaTeX", "Local RAG (embeddings)"].map((x) => <span key={x} style={{ padding: "12px 20px", borderRadius: 999, border: `1px solid ${D.line}`, background: "#fff", fontSize: 20 }}>{x}</span>)}
    </R>
  </Slide>
);

export const Harness: React.FC = () => (
  <Slide>
    <Eyebrow>Engineering · The pedagogy harness</Eyebrow>
    <H2 size={72}>We don't guess whether Gerald teaches well. <Em>We measure it.</Em></H2>
    <div style={{ display: "flex", alignItems: "center", gap: 26 }}>
      {[["17", "rendered scenarios (code, maths, diagrams, worksheets)"], ["Realtime", "real gpt-realtime-2 turns, actions recorded"], ["Judge", "gpt-5.5 · 8-criterion rubric + deterministic checks"]].map(([b, s], i) => (
        <React.Fragment key={b}>
          <R at={1.5 + i * 1.3} style={{ flex: 1 }}><div style={{ padding: "24px 30px", borderRadius: 24, background: "#fff", border: `1px solid ${D.line}`, display: "flex", gap: 22, alignItems: "center" }}><b style={{ fontSize: 44, fontWeight: 500, letterSpacing: "-.04em" }}>{b}</b><span style={{ fontSize: 20, lineHeight: 1.3, color: "#5e5e5b" }}>{s}</span></div></R>
          {i < 2 && <R at={1.5 + i * 1.3}><span style={{ fontSize: 32, color: D.muted }}>→</span></R>}
        </React.Fragment>
      ))}
    </div>
    <R at={6} style={{ marginTop: 50, display: "flex", alignItems: "center", gap: 50 }}>
      <div><small style={{ display: "block", font: `20px ${LABEL}`, letterSpacing: ".06em", textTransform: "uppercase", color: D.muted }}>Baseline prompt</small><strong style={{ fontSize: 150, fontWeight: 500, letterSpacing: "-.07em", lineHeight: 1, color: "#bdbdb8" }}>77 %</strong></div>
      <span style={{ fontSize: 80, color: D.muted }}>→</span>
      <div><small style={{ display: "block", font: `20px ${LABEL}`, letterSpacing: ".06em", textTransform: "uppercase", color: D.muted }}>Tutor-first + cursor + diagrams</small><strong style={{ fontSize: 150, fontWeight: 500, letterSpacing: "-.07em", lineHeight: 1, background: `linear-gradient(transparent 62%, ${D.yellow2} 62%)` }}><Counter from={77} to={92} at={6.6} dur={1.8} /> %</strong></div>
    </R>
  </Slide>
);

export const Pointing: React.FC = () => (
  <Slide>
    <Eyebrow>Engineering · Pointing right</Eyebrow>
    <H2 size={72}>The model sees well. It aims badly. <Em>So we anchor every gesture.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 24 }}>
      {[["~90 px", "raw pointing error of gpt-realtime-2 (mini: ~210 px)", D.red], ["8/10", "web targets hit with Moondream grounding", D.ink], ["0.6 s", "per located point (vs 55 s on local CPU)", D.ink], ["$0.0002", "per point · $5 free/month ≈ 20,000 points", D.ink]].map(([n, t, c], i) => (
        <R key={n} at={1.5 + i * 1.4}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 28, padding: 38, minHeight: 280 }}><strong style={{ display: "block", fontSize: 84, fontWeight: 500, letterSpacing: "-.06em", lineHeight: 1, marginBottom: 20, color: c }}>{n}</strong><p style={{ margin: 0, fontSize: 24, lineHeight: 1.35, color: "#5e5e5b" }}>{t}</p></div></R>
      ))}
    </div>
    <R at={8} style={{ marginTop: 44, fontSize: 28, color: D.muted }}>Trust order: UIA element → OCR word → visual grounder → <span style={{ color: D.ink }}>never the model's raw coordinate.</span></R>
  </Slide>
);

export const Trust: React.FC = () => (
  <Slide>
    <Eyebrow>Trust & privacy</Eyebrow>
    <H2 size={72}>A tutor on your screen, <Em>not a spy.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
      {[["Vision on demand", "No continuous capture: the screen is only read while you hold the shortcut."], ["Real consent", "Before any action, an “Allow / Cancel” prompt. The model can't approve itself."], ["Guardrails", "Max 8 actions per turn, Esc stops everything, moving the mouse 40 px takes back control."], ["Local first", "Your courses are indexed on your machine; proactive mode only reads the window title."]].map(([b, t], i) => (
        <R key={b} at={1.2 + i * 1.2}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 26, padding: "34px 38px", fontSize: 25, lineHeight: 1.4, color: "#5e5e5b" }}><b style={{ display: "block", fontSize: 34, fontWeight: 500, letterSpacing: "-.03em", color: D.ink, marginBottom: 12 }}>{b}</b>{t}</div></R>
      ))}
    </div>
  </Slide>
);

export const Next: React.FC = () => (
  <Slide>
    <Eyebrow>What's next</Eyebrow>
    <H2 size={72}>From one maths worksheet <Em>to every subject.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 24 }}>
      {[["Today", "Hackathon", "Windows, board, quadratics worksheet, harness, local RAG."], ["Next", "Student memory", "Revision sheets, recurring mistakes, a level that adapts."], ["Then", "macOS · iPad", "Same engine, native overlay, pen first."], ["Vision", "Schools", "Teachers load their worksheets, Gerald supports every student."]].map(([k, t, d], i) => (
        <Card key={k} at={1 + i * 1.8} num={k} title={t} dark={i === 3}>{d}</Card>
      ))}
    </div>
  </Slide>
);

export const Thanks: React.FC = () => (
  <Slide>
    <Eyebrow>Thank you</Eyebrow>
    <R at={0.3}><div style={{ display: "flex", alignItems: "center", gap: 40 }}><Mark size={150} /><div style={{ fontSize: 300, lineHeight: 0.9, letterSpacing: "-.07em", fontWeight: 500 }}>Gerald.</div></div></R>
    <R at={0.9} style={{ fontSize: 46, letterSpacing: "-.035em", marginTop: 40 }}>Doesn't give you the answer. <Em>Helps you find it.</Em></R>
    <R at={1.6} style={{ marginTop: "auto", font: `22px ${LABEL}`, letterSpacing: ".04em", textTransform: "uppercase", color: D.muted }}>github.com/talal95c/Gerald.ai- · open source · MIT</R>
  </Slide>
);
export const _ = SANS;
