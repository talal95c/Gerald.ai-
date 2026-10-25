import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { EASE, FONT, STAGE_BG, T } from "./theme";

export const ease = Easing.bezier(...EASE);

/** 0→1 between `at` and `at+dur` seconds, clamped, landing easing. */
export const useP = (at: number, dur = 0.8, e: ((n: number) => number) | undefined = ease) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return interpolate(frame, [at * fps, (at + dur) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: e });
};

export const Bg: React.FC<{ children: React.ReactNode; dark?: boolean; style?: React.CSSProperties }> = ({ children, dark, style }) => (
  <div style={{ position: "absolute", inset: 0, background: dark ? T.dark : T.bg, color: dark ? "#fff" : T.ink, fontFamily: FONT.body, overflow: "hidden", ...style }}>{children}</div>
);

/** The landing hero gradient panel. */
export const Stage: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ position: "absolute", borderRadius: 28, background: STAGE_BG, overflow: "hidden", display: "grid", placeItems: "center", ...style }}>{children}</div>
);

/** Blur-to-sharp reveal (landing `.pop`). Seconds relative to the scene. */
export const Reveal: React.FC<{ at?: number; dur?: number; out?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at = 0, dur = 0.9, out, children, style }) => {
  const p = useP(at, dur);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const o = out === undefined ? 1 : interpolate(frame, [out * fps, (out + 0.4) * fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <div style={{ opacity: p * o, filter: `blur(${(1 - p) * 8}px)`, translate: `0 ${(1 - p) * 16}px`, ...style }}>{children}</div>;
};

export const Badge: React.FC<{ children: React.ReactNode; dot?: boolean; dark?: boolean }> = ({ children, dot, dark }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 12, height: 48, padding: "0 20px", border: `1px solid ${dark ? "rgba(255,255,255,.18)" : "rgba(0,0,0,.12)"}`, borderRadius: 999, background: dark ? "rgba(255,255,255,.06)" : "#fff", fontSize: 22, fontFamily: FONT.body, color: dark ? "#fff" : T.ink }}>
    {dot && <span style={{ width: 12, height: 12, borderRadius: "50%", background: T.acc, boxShadow: "0 0 0 6px rgba(61,43,255,.15)" }} />}
    {children}
  </span>
);

export const H: React.FC<{ children: React.ReactNode; size?: number; style?: React.CSSProperties; color?: string }> = ({ children, size = 96, style, color }) => (
  <div style={{ fontFamily: FONT.head, fontWeight: 500, fontSize: size, lineHeight: 1.06, letterSpacing: "-.035em", color, ...style }}>{children}</div>
);

export const Lead: React.FC<{ children: React.ReactNode; size?: number; style?: React.CSSProperties; light?: boolean }> = ({ children, size = 30, style, light }) => (
  <div style={{ fontFamily: FONT.body, fontSize: size, lineHeight: 1.45, color: light ? "rgba(255,255,255,.7)" : T.mut, ...style }}>{children}</div>
);

export const Keycap: React.FC<{ label: string; pressed?: number; size?: number; dark?: boolean }> = ({ label, pressed = 0, size = 28, dark }) => (
  <span style={{ display: "inline-block", font: `500 ${size}px ${FONT.body}`, padding: `${size * 0.3}px ${size * 0.6}px`, borderRadius: size * 0.4, background: dark ? T.ink : "#fff", color: dark ? "#fff" : T.ink, border: `1px solid ${dark ? "#000" : "rgba(0,0,0,.12)"}`, boxShadow: `0 ${4 * (1 - pressed)}px 0 ${dark ? "#000" : "rgba(0,0,0,.12)"}`, translate: `0 ${4 * pressed}px` }}>{label}</span>
);

export const Orb: React.FC<{ size?: number }> = ({ size = 16 }) => {
  const frame = useCurrentFrame();
  const s = 1 + 0.07 * Math.sin(frame / 14);
  return <span style={{ display: "inline-block", flex: "none", width: size, height: size, borderRadius: "50%", background: "radial-gradient(circle at 35% 30%,#fff 0,#d9c8ff 18%,#8b5cf6 55%,#4c1d95 100%)", boxShadow: "0 0 0 3px rgba(139,92,246,.15),0 4px 12px rgba(109,40,217,.35)", scale: `${s}` }} />;
};

export const BrandMark: React.FC<{ size?: number }> = ({ size = 56 }) => (
  <span style={{ display: "grid", placeItems: "center", width: size, height: size, borderRadius: size * 0.32, background: T.ink, flex: "none" }}>
    <svg viewBox="0 0 40 24" width={size * 0.5} height={size * 0.3} fill="#fff"><rect x="2" y="2" width="10" height="20" rx="5" /><circle cx="27" cy="12" r="10" /></svg>
  </span>
);

export const Brand: React.FC<{ size?: number; light?: boolean }> = ({ size = 56, light }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: size * 0.3, fontFamily: FONT.head, fontWeight: 500, fontSize: size * 0.8, letterSpacing: "-.03em", color: light ? "#fff" : T.ink }}>
    <BrandMark size={size} />Gerald
  </span>
);

/** Gerald's pointer: black pill with the orb. Position in px within the parent. */
export const GeraldCursor: React.FC<{ x: number; y: number; scale?: number; opacity?: number }> = ({ x, y, scale = 1, opacity = 1 }) => (
  <div style={{ position: "absolute", left: x, top: y, display: "flex", alignItems: "center", gap: 8, padding: "6px 14px 6px 8px", borderRadius: 999, background: T.ink, color: "#fff", font: `500 18px ${FONT.body}`, boxShadow: "0 10px 30px -10px rgba(0,0,0,.5)", scale: `${scale}`, opacity, transformOrigin: "left top", whiteSpace: "nowrap" }}>
    <Orb size={16} /> Gerald
  </div>
);

/** Interpolate the cursor along keyframes [{t, x, y}] (seconds). */
export const useGlide = (keys: { t: number; x: number; y: number }[]) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ts = keys.map((k) => k.t * fps);
  const es = keys.slice(1).map(() => Easing.bezier(0.4, 0, 0.2, 1));
  return {
    x: interpolate(frame, ts, keys.map((k) => k.x), { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: es }),
    y: interpolate(frame, ts, keys.map((k) => k.y), { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: es }),
  };
};

export const Bubble: React.FC<{ at: number; out?: number; x: number; y: number; ok?: boolean; children: React.ReactNode; size?: number; width?: number }> = ({ at, out, x, y, ok, children, size = 22, width = 460 }) => {
  const p = useP(at, 0.5);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const o = out === undefined ? 1 : interpolate(frame, [out * fps, (out + 0.3) * fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: x, top: y, display: "flex", alignItems: "center", gap: 12, maxWidth: width, padding: "14px 20px", borderRadius: 18, background: "#fff", border: `1px solid ${ok ? "rgba(22,163,74,.35)" : "rgba(124,58,237,.3)"}`, boxShadow: "0 14px 40px -14px rgba(76,29,149,.35)", font: `${size}px/1.3 ${FONT.body}`, color: T.ink, opacity: p * o, translate: `0 ${(1 - p) * 8}px`, scale: `${0.97 + 0.03 * p}`, filter: `blur(${(1 - p) * 4}px)` }}>
      <Orb size={size * 0.9} /><span>{children}</span>
    </div>
  );
};

/** Bottom caption: the "read without sound" layer. */
export const Caption: React.FC<{ at: number; out?: number; children: React.ReactNode; light?: boolean; bottom?: number }> = ({ at, out, children, light, bottom = 96 }) => {
  const p = useP(at, 0.5);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const o = out === undefined ? 1 : interpolate(frame, [out * fps, (out + 0.3) * fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom, display: "flex", justifyContent: "center", opacity: p * o, translate: `0 ${(1 - p) * 20}px`, filter: `blur(${(1 - p) * 6}px)` }}>
      <div style={{ padding: "16px 30px", borderRadius: 999, background: light ? "#fff" : T.ink, color: light ? T.ink : "#fff", font: `500 34px ${FONT.head}`, letterSpacing: "-.02em", boxShadow: "0 20px 50px -20px rgba(0,0,0,.35)" }}>{children}</div>
    </div>
  );
};

/** Headline revealed word by word; `highlight` words get a blue underline after. */
export const Words: React.FC<{ text: string; at?: number; step?: number; size?: number; highlight?: string[]; color?: string; maxWidth?: number; align?: "left" | "center" }> = ({ text, at = 0, step = 0.08, size = 96, highlight = [], color, maxWidth = 1500, align = "left" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");
  const hlAt = at + words.length * step + 0.25;
  return (
    <div style={{ fontFamily: FONT.head, fontWeight: 500, fontSize: size, lineHeight: 1.08, letterSpacing: "-.035em", maxWidth, color, display: "flex", flexWrap: "wrap", justifyContent: align === "center" ? "center" : "flex-start", gap: "0 .24em" }}>
      {words.map((w, i) => {
        const p = interpolate(frame, [(at + i * step) * fps, (at + i * step + 0.7) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
        const hl = highlight.includes(w.replace(/[.,!?]/g, ""));
        const hp = hl ? interpolate(frame, [hlAt * fps, (hlAt + 0.6) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) : 0;
        return (
          <span key={i} style={{ position: "relative", opacity: p, filter: `blur(${(1 - p) * 8}px)`, translate: `0 ${(1 - p) * 14}px` }}>
            {w}
            {hl && <span style={{ position: "absolute", left: 0, bottom: size * 0.02, height: size * 0.06, width: `${hp * 100}%`, borderRadius: 4, background: T.acc }} />}
          </span>
        );
      })}
    </div>
  );
};

/** Handwritten line (Caveat), revealed left to right like a pen (landing `.hw`). */
export const Hand: React.FC<{ at: number; dur?: number; children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties }> = ({ at, dur = 1.1, children, size = 44, color = "#1f2937", style }) => {
  const p = useP(at, dur, Easing.bezier(0.5, 0, 0.3, 1));
  return <div style={{ position: "relative", font: `600 ${size}px/1.2 ${FONT.hand}`, color, whiteSpace: "nowrap", clipPath: `inset(-20% ${(1 - p) * 104}% -20% -4%)`, ...style }}>{children}</div>;
};

/** Hand-drawn ellipse around the children (landing `.circ`). */
export const Circled: React.FC<{ at: number; children: React.ReactNode; color?: string }> = ({ at, children, color = T.violet }) => {
  const p = useP(at, 0.7, Easing.linear);
  return (
    <span style={{ position: "relative", display: "inline-block", padding: "0 8px" }}>
      {children}
      <svg viewBox="0 0 100 50" preserveAspectRatio="none" style={{ position: "absolute", left: -10, top: -8, width: "calc(100% + 20px)", height: "calc(100% + 16px)", overflow: "visible" }}>
        <ellipse cx="50" cy="25" rx="46" ry="21" pathLength={1} fill="none" stroke={color} strokeWidth={3} vectorEffect="non-scaling-stroke" strokeDasharray={1} strokeDashoffset={1 - p} transform="rotate(-4 50 25)" />
      </svg>
    </span>
  );
};

export const Tick: React.FC<{ at: number }> = ({ at }) => {
  const p = useP(at, 0.45, Easing.bezier(0.3, 1.6, 0.5, 1));
  return <span style={{ display: "inline-block", color: T.green, scale: `${p}` }}>✓</span>;
};

export const Btn: React.FC<{ children: React.ReactNode; primary?: boolean; size?: number }> = ({ children, primary, size = 26 }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: 10, height: size * 2.3, padding: `0 ${size * 1.1}px`, borderRadius: 999, fontSize: size, fontWeight: 500, fontFamily: FONT.body, background: primary ? T.acc : "#fff", color: primary ? "#fff" : T.ink, border: primary ? "none" : "1px solid rgba(0,0,0,.12)", boxShadow: primary ? "inset 0 1px 0 rgba(255,255,255,.25),0 10px 30px -10px rgba(61,43,255,.6)" : "none" }}>{children}</span>
);

/** Voice pill (landing `.board-talk`). */
export const TalkPill: React.FC<{ size?: number; active?: boolean }> = ({ size = 18, active }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: size * 0.6, padding: `${size * 0.55}px ${size * 0.9}px`, borderRadius: 999, background: "#fff", border: `1px solid ${T.line}`, font: `${size}px ${FONT.body}`, color: T.mut, whiteSpace: "nowrap" }}>
      <Orb size={size} />
      <span>Hold <Keycap label="Ctrl" size={size * 0.7} /> + <Keycap label="Shift" size={size * 0.7} /> to ask</span>
      <span style={{ display: "flex", gap: 2, alignItems: "center", height: size }}>
        {Array.from({ length: 12 }, (_, i) => <i key={i} style={{ width: 2, height: "100%", borderRadius: 2, background: T.acc, scale: `1 ${active ? 0.25 + 0.75 * Math.abs(Math.sin(frame / 5 + i * 0.7)) : 0.25}` }} />)}
      </span>
    </div>
  );
};
