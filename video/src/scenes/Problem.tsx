import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Bg, Caption, H, Lead, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

/** Scene 1 · Hook — punchy, dark. */
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const caret = Math.floor(frame / (fps / 2)) % 2 === 0;
  return (
    <Bg dark>
      <AbsoluteFill style={{ padding: "0 160px", justifyContent: "center" }}>
        <Reveal at={0.2}><Badge dark dot>Every student knows this moment</Badge></Reveal>
        <div style={{ height: 40 }} />
        <Words text="11 pm. One exercise. Stuck. Alone." at={1.0} step={0.42} size={150} color="#fff" maxWidth={1600} highlight={["Alone"]} />
        <Reveal at={3.6} style={{ marginTop: 30 }}>
          <Lead light size={36}>x² − 5x + 6 = 0<span style={{ opacity: caret ? 1 : 0, color: T.acc2 }}> |</span></Lead>
        </Reveal>
        <Reveal at={6.4} style={{ marginTop: 40 }}><H size={76} color={T.acc2}>That ends today.</H></Reveal>
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
  const dim = interpolate(frame, [5.6 * fps, 6.6 * fps], [0, 0.8], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
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
      <Caption at={0.8} out={4.4}>Chatbots hand you the answer in 3 seconds.</Caption>
      <Caption at={4.8}>You learn nothing. Education deserves better.</Caption>
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
        <Reveal at={0}><Badge dark dot>PISA 2022 · France · mathematics</Badge></Reveal>
        <div style={{ display: "flex", alignItems: "baseline", gap: 40, marginTop: 30 }}>
          <div style={{ font: `500 360px/.9 ${FONT.head}`, letterSpacing: "-.07em", color: "#fff", opacity: p, filter: `blur(${(1 - p) * 10}px)` }}>{n}</div>
          <Reveal at={2.2}><div style={{ font: `500 72px ${FONT.head}`, letterSpacing: "-.04em", color: T.acc2 }}>−21 pts</div></Reveal>
        </div>
        <Reveal at={2.6} style={{ marginTop: 30 }}>
          <Lead light size={36}>A historic low. Private tutors cost a fortune. <b style={{ color: "#fff" }}>Until now.</b><br /><span style={{ color: "rgba(255,255,255,.4)", fontSize: 22 }}>OECD · PISA 2022 · average maths score, −21 pts vs 2018</span></Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};

