import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Bg, Caption, H, Lead, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

/** Scene 1 · Hook — 11 pm, the night before the test. */
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const caret = Math.floor(frame / (fps / 2)) % 2 === 0;
  return (
    <Bg dark>
      <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center" }}>
        <Reveal at={0.2}><Badge dark dot>11:04 pm · the night before the test</Badge></Reveal>
        <div style={{ height: 40 }} />
        <Words text="One equation. Forty pages of course. And nobody next to you." at={0.7} step={0.12} size={112} color="#fff" maxWidth={1500} highlight={["nobody"]} />
        <Reveal at={3.6} style={{ marginTop: 50 }}>
          <Lead light size={34}>
            x² − 5x + 6 = 0<span style={{ opacity: caret ? 1 : 0, color: T.acc2 }}> |</span>
          </Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};

const stream = (text: string, p: number) => text.slice(0, Math.floor(text.length * p));

/** Scene 2 · Problem — the chatbot dumps the answer. */
export const Chat: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const q = useP(0.6, 1.2, Easing.linear);
  const a = useP(2.2, 1.1, Easing.linear);
  const answer = "a = 1, b = −5, c = 6. Δ = b² − 4ac = 25 − 24 = 1. √Δ = 1.\nx₁ = (5 − 1)/2 = 2 and x₂ = (5 + 1)/2 = 3.\nSolutions: x = 2 or x = 3.";
  const win = useP(0, 0.9);
  const dim = interpolate(frame, [6.2 * fps, 6.9 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 1180, borderRadius: 24, background: "#fff", border: `1px solid ${T.line}`, boxShadow: "0 40px 90px -40px rgba(30,40,120,.35)", overflow: "hidden", opacity: win, scale: `${0.96 + 0.04 * win}`, filter: `grayscale(${dim}) blur(${dim * 3}px)` }}>
          <div style={{ height: 56, display: "flex", alignItems: "center", gap: 8, padding: "0 20px", borderBottom: `1px solid ${T.line}` }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => <i key={c} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />)}
            <span style={{ marginLeft: 16, font: `16px ${FONT.body}`, color: T.mut }}>Some chatbot</span>
          </div>
          <div style={{ padding: "34px 40px", display: "flex", flexDirection: "column", gap: 24, minHeight: 420 }}>
            <div style={{ alignSelf: "flex-end", maxWidth: 700, padding: "16px 22px", borderRadius: "18px 18px 4px 18px", background: T.soft, font: `26px ${FONT.body}` }}>
              {stream("Solve x² − 5x + 6 = 0 please", q)}
            </div>
            {a > 0 && (
              <div style={{ alignSelf: "flex-start", maxWidth: 820, padding: "18px 24px", borderRadius: "18px 18px 18px 4px", background: "#f3f4f6", font: `26px/1.5 ${FONT.body}`, whiteSpace: "pre-wrap" }}>
                {stream(answer, a)}
              </div>
            )}
          </div>
        </div>
        <Reveal at={3.6} style={{ position: "absolute", left: "50%", top: "50%", translate: "-50% -50%" }}>
          <div style={{ rotate: "-6deg", padding: "14px 30px", border: `6px solid ${T.red}`, borderRadius: 14, font: `600 72px ${FONT.head}`, letterSpacing: "-.03em", color: T.red, background: "rgba(255,255,255,.85)", mixBlendMode: "multiply" }}>Copied. Not learned.</div>
        </Reveal>
      </AbsoluteFill>
      <Caption at={1.0} out={3.4}>AI gives you the answer in three seconds.</Caption>
      <Caption at={4.4}>You paste it. You still can't do it.</Caption>
    </Bg>
  );
};

/** Scene 3 · The next morning — same equation, blank page. */
export const Morning: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const caret = Math.floor(frame / (fps / 2)) % 2 === 0;
  const timer = Math.max(0, Math.floor(frame / fps));
  const shake = interpolate(frame, [4 * fps, 4.1 * fps, 4.2 * fps, 4.3 * fps, 4.4 * fps], [0, -6, 6, -4, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <Reveal at={0}>
          <div style={{ width: 1100, height: 640, borderRadius: 18, background: "#fff", border: `1px solid ${T.line}`, boxShadow: "0 40px 90px -40px rgba(30,40,120,.3)", padding: "54px 70px", position: "relative", translate: `${shake}px 0` }}>
            <div style={{ display: "flex", justifyContent: "space-between", font: `18px ${FONT.body}`, color: T.mut, textTransform: "uppercase", letterSpacing: ".08em" }}>
              <span>Maths test · 8:05 am</span><span>00:{String(timer).padStart(2, "0")}</span>
            </div>
            <div style={{ marginTop: 40, font: `500 40px ${FONT.head}`, letterSpacing: "-.02em" }}>Exercise 1 — Solve x² − 5x + 6 = 0</div>
            {[0, 1, 2, 3, 4].map((i) => <div key={i} style={{ marginTop: i === 0 ? 50 : 54, height: 1, background: "rgba(0,0,0,.14)" }} />)}
            <div style={{ position: "absolute", left: 72, top: 212, width: 3, height: 44, borderRadius: 2, background: T.ink, opacity: caret ? 1 : 0 }} />
          </div>
        </Reveal>
      </AbsoluteFill>
      <Caption at={1.2}>The next morning. Same equation. Still stuck.</Caption>
    </Bg>
  );
};

/** Scene 4 · The number — PISA 2022. */
export const Stat: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.round(interpolate(frame, [0.4 * fps, 2.4 * fps], [495, 474], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  const p = useP(0.2, 0.8);
  return (
    <Bg dark>
      <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center" }}>
        <Reveal at={0}><Badge dark>PISA 2022 · France · mathematics</Badge></Reveal>
        <div style={{ display: "flex", alignItems: "baseline", gap: 40, marginTop: 30 }}>
          <div style={{ font: `500 360px/.9 ${FONT.head}`, letterSpacing: "-.07em", color: "#fff", opacity: p, filter: `blur(${(1 - p) * 10}px)` }}>{n}</div>
          <Reveal at={2.2}><div style={{ font: `500 72px ${FONT.head}`, letterSpacing: "-.04em", color: T.acc2 }}>−21 pts</div></Reveal>
        </div>
        <Reveal at={2.6} style={{ marginTop: 30 }}>
          <Lead light size={34}>Average maths score, down 21 points since 2018 — a historic drop.<br /><span style={{ color: "rgba(255,255,255,.4)", fontSize: 24 }}>Source: OECD, PISA 2022 results (Dec. 2023)</span></Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};

/** Scene 5 · Thesis. */
export const Thesis: React.FC = () => (
  <Bg>
    <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <Words text="Learning alone in front of a screen means learning with nobody next to you." at={0.2} step={0.1} size={104} maxWidth={1560} highlight={["nobody", "next", "to", "you"]} align="center" />
      <Reveal at={2.6} style={{ marginTop: 50 }}><H size={56} color={T.mut}>Until now.</H></Reveal>
    </AbsoluteFill>
  </Bg>
);
