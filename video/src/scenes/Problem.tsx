import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Bg, Caption, H, Lead, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

/** Scene 1 · Opener — the deck's problem statement (slide 3). */
export const Hook: React.FC = () => (
  <Bg dark>
    <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center" }}>
      <Reveal at={0.2}><Badge dark>The problem</Badge></Reveal>
      <div style={{ height: 40 }} />
      <Words text="Learning alone in front of a screen means learning with nobody next to you." at={0.7} step={0.1} size={108} color="#fff" maxWidth={1560} highlight={["nobody", "next", "to", "you"]} />
    </AbsoluteFill>
  </Bg>
);

const stream = (text: string, p: number) => text.slice(0, Math.floor(text.length * p));

/** Scene 2 · Problem — the chatbot dumps the answer. */
export const Chat: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const q = useP(0.6, 1.2, Easing.linear);
  const a = useP(2.2, 1.1, Easing.linear);
  const answer = "a = 1, b = −5, c = 6. Δ = b² − 4ac = 25 − 24 = 1. √Δ = 1.\nx₁ = (5 − 1)/2 = 2 and x₂ = (5 + 1)/2 = 3.\nSolutions: x = 2 or x = 3.";
  const win = useP(0, 0.9);
  const dim = interpolate(frame, [4.2 * fps, 5.2 * fps], [0, 0.8], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 1180, borderRadius: 24, background: "#fff", border: `1px solid ${T.line}`, boxShadow: "0 40px 90px -40px rgba(30,40,120,.35)", overflow: "hidden", opacity: win, scale: `${0.96 + 0.04 * win}`, filter: `grayscale(${dim}) blur(${dim * 3}px)` }}>
          <div style={{ height: 56, display: "flex", alignItems: "center", gap: 8, padding: "0 20px", borderBottom: `1px solid ${T.line}` }}>
            {["#ff5f57", "#febc2e", "#28c840"].map((c) => <i key={c} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />)}
            <span style={{ marginLeft: 16, font: `16px ${FONT.body}`, color: T.mut }}>Chatbot</span>
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
      </AbsoluteFill>
      <Caption at={1.0} out={3.6}>AI gives the answer. Chatbots solve the exercise for you.</Caption>
      <Caption at={4.0}>You copy it. You don't understand it.</Caption>
    </Bg>
  );
};

/** Scene 3 · Deck point 02 — it can't see your screen. */
export const Morning: React.FC = () => (
  <Bg>
    <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center" }}>
      <Reveal at={0}><Badge>It can't see your screen</Badge></Reveal>
      <div style={{ height: 36 }} />
      <Words text="Screenshots, copy-paste, re-explaining context on every question." at={0.4} step={0.09} size={92} maxWidth={1560} />
      <Reveal at={2.6} style={{ marginTop: 40 }}><H size={56} color={T.mut}>The learning flow breaks.</H></Reveal>
    </AbsoluteFill>
  </Bg>
);

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

/** Scene 5 · Deck point 03 — a real tutor is rare. */
export const Thesis: React.FC = () => (
  <Bg>
    <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <Reveal at={0}><Badge>A real tutor is rare</Badge></Reveal>
      <div style={{ height: 36 }} />
      <Words text="A tutor points, draws, makes you think. But not at 11 pm, and not for everyone." at={0.4} step={0.09} size={96} maxWidth={1560} align="center" highlight={["not", "for", "everyone"]} />
    </AbsoluteFill>
  </Bg>
);
