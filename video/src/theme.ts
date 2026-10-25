/** Landing DA (web/src/landing.css). */
export const T = {
  bg: "#f9f9f9",
  ink: "#0a0a0b",
  mut: "rgba(0,0,0,.62)",
  mut2: "rgba(0,0,0,.45)",
  line: "rgba(0,0,0,.08)",
  acc: "#3d2bff",
  acc2: "#5b7cff",
  soft: "#eef1f8",
  dark: "#111113",
  paper: "#ffffff",
  red: "#e11d48",
  green: "#16a34a",
  blue: "#2563eb",
  violet: "#7c3aed",
  yellow: "#F3EA7A",
} as const;

/** The landing hero "stage" gradient. */
export const STAGE_BG =
  "repeating-linear-gradient(135deg,rgba(255,255,255,.5) 0 1px,transparent 1px 4px),radial-gradient(120% 90% at 85% 10%,#e8f3ff 0,transparent 55%),radial-gradient(90% 80% at 10% 100%,#dcd6ff 0,transparent 60%),linear-gradient(135deg,#bfe0ff,#8cc4ff 45%,#a9b6ff)";

export const FONT = {
  head: "Google Sans Flex, Geist, system-ui, sans-serif",
  body: "Geist, system-ui, sans-serif",
  hand: "Caveat, cursive",
} as const;

export const EASE = [0.2, 0.8, 0.2, 1] as const;
