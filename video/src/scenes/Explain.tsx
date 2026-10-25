import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Bg, Brand, Btn, Keycap, Lead, Orb, Reveal, Words, useP } from "../ui";
import { FONT, T } from "../theme";

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
          <Words text="Ne restez plus jamais bloqué." at={0.6} step={0.12} size={116} align="center" maxWidth={1600} highlight={["jamais"]} />
          <Reveal at={1.6} style={{ marginTop: 22, textAlign: "center" }}><Lead size={38}>Il ne donne pas la réponse. Il vous aide à la trouver.</Lead></Reveal>
        </div>
        <Reveal at={2.0} style={{ marginTop: 44, display: "flex", alignItems: "center", gap: 14, font: `28px ${FONT.body}`, color: T.mut }}>
          <Orb size={24} /> Maintenez <Keycap label="Ctrl" pressed={press} /> + <Keycap label="Shift" pressed={press} /> et posez votre question
        </Reveal>
        <Reveal at={2.6} style={{ marginTop: 46, display: "flex", gap: 16 }}>
          <Btn>Essayer la démo</Btn><Btn primary>Apprendre en live →</Btn>
        </Reveal>
        <Reveal at={3.2} style={{ position: "absolute", bottom: 70 }}>
          <Lead size={24}>github.com/talal95c/Gerald.ai- · toutes vos applis · Windows d'abord · open source (MIT)</Lead>
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};
