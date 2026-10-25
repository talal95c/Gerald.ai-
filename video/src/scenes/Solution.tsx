import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Badge, Brand, Bg, Bubble, Caption, Circled, GeraldCursor, H, Hand, Keycap, Orb, Reveal, Stage, TalkPill, Tick, useGlide, useP } from "../ui";
import { Footage } from "../footage";
import { FONT, T } from "../theme";

/** Scene · Meet Gerald — brand + the hero claim. */
export const Meet: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const press = interpolate(frame, [2.9 * fps, 3.05 * fps, 4.2 * fps, 4.35 * fps], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const brand = useP(0, 1.0);
  return (
    <Bg>
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
        <div style={{ opacity: brand, scale: `${0.85 + 0.15 * brand}`, filter: `blur(${(1 - brand) * 12}px)` }}><Brand size={120} /></div>
        <Reveal at={0.9} style={{ marginTop: 40 }}><Badge dot>The world's first tutor that lives on your screen</Badge></Reveal>
        <Reveal at={1.2} style={{ marginTop: 30 }}><H size={100}>It sees. It talks. It draws.<br />You finally learn.</H></Reveal>
        <Reveal at={2.4} style={{ marginTop: 40, display: "flex", alignItems: "center", gap: 14, font: `30px ${FONT.body}`, color: T.mut }}>
          <Orb size={26} /> Hold <Keycap label="Ctrl" pressed={press} size={30} /> + <Keycap label="Shift" pressed={press} size={30} /> and speak
        </Reveal>
      </AbsoluteFill>
    </Bg>
  );
};

/** The landing hero board, replayed as a timed sequence (seconds relative to scene). */
const BoardMock: React.FC = () => {
  const cur = useGlide([
    { t: 0, x: 1000, y: 560 },
    { t: 3.6, x: 1000, y: 560 },
    { t: 4.6, x: 350, y: 292 },
    { t: 8.4, x: 350, y: 292 },
    { t: 9.3, x: 700, y: 470 },
  ]);
  return (
    <div style={{ position: "absolute", inset: 0, backgroundColor: "rgba(255,255,255,.92)", backgroundImage: "radial-gradient(rgba(0,0,0,.13) 1.6px,transparent 1.9px)", backgroundSize: "34px 34px", borderRadius: 24, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 22, top: "50%", translate: "0 -50%", display: "flex", flexDirection: "column", gap: 14, padding: "14px 12px", borderRadius: 18, background: "#fff", border: `1px solid ${T.line}` }}>
        {["#111", T.blue, T.red].map((c) => <i key={c} style={{ width: 30, height: 30, borderRadius: "50%", background: c, boxShadow: "inset 0 0 0 3px #fff" }} />)}
        <i style={{ width: 30, height: 30, borderRadius: 9, background: "#eef0f4" }} />
      </div>
      <div style={{ position: "absolute", right: 24, top: 24, padding: "14px 20px", borderRadius: 16, background: "#fff", border: `1px solid ${T.line}`, font: `22px ${FONT.body}` }}>
        <div style={{ fontSize: 15, color: T.mut, textTransform: "uppercase", letterSpacing: ".06em" }}>TD 4 · Exercise 1</div>
        <b style={{ fontWeight: 600 }}>Solve x² − 5x + 6 = 0</b>
      </div>
      <div style={{ position: "absolute", left: 120, top: 90, display: "flex", flexDirection: "column", gap: 14 }}>
        <Hand at={0.4} size={52}>a = 1, b = −5, c = 6</Hand>
        <Hand at={1.6} size={52}>Δ = b² − 4ac</Hand>
        <Hand at={2.8} size={52}>Δ = 25 <Circled at={4.7}>+ 24</Circled> = 49</Hand>
        <Hand at={6.6} dur={0.9} size={44} color={T.violet} style={{ marginLeft: 140, marginTop: -6 }}>− 24 → Δ = 1</Hand>
        <Hand at={8.0} size={52}>x₁ = 2 &nbsp; x₂ = 3 <Tick at={9.4} /></Hand>
      </div>
      <Bubble at={5.3} out={8.6} x={620} y={250}>Careful: it's <b>minus</b> 4ac. 4 × 1 × 6 = 24.</Bubble>
      <Bubble at={9.6} x={760} y={420} ok>Bravo! Both roots are right.</Bubble>
      <GeraldCursor x={cur.x} y={cur.y} />
      <div style={{ position: "absolute", left: "50%", bottom: 22, translate: "-50% 0" }}><TalkPill size={20} active /></div>
    </div>
  );
};

/** Scene · Gerald sees, circles, speaks — on the board. */
export const Board: React.FC<{ footage: string | null }> = ({ footage }) => {
  const p = useP(0, 1.0);
  return (
    <Bg>
      <Stage style={{ left: 120, right: 120, top: 70, bottom: 190, opacity: p, scale: `${0.97 + 0.03 * p}` }}>
        <div style={{ position: "absolute", left: 70, right: 70, top: 50, bottom: 50, borderRadius: 24, boxShadow: "0 40px 80px -40px rgba(30,40,120,.5)" }}>
          <Footage src={footage} label="board recording"><BoardMock /></Footage>
        </div>
      </Stage>
      <Caption at={0.8} out={4.2}>You write. Gerald watches every line.</Caption>
      <Caption at={4.6} out={8.4}>It circles the mistake — and explains it out loud.</Caption>
      <Caption at={8.8}>Like the best teacher you ever had. Right next to you.</Caption>
    </Bg>
  );
};

/** Fake desktop with a Photoshop-like window; Gerald points at tools step by step. */
const PhotoshopMock: React.FC = () => {
  const cur = useGlide([
    { t: 0, x: 900, y: 520 },
    { t: 1.4, x: 900, y: 520 },
    { t: 2.3, x: 76, y: 236 },
    { t: 5.0, x: 76, y: 236 },
    { t: 5.9, x: 1272, y: 180 },
    { t: 8.4, x: 1272, y: 180 },
    { t: 9.2, x: 640, y: 420 },
  ]);
  const rect = useP(3.9, 0.9, Easing.inOut(Easing.cubic));
  const fill = useP(7.6, 0.5);
  const tools = ["▭", "✥", "⌖", "⟋", "✎", "T", "◐", "⬚"];
  const ring = (on: boolean) => (on ? `0 0 0 4px ${T.acc}, 0 0 0 10px rgba(61,43,255,.25)` : "none");
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  return (
    <div style={{ position: "absolute", inset: 0, background: "#2b2b2f", borderRadius: 18, overflow: "hidden", color: "#ddd", font: `16px ${FONT.body}` }}>
      <div style={{ height: 44, display: "flex", alignItems: "center", gap: 22, padding: "0 18px", background: "#1e1e22", borderBottom: "1px solid #000" }}>
        <span style={{ width: 24, height: 24, borderRadius: 5, background: "#001e36", color: "#31a8ff", display: "grid", placeItems: "center", font: "700 12px sans-serif" }}>Ps</span>
        {["File", "Edit", "Image", "Layer", "Select", "Filter", "View"].map((m) => <span key={m} style={{ opacity: 0.8 }}>{m}</span>)}
      </div>
      <div style={{ position: "absolute", left: 14, top: 70, display: "flex", flexDirection: "column", gap: 6, padding: 8, background: "#1e1e22", borderRadius: 10 }}>
        {tools.map((x, i) => <span key={i} style={{ width: 40, height: 40, display: "grid", placeItems: "center", borderRadius: 8, background: i === 0 && t > 3.6 ? "#3d3d44" : "transparent", boxShadow: ring(i === 0 && t > 2.3 && t < 5.0), fontSize: 20 }}>{x}</span>)}
      </div>
      <div style={{ position: "absolute", left: 110, right: 240, top: 80, bottom: 30, background: "#3a3a40", display: "grid", placeItems: "center" }}>
        <div style={{ width: 900, height: 560, background: "#fff", position: "relative", boxShadow: "0 20px 60px rgba(0,0,0,.5)" }}>
          <div style={{ position: "absolute", left: 230, top: 150, width: 440 * rect, height: 260 * rect, border: `2px ${fill > 0 ? "solid" : "dashed"} ${fill > 0 ? T.acc : "#333"}`, background: `rgba(61,43,255,${fill})` }} />
        </div>
      </div>
      <div style={{ position: "absolute", right: 14, top: 70, width: 210, padding: 12, background: "#1e1e22", borderRadius: 10 }}>
        <div style={{ opacity: 0.6, marginBottom: 10 }}>Color</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 8 }}>
          {["#111", "#e11d48", "#f59e0b", "#16a34a", T.acc, "#7c3aed", "#fff", "#94a3b8", "#0ea5e9", "#f472b6"].map((c, i) => <span key={c} style={{ width: 32, height: 32, borderRadius: 6, background: c, boxShadow: ring(i === 4 && t > 5.9 && t < 8.4) }} />)}
        </div>
        <div style={{ opacity: 0.6, margin: "18px 0 10px" }}>Layers</div>
        {["Rectangle 1", "Background"].map((l, i) => <div key={l} style={{ padding: "8px 10px", borderRadius: 6, background: i === 0 ? "#3d3d44" : "transparent", opacity: i === 0 && rect === 0 ? 0 : 1 }}>{l}</div>)}
      </div>
      <Bubble at={0.3} out={2.2} x={560} y={110} size={20}>A rectangle? Start with the shape tool.</Bubble>
      <Bubble at={2.6} out={5.0} x={140} y={200} size={20}>This one. Click it, then drag on the canvas.</Bubble>
      <Bubble at={6.0} out={8.6} x={880} y={120} size={20}>Good. Now choose a colour in the swatches.</Bubble>
      <Bubble at={9.2} x={520} y={380} size={20} ok>Your rectangle is blue. Your turn.</Bubble>
      <GeraldCursor x={cur.x} y={cur.y} />
    </div>
  );
};

/** Scene · Any app — the fake desktop with Photoshop, guided by voice. */
export const Desktop: React.FC<{ footage: string | null }> = ({ footage }) => {
  const p = useP(0, 1.0);
  return (
    <Bg>
      <Reveal at={0} style={{ position: "absolute", left: 120, top: 60 }}><Badge dot>Any app · Windows first</Badge></Reveal>
      <div style={{ position: "absolute", left: 120, right: 120, top: 130, bottom: 190, borderRadius: 24, background: "linear-gradient(135deg,#dfe8ff,#eef1f8)", border: `1px solid ${T.line}`, boxShadow: "0 40px 80px -40px rgba(30,40,120,.4)", opacity: p, scale: `${0.97 + 0.03 * p}`, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 60, right: 60, top: 40, bottom: 40, borderRadius: 18, boxShadow: "0 30px 60px -30px rgba(0,0,0,.6)" }}>
          <Footage src={footage} label="photoshop recording"><PhotoshopMock /></Footage>
        </div>
      </div>
      <Caption at={0.6} out={3.6}>One key. Any app. Gerald sees what you see.</Caption>
      <Caption at={4.0} out={7.2}>It points. You click. It checks.</Caption>
      <Caption at={7.6}>Design, code, maths — anything.</Caption>
    </Bg>
  );
};

/** TD + board side by side (placeholder for the real TD recording). */
const TdMock: React.FC = () => {
  const cur = useGlide([
    { t: 0, x: 760, y: 500 },
    { t: 0.8, x: 760, y: 500 },
    { t: 1.5, x: 330, y: 318 },
    { t: 3.2, x: 330, y: 318 },
    { t: 3.9, x: 1100, y: 360 },
  ]);
  const plot = useP(4.0, 1.4, Easing.inOut(Easing.cubic));
  const under = useP(1.6, 0.6);
  const pts = Array.from({ length: 61 }, (_, i) => {
    const x = -0.6 + (i / 60) * 6.2;
    return [x, x * x - 5 * x + 6] as const;
  });
  const sx = (x: number) => 80 + (x + 0.6) * (420 / 6.2);
  const sy = (y: number) => 300 - y * 28;
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(x).toFixed(1)} ${sy(y).toFixed(1)}`).join(" ");
  return (
    <div style={{ position: "absolute", inset: 0, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, padding: 24, background: T.bg, borderRadius: 24 }}>
      <div style={{ background: "#fff", borderRadius: 18, border: `1px solid ${T.line}`, padding: "40px 46px", fontFamily: "Georgia, serif", color: "#222", position: "relative" }}>
        <div style={{ fontSize: 14, letterSpacing: ".1em", textTransform: "uppercase", color: "#888" }}>TD 4 · Polynômes du second degré</div>
        <div style={{ fontSize: 30, marginTop: 18, fontWeight: 700 }}>Exercice 1</div>
        <p style={{ fontSize: 22, lineHeight: 1.55, marginTop: 14 }}>Résoudre dans ℝ l'équation <i>x² − 5x + 6 = 0</i>. On calculera d'abord le discriminant <span style={{ position: "relative" }}>Δ = b² − 4ac<span style={{ position: "absolute", left: 0, bottom: -4, height: 3, width: `${under * 100}%`, background: T.violet, borderRadius: 3 }} /></span>, puis les racines.</p>
        <div style={{ fontSize: 30, marginTop: 30, fontWeight: 700 }}>Exercice 2</div>
        <p style={{ fontSize: 22, lineHeight: 1.55, marginTop: 14 }}>Même question pour 2x² + 3x − 2 = 0.</p>
        <Bubble at={1.8} out={3.8} x={60} y={330} size={20}>Start with Δ. What are a, b and c here?</Bubble>
      </div>
      <div style={{ position: "relative", borderRadius: 18, border: `1px solid ${T.line}`, backgroundColor: "#fff", backgroundImage: "radial-gradient(rgba(0,0,0,.13) 1.4px,transparent 1.7px)", backgroundSize: "30px 30px", overflow: "hidden" }}>
        <svg viewBox="0 0 580 420" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          <path d={`M${sx(-0.6)} ${sy(0)} H${sx(5.6)} M${sx(0)} 40 V400`} stroke="#c9cfdb" strokeWidth={1.5} fill="none" />
          <path d={d} fill="none" stroke={T.acc} strokeWidth={3.5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - plot} strokeLinecap="round" />
          {[2, 3].map((r) => <circle key={r} cx={sx(r)} cy={sy(0)} r={6 * Math.max(0, (plot - 0.85) / 0.15)} fill={T.acc} />)}
          <text x={sx(2) - 8} y={sy(0) + 28} fontFamily={FONT.body} fontSize={18} fill={T.ink} opacity={plot > 0.95 ? 1 : 0}>2</text>
          <text x={sx(3) - 6} y={sy(0) + 28} fontFamily={FONT.body} fontSize={18} fill={T.ink} opacity={plot > 0.95 ? 1 : 0}>3</text>
        </svg>
        <div style={{ position: "absolute", left: 20, top: 16, font: `16px ${FONT.body}`, color: T.mut }}>Board · y = x² − 5x + 6</div>
      </div>
      <GeraldCursor x={cur.x} y={cur.y} />
    </div>
  );
};

/** Scene · Your course, your worksheets — the board opens when it helps. */
export const Td: React.FC<{ footage: string | null }> = ({ footage }) => {
  const p = useP(0, 1.0);
  return (
    <Bg>
      <Reveal at={0} style={{ position: "absolute", left: 120, top: 60 }}><Badge>Your courses · the board</Badge></Reveal>
      <div style={{ position: "absolute", left: 120, right: 120, top: 130, bottom: 190, borderRadius: 24, boxShadow: "0 40px 80px -40px rgba(30,40,120,.4)", opacity: p, scale: `${0.97 + 0.03 * p}` }}>
        <Footage src={footage} label="TD + board recording"><TdMock /></Footage>
      </div>
      <Caption at={0.6} out={3.4}>Drop your courses. Gerald learns them.</Caption>
      <Caption at={3.8}>The exact curve, plotted live on your board.</Caption>
    </Bg>
  );
};

