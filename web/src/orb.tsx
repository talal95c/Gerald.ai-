import React, { useEffect, useRef } from "react";

const N = 72;
const sides: Record<string, number> = {listening: 0, thinking: 3, speaking: 4};

function radius(theta: number, n: number) {
  if (!n) return 1;
  const seg = 2 * Math.PI / n;
  const local = ((theta % seg) + seg) % seg - seg / 2;
  const polygon = Math.cos(Math.PI / n) / Math.cos(local);
  return 0.72 * polygon + 0.28;
}

function shape(n: number, rot: number) {
  return Array.from({length: N}, (_, i) => radius(i / N * 2 * Math.PI - rot, n));
}

function path(radii: number[], size: number, scale: number, t: number, wobble: number) {
  const c = size / 2, base = size * 0.4 * scale;
  const pts = radii.map((r, i) => {
    const a = i / N * 2 * Math.PI;
    const w = 1 + wobble * (Math.sin(a * 3 + t * 2.1) * 0.6 + Math.sin(a * 2 - t * 1.3) * 0.4);
    return [c + Math.cos(a) * base * r * w, c + Math.sin(a) * base * r * w];
  });
  let d = `M${((pts[N - 1][0] + pts[0][0]) / 2).toFixed(2)},${((pts[N - 1][1] + pts[0][1]) / 2).toFixed(2)}`;
  pts.forEach((p, i) => { const q = pts[(i + 1) % N]; d += `Q${p[0].toFixed(2)},${p[1].toFixed(2)} ${((p[0] + q[0]) / 2).toFixed(2)},${((p[1] + q[1]) / 2).toFixed(2)}`; });
  return d + "Z";
}

export function Orb({status, size = 26}: {status: string; size?: number}) {
  const halo = useRef<SVGPathElement>(null), core = useRef<SVGPathElement>(null);
  const target = useRef(status);
  target.current = status;
  useEffect(() => {
    const n0 = sides[target.current] ?? 0;
    let current = shape(n0, -Math.PI / 2), frame = 0, t = 0, last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt;
      const s = target.current, n = sides[s] ?? 0;
      const goal = shape(n, -Math.PI / 2 + (n === 4 ? Math.PI / 4 : 0) + (s === "thinking" ? t * 0.9 : 0));
      const k = 1 - Math.exp(-dt * 9);
      current = current.map((r, i) => r + (goal[i] - r) * k);
      const pulse = s === "listening" ? 1 + Math.sin(t * 5) * 0.05 : s === "speaking" ? 1 + Math.abs(Math.sin(t * 7)) * 0.07 : 1 + Math.sin(t * 1.6) * 0.025;
      const wobble = s === "listening" ? 0.035 : s === "speaking" ? 0.02 : 0.012;
      halo.current?.setAttribute("d", path(current, size, 1.08 * pulse, t, wobble * 1.8));
      core.current?.setAttribute("d", path(current, size, 0.74 * pulse, t + 1, wobble));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [size]);
  const id = `orb${size}`;
  return <svg style={{overflow:"visible", flex:"none"}} className={`orb o-${status}`} width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
    <defs>
      <linearGradient id={`${id}h`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#6F7BFF"/><stop offset=".55" stopColor="#B9A6FF"/><stop offset="1" stopColor="#F3C9F2"/></linearGradient>
      <radialGradient id={`${id}c`} cx=".35" cy=".3" r=".9"><stop offset="0" stopColor="#F4F2FF"/><stop offset=".6" stopColor="#C9C3FF"/><stop offset="1" stopColor="#A9A2F5"/></radialGradient>
      <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation={size * 0.035}/></filter>
    </defs>
    <path ref={halo} fill={`url(#${id}h)`} filter={`url(#${id}b)`} opacity=".95"/>
    <path ref={core} fill={`url(#${id}c)`} stroke="rgba(255,255,255,.85)" strokeWidth={size * 0.03}/>
  </svg>;
}
