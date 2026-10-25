import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Bg, Brand, Btn, H, Keycap, Lead, Orb, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

/** Scene · Trust & proof — three facts. */
export const Proof: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const score = Math.round(interpolate(frame, [1.6 * fps, 3.4 * fps], [77, 92], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  const cards: { h: React.ReactNode; p: string }[] = [
    { h: <>{score} %</>, p: "pedagogy score, measured on 17 real scenarios with an AI judge — up from 77 %." },
    { h: <span style={{ fontSize: 64 }}>Real-time</span>, p: "voice and vision in one stream. Ask, point, draw — it answers out loud while it draws." },
    { h: <span style={{ fontSize: 64 }}>Private</span>, p: "sees your screen only while you hold the key. Open source, MIT." },
  ];
  return (
    <Bg>
      <AbsoluteFill style={{ padding: "0 120px", justifyContent: "center" }}>
        <Reveal at={0}><Badge dot>Not a chatbot</Badge></Reveal>
        <Reveal at={0.15} style={{ marginTop: 22 }}><H size={78}>A revolution in learning.<br />For every student. Any screen.</H></Reveal>
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
  const press = interpolate(frame, [2.4 * fps, 2.55 * fps, 3.4 * fps, 3.55 * fps], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const brand = useP(0.1, 1.1);
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <div style={{ opacity: brand, scale: `${0.9 + 0.1 * brand}`, filter: `blur(${(1 - brand) * 10}px)` }}><Brand size={96} /></div>
        <div style={{ marginTop: 44 }}>
          <Words text="Never be stuck again." at={0.6} step={0.12} size={120} align="center" maxWidth={1500} highlight={["again"]} />
          <Reveal at={1.6} style={{ marginTop: 22, textAlign: "center" }}><Lead size={38}>It doesn't give you the answer. It helps you find it.</Lead></Reveal>
        </div>
        <Reveal at={2.0} style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 14, font: `28px ${FONT.body}`, color: T.mut }}>
          <Orb size={24} /> Hold <Keycap label="Ctrl" pressed={press} /> + <Keycap label="Shift" pressed={press} /> and ask out loud
        </Reveal>
        <Reveal at={2.6} style={{ marginTop: 46, display: "flex", gap: 16 }}>
          <Btn>Try the demo</Btn><Btn primary>Learn live →</Btn>
        </Reveal>
        <Reveal at={3.2} style={{ position: "absolute", bottom: 70 }}>
          <Lead size={24}>github.com/talal95c/Gerald.ai- · Any app · Windows first · open source (MIT)</Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};
