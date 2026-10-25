import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/** Pitch-deck DA (pitch/deck.css): paper, ink, pale yellow, Google Sans Flex + Abel. */
export const D = {
  paper: "#F7F6F3",
  paper2: "#EEEDE9",
  ink: "#262626",
  muted: "#7a7a77",
  line: "rgba(38,38,38,.1)",
  yellow: "#FFFDBD",
  yellow2: "#F3EA7A",
  dark: "#161616",
  red: "#c0574d",
} as const;
export const SANS = "Google Sans Flex, system-ui, sans-serif";
export const LABEL = "Abel, sans-serif";
const ease = Easing.bezier(0.2, 0.7, 0.2, 1);

export const useR = (at: number, dur = 0.8) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return interpolate(frame, [at * fps, (at + dur) * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
};

/** Deck `.r` reveal: blur → sharp, 14 px rise. */
export const R: React.FC<{ at?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ at = 0, children, style }) => {
  const p = useR(at);
  return <div style={{ opacity: p, filter: `blur(${(1 - p) * 10}px)`, translate: `0 ${(1 - p) * 14}px`, ...style }}>{children}</div>;
};

export const Slide: React.FC<{ children: React.ReactNode; dark?: boolean; style?: React.CSSProperties }> = ({ children, dark, style }) => (
  <div style={{ position: "absolute", inset: 0, background: dark ? D.dark : D.paper, color: dark ? D.paper : D.ink, fontFamily: SANS, padding: "120px 150px 140px", display: "flex", flexDirection: "column", justifyContent: "center", overflow: "hidden", ...style }}>{children}</div>
);

export const Eyebrow: React.FC<{ children: React.ReactNode; light?: boolean; at?: number }> = ({ children, light, at = 0 }) => (
  <R at={at} style={{ display: "flex", alignItems: "center", gap: 12, font: `22px ${LABEL}`, letterSpacing: ".06em", textTransform: "uppercase", color: light ? "rgba(247,246,243,.55)" : D.muted, marginBottom: 34 }}>
    <span style={{ width: 16, height: 16, borderRadius: 4, background: light ? D.yellow : D.ink, display: "inline-block" }} />{children}
  </R>
);

export const H2: React.FC<{ children: React.ReactNode; at?: number; size?: number; style?: React.CSSProperties }> = ({ children, at = 0.1, size = 84, style }) => (
  <R at={at} style={{ fontSize: size, lineHeight: 1.02, letterSpacing: "-.045em", fontWeight: 500, maxWidth: 1500, marginBottom: 64, ...style }}>{children}</R>
);

export const Em: React.FC<{ children: React.ReactNode }> = ({ children }) => <span style={{ color: D.muted }}>{children}</span>;

export const Card: React.FC<{ num?: string; title: React.ReactNode; children?: React.ReactNode; at?: number; dark?: boolean; icon?: boolean }> = ({ num, title, children, at = 0, dark, icon }) => (
  <R at={at}>
    <div style={{ background: dark ? D.dark : "#fff", color: dark ? D.paper : D.ink, border: `1px solid ${D.line}`, borderRadius: 28, padding: 38, height: "100%" }}>
      {num && <span style={{ display: "block", font: `22px ${LABEL}`, color: D.muted, marginBottom: 46 }}>{num}</span>}
      {icon && <span style={{ display: "block", width: 64, height: 64, borderRadius: 18, background: D.yellow, marginBottom: 46, position: "relative" }}><span style={{ position: "absolute", inset: 18, border: `3px solid ${D.ink}`, borderRadius: "50%" }} /></span>}
      <div style={{ fontSize: 34, letterSpacing: "-.03em", fontWeight: 500 }}>{title}</div>
      {children && <p style={{ margin: "16px 0 0", fontSize: 24, lineHeight: 1.35, color: dark ? "rgba(247,246,243,.6)" : "#5e5e5b" }}>{children}</p>}
    </div>
  </R>
);

export const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span style={{ font: `500 22px ${SANS}`, padding: "10px 18px", borderRadius: 12, background: D.dark, color: D.paper, boxShadow: "0 4px 0 #000" }}>{children}</span>
);

export const Mark: React.FC<{ size?: number; color?: string }> = ({ size = 40, color = D.ink }) => (
  <svg viewBox="0 0 40 24" width={size} height={size * 0.6} fill={color} style={{ display: "block" }}><rect x="2" y="2" width="10" height="20" rx="5" /><circle cx="27" cy="12" r="10" /></svg>
);

export const Notch: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const pulse = 0.6 + 0.4 * Math.abs(Math.sin(frame / 18));
  return (
    <div style={{ position: "absolute", top: 0, left: "50%", translate: "-50% 0", height: 64, padding: "0 34px", borderRadius: "0 0 26px 26px", background: D.dark, color: D.paper, display: "flex", alignItems: "center", gap: 14, fontSize: 22, fontFamily: SANS }}>
      <span style={{ width: 10, height: 10, borderRadius: "50%", background: D.yellow, boxShadow: `0 0 0 ${pulse * 10}px rgba(255,253,189,${0.5 - pulse * 0.4})` }} />{text}
    </div>
  );
};

/** Caption pill (dark on paper, paper on dark) for the demo clips. */
export const Cap: React.FC<{ at: number; out?: number; children: React.ReactNode }> = ({ at, out, children }) => {
  const p = useR(at, 0.5);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const o = out === undefined ? 1 : interpolate(frame, [out * fps, (out + 0.3) * fps], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 0, right: 0, bottom: 70, display: "flex", justifyContent: "center", opacity: p * o, translate: `0 ${(1 - p) * 16}px` }}>
      <div style={{ padding: "14px 28px", borderRadius: 999, background: D.dark, color: D.paper, font: `500 30px ${SANS}`, letterSpacing: "-.02em" }}>{children}</div>
    </div>
  );
};

export const Counter: React.FC<{ from: number; to: number; at: number; dur?: number; suffix?: string; style?: React.CSSProperties }> = ({ from, to, at, dur = 1.6, suffix = "", style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = Math.round(interpolate(frame, [at * fps, (at + dur) * fps], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  return <span style={style}>{n}{suffix}</span>;
};
