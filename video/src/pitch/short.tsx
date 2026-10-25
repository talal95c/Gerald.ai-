import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Img, Sequence, staticFile, useVideoConfig } from "remotion";
import { Cap, Card, Counter, D, Em, Eyebrow, H2, Kbd, LABEL, Mark, Notch, R, Slide, useR } from "./deck";

const Big: React.FC<{ children: React.ReactNode; at?: number; size?: number }> = ({ children, at = 0.1, size = 120 }) => (
  <R at={at} style={{ fontSize: size, lineHeight: 0.98, letterSpacing: "-.055em", fontWeight: 500, maxWidth: 1560 }}>{children}</R>
);

const VOICES = [["My friends", "Just learn with AI."], ["My teachers", "You should learn with AI."], ["Every ad", "Learn anything with AI!"], ["My mum", "Have you tried learning with AI?"]];
export const Hook: React.FC = () => (
  <Slide dark>
    <Eyebrow light at={0.1}>Hackathon 2026</Eyebrow>
    <Big at={0.2}>Everyone told me: <span style={{ color: D.yellow }}>learn with AI.</span></Big>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 50, maxWidth: 1500 }}>
      {VOICES.map(([who, q], i) => (
        <R key={who} at={1.3 + i * 0.45} style={{ display: "flex", alignItems: "baseline", gap: 14, padding: "14px 24px", borderRadius: 999, background: "rgba(247,246,243,.08)", border: "1px solid rgba(247,246,243,.15)" }}>
          <span style={{ font: `17px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", opacity: 0.55 }}>{who}</span><span style={{ fontSize: 26 }}>{q}</span>
        </R>
      ))}
    </div>
    <R at={3.6} style={{ marginTop: 50, fontSize: 56, letterSpacing: "-.04em" }}>So I did. <Em>Then I tried… with maths.</Em></R>
  </Slide>
);

export const Problem: React.FC = () => (
  <Slide>
    <Eyebrow>The problem</Eyebrow>
    <Big at={0.1} size={88}>Maths is written, drawn, pointed at. <Em>AI tutors are stuck in a chat box.</Em></Big>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 24, marginTop: 50 }}>
      <Card at={1.6} num="01" title="You retype everything">x^2 - 5x + 6 = 0… every single time.</Card>
      <Card at={3.6} num="02" title="It can't point">“The third icon on the left” is the best it can do.</Card>
      <Card at={5.4} num="03" title="It gives you the answer">You copy it. Tomorrow, you still can't solve it.</Card>
    </div>
    <R at={7.4} style={{ marginTop: 34, display: "flex", alignItems: "center", gap: 30, padding: "18px 34px", borderRadius: 22, background: D.dark, color: D.paper, alignSelf: "flex-start" }}>
      <Counter from={495} to={474} at={7.6} dur={1.2} style={{ fontSize: 72, fontWeight: 500, letterSpacing: "-.06em", color: D.yellow }} />
      <span style={{ fontSize: 24, maxWidth: 820 }}>PISA 2022 maths, France: −21 points, a historic low.</span>
    </R>
  </Slide>
);

export const Meet: React.FC = () => (
  <Slide>
    <Notch text="Gerald is listening…" />
    <Eyebrow at={0.1}>The solution</Eyebrow>
    <R at={0.2}><div style={{ display: "flex", alignItems: "center", gap: 36 }}><Mark size={120} /><div style={{ fontSize: 130, lineHeight: 0.95, letterSpacing: "-.06em", fontWeight: 500 }}>Meet Gerald.</div></div></R>
    <R at={0.9} style={{ fontSize: 44, letterSpacing: "-.035em", marginTop: 20, maxWidth: 900 }}>The AI teacher that <Em>lives on your screen.</Em></R>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 44, maxWidth: 900 }}>
      {["It sees", "It talks", "It draws", "It makes you think"].map((t, i) => (
        <R key={t} at={2.2 + i * 0.5} style={{ padding: "18px 30px", borderRadius: 999, background: i === 3 ? D.yellow : "#fff", border: `1px solid ${D.line}`, fontSize: 32, fontWeight: 500, letterSpacing: "-.02em" }}>{t}</R>
      ))}
    </div>
    <R at={4.2} style={{ marginTop: 50, display: "flex", alignItems: "center", gap: 14, fontSize: 24 }}><Kbd>Ctrl</Kbd> + <Kbd>Shift</Kbd><small style={{ marginLeft: 16, font: `20px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted }}>hold to ask · any app</small></R>
    <Screens />
  </Slide>
);

const Shot: React.FC<{ src: string; style?: React.CSSProperties }> = ({ src, style }) => (
  <div style={{ width: 520, height: 325, borderRadius: 18, overflow: "hidden", border: `1px solid ${D.line}`, boxShadow: "0 24px 60px rgba(0,0,0,.14)", background: "#fff", ...style }}>
    <Img src={staticFile(`screens/${src}`)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }} />
  </div>
);
const Screens: React.FC = () => (
  <div style={{ position: "absolute", right: 90, top: 150, width: 700, height: 800 }}>
    {[["notes.jpg", 0, 0, -6], ["plot.jpg", 60, 230, 3], ["photoshop.jpg", 130, 460, -2]].map(([src, x, y, rot], i) => (
      <R key={src as string} at={1.2 + i * 0.4} style={{ position: "absolute", left: x as number, top: y as number, rotate: `${rot}deg` }}><Shot src={src as string} /></R>
    ))}
  </div>
);

const Clip: React.FC<{ src: string; trim?: number; height?: number }> = ({ src, trim = 0, height = 800 }) => {
  const { fps } = useVideoConfig();
  const p = useR(0, 0.7);
  return (
    <div style={{ position: "absolute", left: "50%", top: 140, translate: "-50% 0", width: Math.round(height * 1.6), height, borderRadius: 28, overflow: "hidden", background: "#fff", border: `1px solid ${D.line}`, boxShadow: "0 30px 80px rgba(0,0,0,.12)", opacity: p, scale: `${0.97 + 0.03 * p}` }}>
      <Video src={staticFile(`footage/${src}`)} trimBefore={Math.round(trim * fps)} muted objectFit="contain" style={{ width: "100%", height: "100%" }} />
    </div>
  );
};
const Head: React.FC<{ n: string; title: React.ReactNode }> = ({ n, title }) => (
  <AbsoluteFill style={{ padding: "44px 150px 0" }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 30 }}>
      <Eyebrow>{`Live demo ${n}`}</Eyebrow>
      <R at={0.2} style={{ fontSize: 40, letterSpacing: "-.035em", fontWeight: 500, marginBottom: 34 }}>{title}</R>
    </div>
  </AbsoluteFill>
);

export const Demo1: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <Head n="1 / 4" title={<>Open your notes. <Em>Just talk.</Em></>} />
    <Clip src="pm-01-desktop-notes.mp4" trim={2} />
    <Cap at={0.5} out={5}>Your worksheet is already on screen — zero retyping</Cap>
    <Cap at={5.5}>“Δ = 25 + 24, right?” → Gerald points at the exercise and says wait</Cap>
  </Slide>
);
export const Demo2: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <Head n="2 / 4" title={<>You write. <Em>It corrects, live.</Em></>} />
    <Clip src="pm-04-board-correction.mp4" trim={2.5} />
    <Cap at={0.5} out={5.5}>Handwritten Δ = 25 + 24 = 49</Cap>
    <Cap at={6} out={10.5}>Gerald underlines the sign error in red — you fix it</Cap>
    <Cap at={11}>Then it writes the clean solution: x₁ = 3, x₂ = 2</Cap>
  </Slide>
);
export const Demo3: React.FC = () => (
  <Slide style={{ padding: 0 }}>
    <Head n="3 / 4" title={<>It opens a board. <Em>And plots the real curve.</Em></>} />
    <Clip src="pm-02-board-plot.mp4" trim={1.5} />
    <Cap at={0.5}>Real plot of x² − 5x + 6 · roots 2 and 3 · vertex (2.5, −0.25)</Cap>
  </Slide>
);
const PS: readonly (readonly [number, number])[] = [[6, 4.5], [20.5, 4.5], [29.5, 6.5]];
export const Demo4: React.FC = () => {
  const { fps } = useVideoConfig();
  let acc = 0;
  return (
    <Slide style={{ padding: 0 }}>
      <Head n="4 / 4" title={<>Learn any software. <Em>One click at a time.</Em></>} />
      {PS.map(([from, len], i) => { const s = acc; acc += len; return (
        <Sequence key={i} from={Math.round(s * fps)} durationInFrames={Math.round(len * fps)} layout="none"><Clip src="pm-03-photoshop.mp4" trim={from} /></Sequence>
      ); })}
      <Cap at={0.5} out={4.3}>“I need a red square” → Gerald points at Shapes, then Rectangle</Cap>
      <Cap at={4.8} out={8.8}>Fill colour → hex #ff0000 · it waits for your click at every step</Cap>
      <Cap at={9.3} out={15.2}>Red square done. Gerald points, you click</Cap>
      <Sequence from={Math.round(15.5 * fps)} layout="none">
        <AbsoluteFill style={{ background: D.paper, padding: "120px 150px", justifyContent: "center" }}>
          <Eyebrow at={0}>Not just a square</Eyebrow>
          <Big at={0.1} size={100}>You didn't get a red square. <Em>You learned the tool.</Em></Big>
          <div style={{ display: "flex", gap: 16, marginTop: 50 }}>
            {["Photoshop today", "Excel tomorrow", "Figma, Blender, your IDE…", "No tutorial video ever again"].map((t, i) => (
              <R key={t} at={0.9 + i * 0.35} style={{ padding: "16px 28px", borderRadius: 999, background: i === 3 ? D.yellow : "#fff", border: `1px solid ${D.line}`, fontSize: 28, fontWeight: 500, letterSpacing: "-.02em" }}>{t}</R>
            ))}
          </div>
        </AbsoluteFill>
      </Sequence>
    </Slide>
  );
};

const AGENTS: [string, string, string][] = [["Clicky", "Assistant", "Takes the mouse. Does the task for you."], ["Claude", "Computer use", "Drives your computer. You watch."], ["OpenAI", "Agent / Operator", "Books, clicks, fills forms — for you."], ["ChatGPT", "Chat box", "Can't see your laptop. Copy-paste."], ["Gemini", "Side panel", "Chrome tabs only, far from your work."]];
const ROWS: [string, string[]][] = [["Sees your work", ["screenshots", "✓", "✓"]], ["Shows exactly where", ["✗", "roughly", "✓"]], ["Writes on your exercise", ["✗", "arrows", "✓"]], ["Lets you try first", ["in chat", "✗", "✓"]]];
export const Agents: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <Slide>
      <Sequence durationInFrames={Math.round(10.5 * fps)} layout="none">
        <AbsoluteFill style={{ padding: "120px 150px", justifyContent: "center" }}>
          <Eyebrow at={0}>The market · agents & chatbots</Eyebrow>
          <Big size={84}>They do it <Em>for</Em> you. <Em>You learn nothing.</Em></Big>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 18, marginTop: 44 }}>
            {AGENTS.map(([n, k, d], i) => (
              <R key={n} at={1.2 + i * 0.6}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 24, padding: 28, minHeight: 250 }}>
                <small style={{ font: `17px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted }}>{k}</small>
                <div style={{ fontSize: 40, fontWeight: 500, letterSpacing: "-.04em", margin: "18px 0 12px" }}>{n}</div>
                <p style={{ margin: 0, fontSize: 21, lineHeight: 1.35, color: "#5e5e5b" }}>{d}</p>
                <div style={{ marginTop: 18, color: D.red, fontSize: 20, fontWeight: 500 }}>{i < 3 ? "✗ does it for you" : "✗ stuck in a chat"}</div>
              </div></R>
            ))}
          </div>
        </AbsoluteFill>
      </Sequence>
      <Sequence from={Math.round(10.5 * fps)} layout="none">
        <AbsoluteFill style={{ background: D.paper, padding: "120px 150px", justifyContent: "center" }}>
          <Eyebrow at={0}>Why Gerald</Eyebrow>
          <div style={{ display: "flex", gap: 60, alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <Big at={0.1} size={84}>Gerald is <Em>a teacher.</Em></Big>
              <div style={{ display: "grid", gridTemplateColumns: "1.4fr repeat(3,1fr)", gap: "10px 0", fontSize: 24, marginTop: 40, alignItems: "center" }}>
                <span />{["Chatbots", "Clicky", "Gerald"].map((h) => <span key={h} style={{ font: `19px ${LABEL}`, textTransform: "uppercase", letterSpacing: ".06em", color: D.muted, padding: "0 22px 6px", fontWeight: h === "Gerald" ? 700 : 400 }}>{h}</span>)}
                {ROWS.map(([row, cells], i) => (
                  <React.Fragment key={row}>
                    <R at={0.8 + i * 0.6} style={{ padding: "14px 22px", background: "#fff", border: `1px solid ${D.line}`, borderRadius: "16px 0 0 16px" }}>{row}</R>
                    {cells.map((c, j) => <R key={j} at={0.8 + i * 0.6} style={{ padding: "14px 22px", background: j === 2 ? D.yellow : "#fff", borderTop: `1px solid ${D.line}`, borderBottom: `1px solid ${D.line}`, borderRight: j === 2 ? `1px solid ${D.line}` : "none", borderRadius: j === 2 ? "0 16px 16px 0" : 0, color: c === "✗" ? D.red : c === "✓" ? D.ink : "#5e5e5b", fontWeight: j === 2 ? 600 : 400 }}>{c}</R>)}
                  </React.Fragment>
                ))}
              </div>
            </div>
            <R at={0.5} style={{ rotate: "2deg", marginTop: 20 }}><Shot src="board.jpg" style={{ width: 600, height: 375 }} /></R>
          </div>
        </AbsoluteFill>
      </Sequence>
    </Slide>
  );
};

export const Numbers: React.FC = () => (
  <Slide>
    <Eyebrow>By the numbers</Eyebrow>
    <Big size={84}>Gerald vs. a chatbot. <Em>Not even close.</Em></Big>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 22, marginTop: 44 }}>
      {[["0", "equations retyped"], ["37×", "more precise pointing (2.4 px vs 90 px)"], ["0.6 s", "to find any target, any app"], ["77 → 93 %", "pedagogy score, 16 judged scenarios"], ["$0.0002", "per gesture"], ["Open source", "Windows + web · MIT"]].map(([n, t], i) => (
        <R key={n} at={1 + i * 0.7}><div style={{ background: "#fff", border: `1px solid ${D.line}`, borderRadius: 24, padding: "26px 30px" }}><strong style={{ display: "block", fontSize: 64, fontWeight: 500, letterSpacing: "-.05em", lineHeight: 1 }}>{n}</strong><div style={{ fontSize: 23, color: "#5e5e5b", marginTop: 10 }}>{t}</div></div></R>
      ))}
    </div>
  </Slide>
);

export const Cta: React.FC = () => (
  <Slide dark>
    <Eyebrow light>Gerald</Eyebrow>
    <Big at={0.2} size={110}>Stop retyping. Stop screenshotting. <span style={{ color: D.yellow }}>Just ask Gerald.</span></Big>
    <R at={2.8} style={{ marginTop: 40, fontSize: 44, letterSpacing: "-.03em", opacity: 0.85 }}>The first teacher you can actually <span style={{ borderBottom: `4px solid ${D.yellow}` }}>mute</span>.</R>
    <R at={1} style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 24 }}><Mark size={60} color={D.paper} /><span style={{ font: `22px ${LABEL}`, letterSpacing: ".04em", textTransform: "uppercase", opacity: 0.6 }}>github.com/talal95c/Gerald.ai- · open source · MIT</span></R>
  </Slide>
);
export const __ = H2;
