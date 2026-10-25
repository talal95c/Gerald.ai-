import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, staticFile, useVideoConfig } from "remotion";
import { Cap, Card, Counter, D, Em, Eyebrow, H2, Kbd, LABEL, Mark, Notch, R, SANS, Slide, useR } from "./deck";

const Foot: React.FC<{ children: React.ReactNode; at?: number }> = ({ children, at = 1 }) => (
  <R at={at} style={{ marginTop: "auto", font: `22px ${LABEL}`, letterSpacing: ".04em", textTransform: "uppercase", color: D.muted }}>{children}</R>
);

export const Cover: React.FC = () => (
  <Slide>
    <Notch text="Gerald is listening…" />
    <Eyebrow at={0.2}>AI teacher · Hackathon 2026</Eyebrow>
    <R at={0.4}><div style={{ display: "flex", alignItems: "center", gap: 40 }}><Mark size={130} /><div style={{ fontSize: 150, lineHeight: 0.95, letterSpacing: "-.06em", fontWeight: 500 }}>Meet Gerald.<br /><Em>The AI teacher that lives on your screen.</Em></div></div></R>
    <R at={1.2} style={{ fontSize: 40, lineHeight: 1.2, letterSpacing: "-.03em", marginTop: 50, maxWidth: 1400 }}>It sees, it talks, it draws. The most optimised way to learn anything on a computer: maths, sciences, any software. <Em>And you still find the answer.</Em></R>
    <R at={1.8} style={{ marginTop: 60, display: "flex", alignItems: "center", gap: 14, fontSize: 26 }}><Kbd>Ctrl</Kbd> + <Kbd>Shift</Kbd><small style={{ marginLeft: 16, font: `22px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted }}>hold to ask</small></R>
  </Slide>
);

const VOICES = [["My friends", "Just learn with AI."], ["My teachers", "You should learn with AI."], ["LinkedIn", "Learn with AI. Agree?"], ["Every YouTube ad", "Learn anything with AI!"], ["My mum", "Have you tried learning with AI?"]];
export const Story: React.FC = () => (
  <Slide>
    <Eyebrow>Context · The story</Eyebrow>
    <H2 size={84}>For years, everyone told me <Em>the same thing.</Em></H2>
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1200 }}>
      {VOICES.map(([who, q], i) => (
        <R key={who} at={1.2 + i * 1.1} style={{ alignSelf: i % 2 ? "flex-end" : "flex-start", display: "flex", alignItems: "baseline", gap: 18, padding: "18px 28px", borderRadius: 24, background: i % 2 ? D.dark : "#fff", color: i % 2 ? D.paper : D.ink, border: `1px solid ${D.line}` }}>
          <span style={{ font: `18px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: i % 2 ? "rgba(247,246,243,.55)" : D.muted }}>{who}</span><span style={{ fontSize: 30, letterSpacing: "-.02em" }}>{q}</span>
        </R>
      ))}
    </div>
  </Slide>
);

export const Notebook: React.FC = () => (
  <Slide>
    <Eyebrow>Context · So I tried. With maths.</Eyebrow>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 40, alignItems: "stretch" }}>
      <R at={0.3}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 28, padding: 40, height: 520, backgroundImage: "repeating-linear-gradient(transparent 0 46px, rgba(38,38,38,.08) 46px 47px)" }}>
        <small style={{ font: `18px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted }}>My notebook</small>
        <div style={{ marginTop: 30, font: `600 46px/1.5 Caveat, cursive`, color: "#1f2937" }}>x² − 5x + 6 = 0<br />Δ = b² − 4ac<br />Δ = 25 + 24 = 49 ?<br />x = (5 ± √Δ) / 2</div>
      </div></R>
      <R at={1.0}><div style={{ background: D.dark, color: D.paper, borderRadius: 28, padding: 40, height: 520, display: "flex", flexDirection: "column" }}>
        <small style={{ font: `18px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: "rgba(247,246,243,.55)" }}>Any AI chat</small>
        <div style={{ marginTop: 30, fontSize: 30, color: "rgba(247,246,243,.6)" }}>How can I help you today?</div>
        <R at={3.5} style={{ marginTop: "auto", padding: "16px 22px", borderRadius: 16, background: "#2a2a2a", fontSize: 26, fontFamily: "monospace" }}>x^2 - 5x + 6 = 0, delta = b^2 - 4ac = 25 + 24 …<span style={{ opacity: 0.6 }}>|</span></R>
      </div></R>
    </div>
    <R at={5.5} style={{ marginTop: 40, fontSize: 40, letterSpacing: "-.03em" }}>Before I can even ask my question, I have to <span style={{ background: `linear-gradient(transparent 58%, ${D.yellow2} 58%)` }}>retype my equations</span>. <Em>Every. Single. Time.</Em></R>
  </Slide>
);

export const Problem: React.FC = () => (
  <Slide>
    <Eyebrow>The problem</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>Learning is written, drawn, pointed at. <Em>AI tutors are stuck in a chat box.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 28 }}>
      <Card at={1.5} num="01" title="You retype everything">Equations, formulas, screenshots of the app you're lost in. The context dies before the first question.</Card>
      <Card at={4.5} num="02" title="It can't point">No finger, no pen. “The third icon on the left” is the best it can do.</Card>
      <Card at={7.5} num="03" title="It gives you the answer">You copy the solution. The next morning, you still can't solve it.</Card>
    </div>
    <R at={11} style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 40, padding: "30px 40px", borderRadius: 28, background: D.dark, color: D.paper }}>
      <Counter from={495} to={474} at={11.2} style={{ fontSize: 110, fontWeight: 500, letterSpacing: "-.06em", color: D.yellow }} />
      <div style={{ fontSize: 28, lineHeight: 1.3, maxWidth: 1100 }}>French students' average maths score in PISA 2022: −21 points vs 2018, a historic drop.<small style={{ display: "block", marginTop: 8, font: `18px ${LABEL}`, letterSpacing: ".05em", textTransform: "uppercase", color: "rgba(247,246,243,.5)" }}>Source: OECD, PISA 2022 results (Dec. 2023)</small></div>
    </R>
  </Slide>
);

export const Solution: React.FC = () => (
  <Slide>
    <Eyebrow>The solution</Eyebrow>
    <H2 size={84} style={{ marginBottom: 44 }}>So I built Gerald. <Em>Not a maths teacher. A teacher.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 24 }}>
      <Card at={3.5} icon title="Sees">your exercise, only while you hold the key.</Card>
      <Card at={5.5} icon title="Talks">in real time. Interrupt it whenever you want.</Card>
      <Card at={7.5} icon title="Draws">circles, underlines, arrows and exact plots.</Card>
      <Card at={9.5} icon title="Teaches">hint first, answer last: you do the thinking.</Card>
    </div>
    <Foot at={12}>Hold Ctrl + Shift and talk · it sees what you see · underlines your mistake · you fix it yourself</Foot>
  </Slide>
);

export const Different: React.FC = () => (
  <Slide>
    <Eyebrow>Why it's different</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>One teacher. Every subject. Every app. <Em>The most optimised way to learn. Period.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 28 }}>
      <Card at={2} num="Maths" title="Underlines the exact mistake">Reads your working, underlines the wrong term, plots the real curve. Hints first, answer last.</Card>
      <Card at={4.5} num="Sciences" title="Writes like a real board">Formulas, diagrams, graphs: everything that's painful to type, Gerald draws it for you, live.</Card>
      <Card at={7} num="Any software" title="Learn a new tool in minutes">Photoshop, Excel, Figma… It points at the right button and waits for your click. No tutorial video ever again.</Card>
    </div>
    <Foot at={10}>Zero retyping · zero screenshots · zero tutorials. Just ask.</Foot>
  </Slide>
);

const Clip: React.FC<{ src: string; trim?: number; top?: number; height?: number }> = ({ src, trim = 0, top = 150, height = 850 }) => {
  const { fps } = useVideoConfig();
  const p = useR(0, 0.8);
  return (
    <div style={{ position: "absolute", left: "50%", top, translate: "-50% 0", width: Math.round(height * 1.6), height, borderRadius: 28, overflow: "hidden", background: "#fff", border: `1px solid ${D.line}`, boxShadow: "0 30px 80px rgba(0,0,0,.12)", opacity: p, scale: `${0.97 + 0.03 * p}` }}>
      <Video src={staticFile(`footage/${src}`)} trimBefore={Math.round(trim * fps)} muted objectFit="contain" style={{ width: "100%", height: "100%" }} />
    </div>
  );
};
const DemoHead: React.FC<{ n: string; title: React.ReactNode }> = ({ n, title }) => (
  <AbsoluteFill style={{ padding: "44px 150px 0" }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 30 }}>
      <Eyebrow>{`Demo ${n} / 4`}</Eyebrow>
      <R at={0.2} style={{ fontSize: 40, letterSpacing: "-.035em", fontWeight: 500, marginBottom: 34 }}>{title}</R>
    </div>
  </AbsoluteFill>
);

export const Demo1: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <DemoHead n="1" title={<>Open your notes. <Em>Just talk.</Em></>} />
    <Clip src="pm-01-desktop-notes.mp4" top={140} height={800} />
    <Cap at={0.6} out={6}>Your desktop, your apps, your worksheet already on screen</Cap>
    <Cap at={6.5}>“Δ = 25 + 24, right?” → Gerald underlines the exercise and says wait</Cap>
  </Slide>
);
export const Demo2: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <DemoHead n="2" title={<>You write. It corrects. <Em>Then writes the clean solution.</Em></>} />
    <Clip src="pm-04-board-correction.mp4" top={140} height={800} />
    <Cap at={0.6} out={6}>You write Δ = 25 + 24 = 49, by hand</Cap>
    <Cap at={6.5} out={12}>Gerald underlines the sign error in red</Cap>
    <Cap at={12.5}>You fix it — then Gerald writes the formula: x₁ = 3, x₂ = 2</Cap>
  </Slide>
);
export const Demo2b: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <DemoHead n="2" title={<>A real session, <Em>filmed on my phone.</Em></>} />
    <Clip src="wa-phone.mp4" trim={80} top={150} height={760} />
    <Cap at={0.8}>Handwriting on the board → Gerald follows every line and underlines the wrong term</Cap>
  </Slide>
);
export const Demo3: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <DemoHead n="3" title={<>It opens a board. <Em>And plots the real curve.</Em></>} />
    <Clip src="pm-02-board-plot.mp4" top={140} height={800} />
    <Cap at={0.6} out={5}>“Show me the parabola on the board”</Cap>
    <Cap at={5.5}>A real plot of x² − 5x + 6 · roots 2 and 3 · vertex (2.5, −0.25)</Cap>
  </Slide>
);
export const Demo4: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <DemoHead n="4" title={<>Learn any software. <Em>Live, one click at a time.</Em></>} />
    <Clip src="pm-03-photoshop.mp4" trim={2} top={140} height={800} />
    <Cap at={0.6} out={6}>Goal: a red square, from scratch</Cap>
    <Cap at={6.5} out={24}>Shapes → Rectangle → Fill → #ff0000 → drag: Gerald points at each step</Cap>
    <Cap at={24.5}>Red square done. Gerald points, you click</Cap>
  </Slide>
);

const Row: React.FC<{ a: string; b: string; at: number }> = ({ a, b, at }) => (
  <R at={at} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
    <div style={{ padding: "24px 30px", borderRadius: 22, background: "#fff", border: `1px solid ${D.line}`, fontSize: 27, color: "#5e5e5b" }}>{a}</div>
    <div style={{ padding: "24px 30px", borderRadius: 22, background: D.dark, color: D.paper, fontSize: 27 }}>{b}</div>
  </R>
);
export const Clicky: React.FC = () => (
  <Slide>
    <Eyebrow>Why not Clicky?</Eyebrow>
    <H2 size={72} style={{ marginBottom: 36 }}>Clicky does it for you. <Em>Gerald teaches you to do it.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, font: `20px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted, padding: "0 30px 6px" }}><span>With Clicky</span><span>With Gerald</span></div>
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Row at={2} a="It does the task. You learn nothing." b="You do it yourself. You actually learn." />
      <Row at={5} a="It points roughly in the right area." b="It shows you exactly where to look and click." />
      <Row at={8} a="A few arrows on your screen." b="A real board: it writes, corrects and draws the curve." />
      <Row at={11} a="It doesn't know your course." b="It knows your course and makes your revision sheet." />
      <Row at={14} a="Mac first. Free plan: 25 messages a month." b="Windows and web. Open source. Costs almost nothing." />
    </div>
  </Slide>
);

export const Llms: React.FC = () => (
  <Slide>
    <Eyebrow>Why not Claude, ChatGPT or Gemini?</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>Brilliant brains. <Em>But they can't see your work, or show you anything.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 28 }}>
      <Card at={2} num="Claude" title="You send it screenshots">Every question starts with a capture. And when it takes over your computer, it does the work for you.</Card>
      <Card at={4.5} num="ChatGPT" title="It can't see your laptop">Screen sharing only works on the phone app. On your computer, you're back to copy-paste.</Card>
      <Card at={7} num="Gemini" title="Stuck in the browser">It only sees your Chrome tabs and answers in a side panel, far from your work.</Card>
    </div>
    <R at={10} style={{ marginTop: 44, fontSize: 32, letterSpacing: "-.02em" }}>None of them <b style={{ fontWeight: 500, background: `linear-gradient(transparent 58%, ${D.yellow2} 58%)` }}>shows you where</b> · <b style={{ fontWeight: 500, background: `linear-gradient(transparent 58%, ${D.yellow2} 58%)` }}>writes on your exercise</b> · <b style={{ fontWeight: 500, background: `linear-gradient(transparent 58%, ${D.yellow2} 58%)` }}>lets you try first</b></R>
  </Slide>
);

const TABLE: [string, string[]][] = [
  ["Sees what you're working on", ["phone only", "screenshots", "Chrome only", "✓", "✓"]],
  ["Shows you exactly where", ["✗", "✗", "✗", "roughly", "✓"]],
  ["Writes & draws on your work", ["✗", "✗", "✗", "arrows only", "✓"]],
  ["Makes you think first", ["in chat only", "in chat only", "in chat only", "✗", "✓"]],
  ["Open source", ["✗", "✗", "✗", "old version", "✓"]],
];
export const Table: React.FC = () => (
  <Slide>
    <Eyebrow>Side by side</Eyebrow>
    <H2 size={72} style={{ marginBottom: 36 }}>Everyone has a piece. <Em>Only Gerald has it all.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(5,1fr)", gap: "12px 0", fontSize: 25, alignItems: "center" }}>
      <span />{["ChatGPT", "Claude", "Gemini", "Clicky", "Gerald"].map((h) => <span key={h} style={{ font: `20px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: h === "Gerald" ? D.ink : D.muted, padding: "0 26px 10px", fontWeight: h === "Gerald" ? 700 : 400 }}>{h}</span>)}
      {TABLE.map(([row, cells], i) => (
        <React.Fragment key={row}>
          <R at={1.5 + i * 1.6} style={{ padding: "18px 26px", background: "#fff", border: `1px solid ${D.line}`, borderRadius: "18px 0 0 18px" }}>{row}</R>
          {cells.map((c, j) => <R key={j} at={1.5 + i * 1.6} style={{ padding: "18px 26px", background: j === 4 ? D.yellow : "#fff", borderTop: `1px solid ${D.line}`, borderBottom: `1px solid ${D.line}`, borderRight: j === 4 ? `1px solid ${D.line}` : "none", borderRadius: j === 4 ? "0 18px 18px 0" : 0, color: c === "✗" ? D.red : c === "✓" ? D.ink : "#5e5e5b", fontWeight: j === 4 ? 500 : 400 }}>{c}</R>)}
        </React.Fragment>
      ))}
    </div>
  </Slide>
);

export const How: React.FC = () => (
  <Slide>
    <Eyebrow>How it works</Eyebrow>
    <H2 size={72} style={{ marginBottom: 40 }}>One voice turn, <Em>from keypress to ink.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 18 }}>
      {[["01 · Listen", "Push-to-talk", "Your voice + one look at the screen, only while you hold the key."], ["02 · Think", "Realtime voice model", "Hears, sees and answers in one stream. Remembers the whole session and your courses."], ["03 · Aim", "Grounding", "UI tree → OCR → Moondream. Never trusts the model's raw coordinates."], ["04 · Draw", "Tools", "point · circle · underline · arrow · write · plot, traced live by Gerald's cursor."]].map(([k, t, d], i) => (
        <R key={k} at={1 + i * 1.2}><div style={{ background: i === 2 ? D.dark : "#fff", color: i === 2 ? D.paper : D.ink, border: `1px solid ${D.line}`, borderRadius: 26, padding: 30, minHeight: 270 }}>
          <small style={{ font: `18px ${LABEL}`, letterSpacing: ".06em", textTransform: "uppercase", color: i === 2 ? "rgba(247,246,243,.6)" : D.muted }}>{k}</small>
          <div style={{ fontSize: 30, margin: "36px 0 14px", fontWeight: 500, letterSpacing: "-.03em", color: i === 2 ? D.yellow : D.ink }}>{t}</div>
          <p style={{ margin: 0, fontSize: 21, lineHeight: 1.35, color: i === 2 ? "rgba(247,246,243,.6)" : "#5e5e5b" }}>{d}</p></div></R>
      ))}
    </div>
    <div style={{ display: "flex", gap: 40, marginTop: 40 }}>
      {[["0.6 s", "to locate a target"], ["~2.4 px", "median pointing error"], ["77 → 91 %", "pedagogy score on 16 judged scenarios"]].map(([n, t], i) => (
        <R key={n} at={8 + i * 1.5} style={{ display: "flex", alignItems: "baseline", gap: 16 }}><strong style={{ fontSize: 64, fontWeight: 500, letterSpacing: "-.05em" }}>{n}</strong><span style={{ fontSize: 22, color: D.muted }}>{t}</span></R>
      ))}
    </div>
  </Slide>
);

export const Market: React.FC = () => (
  <Slide>
    <Eyebrow>Open to market</Eyebrow>
    <H2 size={72} style={{ marginBottom: 44 }}>Students already learn with AI. <Em>They just don't have a teacher yet.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 28 }}>
      {[["95 %", "of UK undergraduates use AI for their studies", "HEPI Student Generative AI Survey, Mar. 2026"], ["$57 B", "AI-in-education market by 2033, from $8.3 B in 2025 (×7, 25.9 % CAGR)", "Grand View Research"], ["$160 B", "private tutoring market by 2034, from $67 B in 2025", "Fortune Business Insights"]].map(([n, t, s], i) => (
        <R key={n} at={1.5 + i * 2.2}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 28, padding: 38, minHeight: 330 }}><strong style={{ display: "block", fontSize: 96, fontWeight: 500, letterSpacing: "-.06em", lineHeight: 1, marginBottom: 20 }}>{n}</strong><p style={{ margin: 0, fontSize: 25, lineHeight: 1.35, color: "#5e5e5b" }}>{t}</p><small style={{ display: "block", marginTop: 16, font: `17px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".05em", color: D.muted }}>{s}</small></div></R>
      ))}
    </div>
    <Foot at={9}>Gerald sits where both meet: the tutor's pedagogy, at the price of an API call.</Foot>
  </Slide>
);

export const Numbers: React.FC = () => (
  <Slide>
    <Eyebrow>By the numbers</Eyebrow>
    <H2 size={72} style={{ marginBottom: 40 }}>Gerald vs. a chatbot. <Em>Not even close.</Em></H2>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 24 }}>
      {[["0", "equations retyped", "vs. every single one in a chat box"], ["5×", "fewer steps to ask", "hold a key and talk vs. screenshot → crop → upload → explain → ask"], ["37×", "more precise pointing", "~2.4 px median error vs. ~90 px for the raw model"], ["+16 pts", "pedagogy score", "77 % → up to 93 % on 16 judged tutoring scenarios"], ["0.6 s", "to find any target", "on screen, in any app"], ["$0.0002", "per gesture", "a private tutor at the price of a rounding error"]].map(([n, t, s], i) => (
        <R key={n} at={1 + i * 1.4}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 26, padding: "28px 32px", display: "flex", gap: 24, alignItems: "baseline" }}><strong style={{ fontSize: 68, fontWeight: 500, letterSpacing: "-.05em", lineHeight: 1, minWidth: 190 }}>{n}</strong><div><div style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-.02em" }}>{t}</div><div style={{ fontSize: 19, color: "#5e5e5b", marginTop: 4 }}>{s}</div></div></div></R>
      ))}
    </div>
  </Slide>
);

export const Thanks: React.FC = () => (
  <Slide>
    <Eyebrow>Conclusion</Eyebrow>
    <H2 size={110}>Stop retyping. Stop screenshotting. <Em>Just ask Gerald.</Em></H2>
    <R at={5} style={{ fontSize: 40, letterSpacing: "-.03em" }}>Bonus: it's the first teacher you can <span style={{ background: `linear-gradient(transparent 58%, ${D.yellow2} 58%)` }}>mute</span>.</R>
    <R at={1.2} style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 24 }}><Mark size={60} /><span style={{ font: `22px ${LABEL}`, letterSpacing: ".04em", textTransform: "uppercase", color: D.muted }}>Thank you · github.com/talal95c/Gerald.ai-</span></R>
  </Slide>
);
export const _ = SANS;
