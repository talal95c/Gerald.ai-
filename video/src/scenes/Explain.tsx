import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Bg, Brand, Btn, Caption, H, Keycap, Lead, Orb, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

/** Pitch deck · "Under the hood", verbatim. */
const NODES = [
  { k: "Trigger", t: "Push-to-talk", d: "24 kHz PCM mic + one capture of the screen under the cursor" },
  { k: "Perception", t: "UIA · OCR · Moondream", d: "Visible elements with provenance, to anchor every gesture" },
  { k: "Brain", t: "gpt-realtime-2", d: "Voice + image over a single WebSocket, context kept for the whole session" },
  { k: "Tools", t: "point · circle · plot · diagram", d: "Validated function calls, turned into drawing commands" },
  { k: "Render", t: "Overlay + board", d: "Transparent, click-through window, excluded from captures" },
];

/** Scene · How it works — one voice turn, from keypress to ink. */
export const How: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pulse = interpolate(frame, [1.2 * fps, 5.2 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  return (
    <Bg>
      <AbsoluteFill style={{ padding: "110px 120px 0", alignItems: "center" }}>
        <Reveal at={0}><Badge>Under the hood</Badge></Reveal>
        <Reveal at={0.15} style={{ marginTop: 22, textAlign: "center" }}><H size={72}>One voice turn,<br />from keypress to ink.</H></Reveal>
        <div style={{ position: "relative", display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 22, marginTop: 70, width: "100%" }}>
          <div style={{ position: "absolute", left: "6%", right: "6%", top: 44, height: 3, background: T.line, borderRadius: 3 }}>
            <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pulse * 100}%`, background: `linear-gradient(90deg, transparent, ${T.acc})`, borderRadius: 3 }} />
            <div style={{ position: "absolute", left: `${pulse * 100}%`, top: -9, width: 20, height: 20, borderRadius: "50%", background: T.acc, boxShadow: "0 0 0 8px rgba(61,43,255,.18)", translate: "-50% 0" }} />
          </div>
          {NODES.map((n, i) => {
            const on = pulse >= i / 4 - 0.02;
            return (
              <Reveal key={n.k} at={0.4 + i * 0.12}>
                <div style={{ marginTop: 100, padding: 28, minHeight: 290, borderRadius: 24, background: on ? T.ink : "#fff", color: on ? "#fff" : T.ink, border: `1px solid ${T.line}`, boxShadow: on ? "0 30px 60px -30px rgba(61,43,255,.5)" : "none", translate: `0 ${on ? -6 : 0}px` }}>
                  <div style={{ font: `16px ${FONT.body}`, letterSpacing: ".08em", textTransform: "uppercase", color: on ? "rgba(255,255,255,.55)" : T.mut }}>0{i + 1} · {n.k}</div>
                  <div style={{ marginTop: 40, font: `500 30px ${FONT.head}`, letterSpacing: "-.02em", color: on ? "#c7d2fe" : T.ink }}>{n.t}</div>
                  <div style={{ marginTop: 12, font: `20px/1.35 ${FONT.body}`, color: on ? "rgba(255,255,255,.7)" : T.mut }}>{n.d}</div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </AbsoluteFill>
      <Caption at={5.6}>Trust order: UIA element → OCR word → visual grounder → never the model's raw coordinate.</Caption>
    </Bg>
  );
};

/** Scene · Trust & proof — three facts. */
export const Proof: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const score = Math.round(interpolate(frame, [1.6 * fps, 3.4 * fps], [77, 92], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  const cards: { h: React.ReactNode; p: string }[] = [
    { h: <>{score} %</>, p: "Pedagogy harness: 17 rendered scenarios, real gpt-realtime-2 turns, gpt-5.5 judge (8 criteria). Baseline prompt 77 % → tutor-first 91–93 %." },
    { h: <span style={{ fontSize: 64 }}>Vision on demand</span>, p: "No continuous capture: the screen is only read while you hold the shortcut." },
    { h: <span style={{ fontSize: 64 }}>Real consent</span>, p: "Before any action, an \"Allow / Cancel\" prompt. The model can't approve itself. Esc stops everything." },
  ];
  return (
    <Bg>
      <AbsoluteFill style={{ padding: "0 120px", justifyContent: "center" }}>
        <Reveal at={0}><Badge>Trust & privacy</Badge></Reveal>
        <Reveal at={0.15} style={{ marginTop: 22 }}><H size={72}>A tutor on your screen,<br />not a spy.</H></Reveal>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 26, marginTop: 60 }}>
          {cards.map((c, i) => (
            <Reveal key={i} at={0.6 + i * 0.18}>
              <div style={{ padding: 38, borderRadius: 26, background: "#fff", border: `1px solid ${T.line}`, minHeight: 300 }}>
                <div style={{ height: 92, display: "flex", alignItems: "center", font: `500 92px/1 ${FONT.head}`, letterSpacing: "-.05em", color: i === 0 ? T.acc : T.ink }}>{c.h}</div>
                <Lead size={25} style={{ marginTop: 26 }}>{c.p}</Lead>
              </div>
            </Reveal>
          ))}
        </div>
      </AbsoluteFill>
    </Bg>
  );
};

/** Scene · CTA. */
export const Cta: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const press = interpolate(frame, [2.6 * fps, 2.75 * fps, 3.6 * fps, 3.75 * fps], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const brand = useP(0.1, 1.1);
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <div style={{ opacity: brand, scale: `${0.9 + 0.1 * brand}`, filter: `blur(${(1 - brand) * 10}px)` }}><Brand size={96} /></div>
        <div style={{ marginTop: 44 }}>
          <Words text="Doesn't give you the answer. Helps you find it." at={0.8} step={0.1} size={92} align="center" maxWidth={1500} highlight={["find"]} />
        </div>
        <Reveal at={2.2} style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 14, font: `28px ${FONT.body}`, color: T.mut }}>
          <Orb size={24} /> Hold <Keycap label="Ctrl" pressed={press} /> + <Keycap label="Shift" pressed={press} /> and ask out loud
        </Reveal>
        <Reveal at={2.8} style={{ marginTop: 46, display: "flex", gap: 16 }}>
          <Btn>Try the demo</Btn><Btn primary>Learn live →</Btn>
        </Reveal>
        <Reveal at={3.4} style={{ position: "absolute", bottom: 70 }}>
          <Lead size={24}>github.com/talal95c/Gerald.ai- · Any app · Windows first · open source (MIT)</Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};
