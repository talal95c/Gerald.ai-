import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import katex from "katex";
import "katex/dist/katex.min.css";
import "./board.css";
import {annotationLeader, annotationSize, arrowEndpoints, createCursorMotion, ellipseCircumference, intentColor, placeAnnotation, segmentBoardText, type AnnotationRect, type BoardTextPart, type CursorVisual} from "./annotations";
import { mountNotch } from "./notch";

type Pt = {x: number; y: number; p: number};
type Stroke = {pts: Pt[]; erase: boolean; color: string};
type Win = {x: number; y: number; w: number; h: number};
type PlotCurveData = {expr: string; label: string; samples: (number[] | null)[]};
type PlotPointData = {label: string; x: number; y: number; x_img: number; y_img: number};
type PlotData = {
  box: number[];
  curves: PlotCurveData[];
  x_range: [number, number];
  y_range: [number, number];
  points: PlotPointData[];
  title?: string;
};
type GeraldText = {id: string; text: string; x: number; y: number; size: number; color: string; html?: string; parts?: Array<BoardTextPart & {html?: string}>};
type BoardMark = {id: string; kind: string; x: number; y: number; w: number; h: number; text: string; color?: string | null; fill?: string | null; target?: AnnotationRect; leader?: boolean; progress?: number};
type BoardSnapshot = {
  plotData: PlotData | null;
  plotBox: Win;
  marks: BoardMark[];
  texts: GeraldText[];
  plotVisible: boolean;
  exerciseRect: DOMRect | null;
};

const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const mathToLatex = (value: string) => value
  .replace(/Δ/gu, "\\Delta ")
  .replace(/²/gu, "^2")
  .replace(/−/gu, "-")
  .replace(/×/gu, "\\times ")
  .replace(/±/gu, "\\pm ")
  .replace(/\*\*/gu, "^")
  .replace(/\*/gu, "\\cdot ")
  .replace(/√\s*\(([^()]*)\)/gu, "\\sqrt{$1}")
  .replace(/√\s*([abcxy0-9]+)/giu, "\\sqrt{$1}")
  .replace(/√/gu, "\\sqrt{}");
const normalizedText = (value: string) => {
  let text = "";
  const starts: number[] = [];
  const ends: number[] = [];
  for (let index = 0; index < value.length;) {
    const char = String.fromCodePoint(value.codePointAt(index)!);
    let normalized = /\s/u.test(char) || char === "^" ? "" : /[²]/u.test(char) ? "2" : /[−‐‑‒–—]/u.test(char) ? "-" : char.normalize("NFKC").toLowerCase();
    for (const unit of normalized) {
      text += unit;
      starts.push(index);
      ends.push(index + char.length);
    }
    index += char.length;
  }
  return {text, starts, ends};
};
const normalizedMatch = (source: string, wanted: string) => {
  const actual = normalizedText(source);
  const query = normalizedText(wanted).text;
  const index = actual.text.indexOf(query);
  return index < 0 || !query ? null : {index: actual.starts[index], end: actual.ends[index + query.length - 1]};
};
const params = new URLSearchParams(location.search);
const liveMode = params.get("live") === "1";
const title = liveMode ? "" : params.get("title") || "Exercice 1";
const lines: string[] = liveMode ? [] : (() => {
  try {
    const value = JSON.parse(params.get("lines") || "[]");
    return Array.isArray(value) && value.every((line) => typeof line === "string") && value.length
      ? value
      : ["Résous dans ℝ : x² − 5x + 6 = 0"];
  } catch {
    return ["Résous dans ℝ : x² − 5x + 6 = 0"];
  }
})();
const serverDemoMode = params.get("voice") === "1";

function niceTicks(min: number, max: number, count = 6) {
  const rough = (max - min) / Math.max(1, count - 1);
  const magnitude = 10 ** Math.floor(Math.log10(rough || 1));
  const fraction = rough / magnitude;
  const step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * magnitude;
  const values: number[] = [];
  for (let value = Math.ceil(min / step) * step; value <= max + step * 0.001; value += step) {
    values.push(Math.abs(value) < step * 0.001 ? 0 : Number(value.toPrecision(10)));
  }
  return values;
}

function formatExpression(expression: string) {
  const superscript = (value: string) => [...value].map((digit) => ({
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺",
  }[digit] ?? digit)).join("");
  return expression.trim()
    .replace(/\*\*\s*([+-]?\d+)/g, (_match, power: string) => superscript(power))
    .replace(/\^([+-]?\d+)/g, (_match, power: string) => superscript(power))
    .replace(/(\d)\s*\*\s*x\b/gi, "$1x")
    .replace(/\s*\*\s*/g, " · ")
    .replace(/-/g, " − ")
    .replace(/\+/g, " + ")
    .replace(/\s+/g, " ")
    .trim();
}

function plotHeader(data: PlotData) {
  return formatExpression(data.title || data.curves.map((curve) => curve.expr).join(" · "));
}

function pointLabelLayout(
  point: PlotPointData,
  points: PlotPointData[],
  sx: (x: number) => number,
  sy: (y: number) => number,
) {
  const roots = points.filter((item) => Math.abs(item.y) < 1e-9).sort((a, b) => a.x - b.x);
  const rootIndex = roots.findIndex((item) => item.x === point.x && item.y === point.y);
  if (rootIndex >= 0) {
    const side = rootIndex % 2 === 0 ? -1 : 1;
    return {
      label: `x = ${Number(point.x.toPrecision(5))}`,
      x: sx(point.x) + side * 8,
      y: sy(point.y) - 12 - Math.floor(rootIndex / 2) * 14,
      anchor: side < 0 ? "end" as const : "start" as const,
    };
  }
  return {label: point.label, x: sx(point.x), y: sy(point.y) + 22, anchor: "middle" as const};
}

function Plot({w, h, data, id}: {w: number; h: number; data: PlotData; id: string}) {
  const pad = {l: 42, r: 14, t: 14, b: 28};
  const gw = Math.max(1, w - pad.l - pad.r), gh = Math.max(1, h - pad.t - pad.b);
  const [xMin, xMax] = data.x_range, [yMin, yMax] = data.y_range;
  const sx = (x: number) => pad.l + (x - xMin) / (xMax - xMin) * gw;
  const sy = (y: number) => pad.t + (yMax - y) / (yMax - yMin) * gh;
  const xTicks = niceTicks(xMin, xMax);
  const yTicks = niceTicks(yMin, yMax);
  const xAxis = sy(yMin <= 0 && yMax >= 0 ? 0 : yMin);
  const yAxis = sx(xMin <= 0 && xMax >= 0 ? 0 : xMin);
  const colors = ["#161616", "#FF9F0A", "#30D158"];
  const pathFor = (curve: PlotCurveData) => {
    let drawing = false;
    return curve.samples.map((sample) => {
      if (!sample || sample.length < 2) {
        drawing = false;
        return "";
      }
      const command = `${drawing ? "L" : "M"}${sx(sample[0]).toFixed(1)},${sy(sample[1]).toFixed(1)}`;
      drawing = true;
      return command;
    }).join("");
  };
  return <svg width={w} height={h} className="plot-svg">
    <defs>
      <marker id={`arr-${id}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M0 0 8 4 0 8z" fill="#262626"/>
      </marker>
      <clipPath id={`graph-${id}`}><rect x={pad.l} y={pad.t} width={gw} height={gh}/></clipPath>
    </defs>
    {xTicks.map((x) => <line key={`x${x}`} x1={sx(x)} x2={sx(x)} y1={pad.t} y2={pad.t + gh} className="grid"/>)}
    {yTicks.map((y) => <line key={`y${y}`} y1={sy(y)} y2={sy(y)} x1={pad.l} x2={pad.l + gw} className="grid"/>)}
    <line x1={pad.l} x2={pad.l + gw} y1={xAxis} y2={xAxis} className="axis" markerEnd={`url(#arr-${id})`}/>
    <line x1={yAxis} x2={yAxis} y1={pad.t + gh} y2={pad.t} className="axis" markerEnd={`url(#arr-${id})`}/>
    {xTicks.filter((x) => x !== 0).map((x) =>
      <text key={`tx${x}`} x={sx(x)} y={xAxis + (xAxis < pad.t + gh ? 15 : -6)} className="tick" textAnchor="middle">{x}</text>)}
    {yTicks.filter((y) => y !== 0).map((y) =>
      <text key={`ty${y}`} x={yAxis - 6} y={sy(y) + 4} className="tick" textAnchor="end">{y}</text>)}
    {data.curves.map((curve, index) =>
      <path key={`${curve.expr}-${index}`} d={pathFor(curve)} className="curve"
        style={{stroke: colors[index % colors.length]}} clipPath={`url(#graph-${id})`} pathLength={1}/>)}
    {data.points.map((point, index) => {
      const label = pointLabelLayout(point, data.points, sx, sy);
      return <g key={`${point.label}-${index}`} className="pt"
      style={{animationDelay: `${0.9 + index * 0.12}s`}}>
      <circle cx={sx(point.x)} cy={sy(point.y)} r="5"/>
      <text x={label.x} y={label.y} textAnchor={label.anchor} className="pt-label">{label.label}</text>
    </g>;
    })}
  </svg>;
}

function PlotWindow({data, initialBox, onClose, onBoxChange}: {
  data: PlotData;
  initialBox: Win;
  onClose: () => void;
  onBoxChange: (box: Win) => void;
}) {
  const [win, setWin] = useState<Win>(initialBox);
  const drag = (kind: "move" | "resize") => (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const start = {px: e.clientX, py: e.clientY, ...win};
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - start.px, dy = ev.clientY - start.py;
      const next = kind === "move"
        ? {...start, x: Math.min(Math.max(0, start.x + dx), innerWidth - start.w), y: Math.min(Math.max(0, start.y + dy), innerHeight - start.h)}
        : {...start, w: Math.min(Math.max(260, start.w + dx), innerWidth - start.x), h: Math.min(Math.max(180, start.h + dy), innerHeight - start.y)};
      setWin(next);
      onBoxChange(next);
    };
    const up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  };
  const header = plotHeader(data);
  return <section className="plot-win" data-gerald-id="400" style={{left: win.x, top: win.y, width: win.w, height: win.h}} onPointerDown={(e) => e.stopPropagation()}>
    <header onPointerDown={drag("move")}><span className="dot" /><span>{header}</span>
      <button onPointerDown={(e) => e.stopPropagation()} onClick={onClose} aria-label="Fermer la courbe">×</button>
    </header>
    <Plot w={win.w} h={win.h - 30} data={data} id={`plot-${data.box.join("-")}`}/>
    <div className="grip" onPointerDown={drag("resize")}><i/><i/><i/></div>
  </section>;
}

const tools = [
  {id: "pen", label: "Stylo", d: "M4 16l1-4L13.5 3.5a1.4 1.4 0 0 1 2 0l1 1a1.4 1.4 0 0 1 0 2L8 15z"},
  {id: "eraser", label: "Gomme", d: "M7.5 16h9M3.8 11.7l6.9-6.9a1.5 1.5 0 0 1 2.1 0l2.4 2.4a1.5 1.5 0 0 1 0 2.1L9.3 15.2a1.5 1.5 0 0 1-2.1 0z"},
  {id: "undo", label: "Annuler", d: "M7 5 3.5 8.5 7 12M4 8.5h7.5a4.5 4.5 0 0 1 0 9H9"},
  {id: "clear", label: "Effacer", d: "M4 6h12M8 6V4h4v2M6 6l.8 10h6.4L14 6"},
  {id: "plot", label: "Courbe", d: "M3 3v14h14M5.5 6c2 9 4 9 5.5 5s3-5 5.5-1"},
];
const penColors = [
  {name: "noir", value: "#111"},
  {name: "bleu", value: "#2563EB"},
  {name: "rouge", value: "#DC2626"},
  {name: "vert", value: "#16A34A"},
];

function drawPlotSnapshot(ctx: CanvasRenderingContext2D, data: PlotData, box: Win) {
  const [xMin, xMax] = data.x_range, [yMin, yMax] = data.y_range;
  const header = 30, left = 42, right = 14, top = 14, bottom = 28;
  const graphWidth = Math.max(1, box.w - left - right), graphHeight = Math.max(1, box.h - header - top - bottom);
  const sx = (x: number) => box.x + left + (x - xMin) / (xMax - xMin) * graphWidth;
  const sy = (y: number) => box.y + header + top + (yMax - y) / (yMax - yMin) * graphHeight;
  ctx.fillStyle = "#fff";
  ctx.fillRect(box.x, box.y, box.w, box.h);
  ctx.fillStyle = "#F7F6F3";
  ctx.fillRect(box.x, box.y, box.w, header);
  ctx.fillStyle = "#262626";
  ctx.font = "500 12px sans-serif";
  ctx.fillText(plotHeader(data), box.x + 30, box.y + 19);
  ctx.strokeStyle = "#E1DFDB";
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x + left, box.y + header + top, graphWidth, graphHeight);
  ctx.clip();
  ctx.strokeStyle = "rgba(38,38,38,.09)";
  ctx.lineWidth = 1;
  for (const x of niceTicks(xMin, xMax)) {
    ctx.beginPath();
    ctx.moveTo(sx(x), box.y + header + top);
    ctx.lineTo(sx(x), box.y + header + top + graphHeight);
    ctx.stroke();
  }
  for (const y of niceTicks(yMin, yMax)) {
    ctx.beginPath();
    ctx.moveTo(box.x + left, sy(y));
    ctx.lineTo(box.x + left + graphWidth, sy(y));
    ctx.stroke();
  }
  const colors = ["#161616", "#FF9F0A", "#30D158"];
  data.curves.forEach((curve, curveIndex) => {
    ctx.beginPath();
    let drawing = false;
    for (const sample of curve.samples) {
      if (!sample) { drawing = false; continue; }
      if (drawing) ctx.lineTo(sx(sample[0]), sy(sample[1]));
      else { ctx.moveTo(sx(sample[0]), sy(sample[1])); drawing = true; }
    }
    ctx.strokeStyle = colors[curveIndex % colors.length];
    ctx.lineWidth = 2.4;
    ctx.stroke();
  });
  ctx.strokeStyle = "#262626";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(box.x + left, sy(yMin <= 0 && yMax >= 0 ? 0 : yMin));
  ctx.lineTo(box.x + left + graphWidth, sy(yMin <= 0 && yMax >= 0 ? 0 : yMin));
  ctx.moveTo(sx(xMin <= 0 && xMax >= 0 ? 0 : xMin), box.y + header + top + graphHeight);
  ctx.lineTo(sx(xMin <= 0 && xMax >= 0 ? 0 : xMin), box.y + header + top);
  ctx.stroke();
  ctx.restore();
  for (const point of data.points) {
    ctx.beginPath();
    ctx.arc(sx(point.x), sy(point.y), 5, 0, Math.PI * 2);
    ctx.fillStyle = "#E8C547";
    ctx.fill();
    ctx.fillStyle = "#262626";
    ctx.font = "12px sans-serif";
    const label = pointLabelLayout(point, data.points, sx, sy);
    ctx.textAlign = label.anchor === "middle" ? "center" : label.anchor;
    ctx.fillText(label.label, label.x, label.y);
  }
  ctx.textAlign = "start";
}

function Board() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const exerciseCard = useRef<HTMLElement>(null);
  const strokes = useRef<Stroke[]>([]);
  const [tool, setTool] = useState("pen");
  const [penColor, setPenColor] = useState(penColors[0].value);
  const [plotData, setPlotData] = useState<PlotData | null>(null);
  const [plotBox, setPlotBox] = useState<Win>({x: 24, y: 140, w: 520, h: 360});
  const [plotVisible, setPlotVisible] = useState(false);
  const [plotRevision, setPlotRevision] = useState(0);
  const [marks, setMarks] = useState<BoardMark[]>([]);
  const cursorRest = {x: innerWidth / 2, y: innerHeight - 90};
  const [cursor, setCursor] = useState<CursorVisual>({...cursorRest, visible: false});
  const cursorMotion = useRef<ReturnType<typeof createCursorMotion> | null>(null);
  if (!cursorMotion.current) cursorMotion.current = createCursorMotion(cursorRest, setCursor);
  const pendingAnnotations = useRef(new Map<string, AnnotationRect>());
  const [geraldTexts, setGeraldTexts] = useState<GeraldText[]>([]);
  const [, tick] = useState(0);
  const snapshotState = useRef<BoardSnapshot>({
    plotData: null,
    plotBox,
    marks: [],
    texts: [],
    plotVisible: true,
    exerciseRect: null,
  });
  const redraw = () => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const ratio = devicePixelRatio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    for (const stroke of strokes.current) {
      ctx.globalCompositeOperation = stroke.erase ? "destination-out" : "source-over";
      ctx.strokeStyle = stroke.erase ? "#111" : stroke.color ?? "#111";
      for (let i = 1; i < stroke.pts.length; i++) {
        const a = stroke.pts[i - 1], b = stroke.pts[i];
        ctx.lineWidth = stroke.erase ? 26 : 1.4 + 2.6 * b.p;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
    ctx.globalCompositeOperation = "source-over";
  };
  useEffect(() => {
    const fit = () => {
      const c = canvas.current;
      if (!c) return;
      c.width = innerWidth * devicePixelRatio;
      c.height = innerHeight * devicePixelRatio;
      redraw();
    };
    fit();
    addEventListener("resize", fit);
    return () => removeEventListener("resize", fit);
  }, []);
  useEffect(() => {
    snapshotState.current = {
      plotData,
      plotBox,
      marks,
      texts: geraldTexts,
      plotVisible,
      exerciseRect: exerciseCard.current?.getBoundingClientRect() ?? null,
    };
  }, [plotData, plotBox, marks, geraldTexts, plotVisible]);
  const occupiedBoxes = () => {
    const boxes: number[][] = [];
    const card = exerciseCard.current?.getBoundingClientRect();
    if (card) boxes.push([card.x, card.y, card.width, card.height]);
    for (const mark of marks) {
      if (mark.kind === "note" || mark.kind === "tip") boxes.push([mark.x, mark.y, mark.w, mark.h]);
      else boxes.push([mark.x - mark.w / 2, mark.y - mark.h / 2, mark.w, mark.h]);
    }
    for (const text of geraldTexts) boxes.push([text.x, text.y - text.size, text.text.length * text.size * 0.65, text.size]);
    if (plotVisible && plotData) boxes.push([plotBox.x, plotBox.y, plotBox.w, plotBox.h]);
    return boxes;
  };
  const installPlot = (data: PlotData) => {
    setPlotData(data);
    setPlotBox({x: data.box[0], y: data.box[1], w: data.box[2], h: data.box[3]});
    setPlotVisible(true);
    setPlotRevision((value) => value + 1);
  };
  const requestPlot = async (args: Record<string, unknown>, occupied = occupiedBoxes()) => {
    const response = await fetch("/api/plot", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({...args, image_size: [innerWidth, innerHeight], occupied_boxes: occupied}),
    });
    const data = await response.json();
    if (!response.ok || data.ok !== true) throw new Error(data.error || "Le tracé a échoué.");
    return data as PlotData;
  };
  const snapshot = () => {
    const width = Math.max(1, Math.round(innerWidth));
    const height = Math.max(1, Math.round(innerHeight));
    const image = document.createElement("canvas");
    image.width = width;
    image.height = height;
    const ctx = image.getContext("2d");
    if (!ctx) throw new Error("Canvas is unavailable");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, width, height);
    const current = snapshotState.current;
    const card = exerciseCard.current?.getBoundingClientRect() ?? current.exerciseRect;
    if (card) {
      ctx.fillStyle = "#fff";
      ctx.fillRect(card.x, card.y, card.width, card.height);
      ctx.strokeStyle = "#E1DFDB";
      ctx.strokeRect(card.x, card.y, card.width, card.height);
      ctx.fillStyle = "#6D6D6D";
      ctx.font = "12px sans-serif";
      ctx.fillText(title.toUpperCase(), card.x + 18, card.y + 20);
      ctx.fillStyle = "#262626";
      ctx.font = "500 17px sans-serif";
      lines.forEach((line, index) => ctx.fillText(line, card.x + 18, card.y + 48 + index * 25, card.width - 36));
    }
    if (canvas.current) ctx.drawImage(canvas.current, 0, 0, width, height);
    for (const text of current.texts) {
      ctx.fillStyle = "#0067D9";
      ctx.font = `500 ${text.size}px sans-serif`;
      ctx.fillText(text.text, text.x, text.y, Math.max(100, width - text.x));
    }
    for (const mark of current.marks) {
      const progress = mark.progress ?? 1;
      ctx.strokeStyle = mark.color ?? "#0067D9";
      ctx.fillStyle = mark.color ?? "#0067D9";
      ctx.lineWidth = 3;
      if (mark.kind === "circle") {
        ctx.beginPath();
        ctx.ellipse(mark.x, mark.y, mark.w / 2, mark.h / 2, 0, 0, Math.PI * 2 * progress);
        ctx.stroke();
      } else if (mark.kind === "underline") {
        ctx.beginPath();
        ctx.moveTo(mark.x - mark.w / 2, mark.y + mark.h / 2);
        ctx.lineTo(mark.x - mark.w / 2 + mark.w * progress, mark.y + mark.h / 2);
        ctx.stroke();
      } else if (mark.kind === "point") {
        ctx.beginPath();
        ctx.arc(mark.x, mark.y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#262626";
        ctx.font = "12px sans-serif";
        ctx.fillText(mark.text, mark.x + 8, mark.y - 8);
      } else if (mark.kind === "highlight") {
        ctx.fillStyle = "rgba(10,132,255,.16)";
        ctx.fillRect(mark.x - mark.w / 2, mark.y - mark.h / 2, mark.w * progress, mark.h);
        ctx.strokeStyle = "#0067D9";
        ctx.strokeRect(mark.x - mark.w / 2, mark.y - mark.h / 2, mark.w * progress, mark.h);
      } else if (mark.kind === "arrow") {
        ctx.beginPath();
        ctx.moveTo(mark.x, mark.y);
        ctx.lineTo(mark.x + mark.w * progress, mark.y + mark.h * progress);
        ctx.stroke();
      } else if (mark.kind === "note") {
        if (mark.leader && mark.target) {
          const line = annotationLeader(mark.target, {x: mark.x, y: mark.y, w: mark.w, h: mark.h});
          ctx.beginPath();
          ctx.moveTo(line.x1, line.y1);
          ctx.lineTo(line.x2, line.y2);
          ctx.strokeStyle = "#0067D9";
          ctx.stroke();
        }
        ctx.fillStyle = "#FFFDBD";
        ctx.fillRect(mark.x, mark.y, mark.w, mark.h);
        ctx.fillStyle = "#262626";
        ctx.font = "13px sans-serif";
        ctx.fillText(mark.text, mark.x + 8, mark.y + 20, mark.w - 16);
      } else if (mark.kind === "tip") {
        if (mark.leader && mark.target) {
          const line = annotationLeader(mark.target, {x: mark.x, y: mark.y, w: mark.w, h: mark.h});
          ctx.beginPath();
          ctx.moveTo(line.x1, line.y1);
          ctx.lineTo(line.x2, line.y2);
          ctx.strokeStyle = "#0067D9";
          ctx.stroke();
        }
        ctx.fillStyle = "#161616";
        ctx.fillRect(mark.x, mark.y, mark.w, mark.h);
        ctx.fillStyle = "#F7F6F3";
        ctx.font = "13px sans-serif";
        ctx.fillText(mark.text, mark.x + 14, mark.y + 24, mark.w - 28);
      }
    }
    if (current.plotVisible && current.plotData) drawPlotSnapshot(ctx, current.plotData, current.plotBox);
    return image.toDataURL("image/jpeg", 0.7);
  };
  const elements = () => {
    const visible = [...document.querySelectorAll<HTMLElement>("[data-gerald-id], .gerald-write, .plot-win")];
    const domElements = visible.filter((element) => element.getClientRects().length).map((element, index) => {
      const rect = element.getBoundingClientRect();
      return {
        id: Number(element.dataset.geraldId) || 200 + index,
        text: (element.innerText || "").trim(),
        rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
      };
    });
    const strokeBoxes = strokes.current.flatMap((stroke) => {
      if (stroke.erase || !stroke.pts.length) return [];
      const xs = stroke.pts.map((point) => point.x);
      const ys = stroke.pts.map((point) => point.y);
      const x = Math.min(...xs);
      const y = Math.min(...ys);
      return [{
        rect: {x: x - 5, y: y - 5, w: Math.max(12, Math.max(...xs) - x + 10), h: Math.max(12, Math.max(...ys) - y + 10)},
        color: stroke.color ?? penColors[0].value,
      }];
    });
    const clusters: Array<{rect: AnnotationRect; colors: Set<string>}> = [];
    for (const {rect, color} of strokeBoxes) {
      const merged = {rect: {...rect}, colors: new Set([color])};
      for (let index = 0; index < clusters.length;) {
        const item = clusters[index];
        const nearby = merged.rect.x <= item.rect.x + item.rect.w + 14 && item.rect.x <= merged.rect.x + merged.rect.w + 14
          && merged.rect.y <= item.rect.y + item.rect.h + 14 && item.rect.y <= merged.rect.y + merged.rect.h + 14;
        if (!nearby) {
          index += 1;
          continue;
        }
        const right = Math.max(merged.rect.x + merged.rect.w, item.rect.x + item.rect.w);
        const bottom = Math.max(merged.rect.y + merged.rect.h, item.rect.y + item.rect.h);
        merged.rect.x = Math.min(merged.rect.x, item.rect.x);
        merged.rect.y = Math.min(merged.rect.y, item.rect.y);
        merged.rect.w = right - merged.rect.x;
        merged.rect.h = bottom - merged.rect.y;
        item.colors.forEach((itemColor) => merged.colors.add(itemColor));
        clusters.splice(index, 1);
        index = 0;
      }
      clusters.push(merged);
    }
    const inkElements = clusters.map(({rect, colors}, index) => {
      const colorName = colors.size === 1
        ? penColors.find(({value}) => value === [...colors][0])?.name
        : undefined;
      return {
        id: 10000 + index,
        text: `encre élève #${index + 1}${colorName ? ` (${colorName})` : ""}`,
        rect,
      };
    });
    return [...domElements, ...inkElements];
  };
  const placeBeside = (target: AnnotationRect, text: string, kind: "note" | "tip") => {
    const occupied = [
      ...elements().map((element) => element.rect),
      ...marks.filter((mark) => mark.kind === "note" || mark.kind === "tip")
        .map((mark) => ({x: mark.x, y: mark.y, w: mark.w, h: mark.h})),
      ...pendingAnnotations.current.values(),
      target,
    ];
    return placeAnnotation(target, annotationSize(text, kind), occupied, {w: innerWidth, h: innerHeight});
  };
  const waitForPaint = () => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  const addMark = (mark: BoardMark) => setMarks((items) => [...items, mark]);
  const updateMarkProgress = (id: string, progress: number) =>
    setMarks((items) => items.map((mark) => mark.id === id ? {...mark, progress} : mark));
  const targetRect = (args: Record<string, unknown>) => {
    const wanted = typeof args.target_text === "string" ? args.target_text : "";
    const elementId = Number(args.element_id);
    const ink = elements().find((item) => item.id === elementId && item.id >= 10000);
    if (ink) return ink.rect;
    const candidates = [...document.querySelectorAll<HTMLElement>("[data-gerald-id]")];
    const element = candidates.find((item) => item.dataset.geraldId === String(args.element_id))
      ?? (wanted ? candidates.find((item) => normalizedMatch(item.innerText, wanted)) : undefined);
    if (element) {
      let rect = element.getBoundingClientRect();
      if (wanted) {
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        const nodes: Text[] = [];
        let current: Node | null;
        while ((current = walker.nextNode())) nodes.push(current as Text);
        const raw = nodes.map((node) => node.data).join("");
        const match = normalizedMatch(raw, wanted);
        if (match && nodes.length) {
          const locate = (offset: number, end: boolean): [Text, number] => {
            let base = 0;
            for (const node of nodes) {
              if (offset < base + node.length || end && offset === base + node.length) return [node, offset - base];
              base += node.length;
            }
            const last = nodes[nodes.length - 1];
            return [last, last.length];
          };
          const [start, startOffset] = locate(match.index, false);
          const [finish, endOffset] = locate(match.end, true);
          const range = document.createRange();
          range.setStart(start, startOffset);
          range.setEnd(finish, endOffset);
          rect = range.getBoundingClientRect();
        } else if (!isNumber(args.element_id)) return null;
      }
      return {x: rect.x, y: rect.y, w: rect.width, h: rect.height};
    }
    if (isNumber(args.x) && isNumber(args.y)) return {x: args.x, y: args.y, w: isNumber(args.w) ? args.w : 120, h: isNumber(args.h) ? args.h : 38};
    return null;
  };
  const executeWebTool = async (name: string, args: Record<string, unknown>) => {
    const id = crypto.randomUUID();
    const target = targetRect(args);
    const motion = cursorMotion.current!;
    const color = intentColor(args.intent);
    const highlightFill = intentColor(args.intent, null, 0.16);
    if (name === "clear_gerald") {
      pendingAnnotations.current.clear();
      motion.enqueue(() => {
        setMarks([]);
        setGeraldTexts([]);
        motion.clear();
        setPlotData(null);
        setPlotVisible(false);
      });
      return {ok: true};
    }
    if (name === "plot") {
      const data = await requestPlot(args);
      motion.enqueue(() => installPlot(data));
      return {ok: true, box: data.box, points: data.points};
    }
    if (name === "write" || name === "write_math") {
      const text = name === "write" ? args.text : args.latex;
      if (typeof text !== "string" || !isNumber(args.x) || !isNumber(args.y)) {
        return {ok: false, error: "write requires text or latex and numeric x,y coordinates"};
      }
      const size = isNumber(args.size) ? args.size : 32;
      const html = name === "write_math"
        ? katex.renderToString(text, {throwOnError: false, output: "htmlAndMathml"})
        : undefined;
      const parts = name === "write"
        ? segmentBoardText(text).map((part) => part.type === "math"
          ? {...part, html: katex.renderToString(mathToLatex(part.value), {throwOnError: false, output: "htmlAndMathml"})}
          : part)
        : undefined;
      motion.enqueue(async (queue) => {
        await queue.moveTo({x: Number(args.x), y: Number(args.y)});
        setGeraldTexts((items) => [...items, {id, text, x: Number(args.x), y: Number(args.y), size, color: color ?? "#111", html, parts}]);
      });
      return {ok: true};
    }
    if (name === "tip") {
      if (typeof args.text !== "string") return {ok: false, error: "tip requires text"};
      const point = target ?? {x: innerWidth / 2, y: innerHeight - 130, w: 0, h: 0};
      const placement = placeBeside(point, args.text, "tip");
      if (!placement) return {ok: false, error: "no free space to place the tip beside its target"};
      pendingAnnotations.current.set(id, placement.rect);
      motion.enqueue(async (queue) => {
        await queue.moveTo({x: point.x + point.w / 2, y: point.y + point.h / 2});
        addMark({
          id, kind: "tip", x: placement.rect.x, y: placement.rect.y, ...annotationSize(args.text as string, "tip"),
          text: args.text as string, color, target: target ? point : undefined, leader: target ? placement.leader : false,
        });
        pendingAnnotations.current.delete(id);
      });
      return {ok: true, target: {x: point.x, y: point.y, w: point.w, h: point.h}, annotation: placement.rect};
    }
    if (name === "arrow") {
      const from = targetRect((args.from ?? {}) as Record<string, unknown>);
      const to = targetRect((args.to ?? {}) as Record<string, unknown>);
      if (!from || !to) return {ok: false, error: "arrow targets were not found"};
      const endpoints = arrowEndpoints(from, to);
      if (!endpoints) return {ok: false, error: "arrow endpoints could not be calculated"};
      const {x1, y1, x2, y2} = endpoints;
      motion.enqueue(async (queue) => {
        await queue.moveTo({x: x1, y: y1});
        addMark({id, kind: "arrow", x: x1, y: y1, w: x2 - x1, h: y2 - y1, text: "", color, progress: 0});
        await waitForPaint();
        await queue.moveTo({x: x2, y: y2}, (progress) => updateMarkProgress(id, progress));
      });
      return {ok: true, target: {x: x2, y: y2}, from: {x: x1, y: y1}, to: {x: x2, y: y2}};
    }
    if (["underline", "circle", "highlight", "point", "note"].includes(name)) {
      if (!target) {
        return {ok: false, error: `${name} requires numeric x,y coordinates on the board`};
      }
      const text = typeof args.text === "string"
        ? args.text
        : typeof args.label === "string" ? args.label : "";
      if (name === "note") {
        const placement = placeBeside(target, text, "note");
        if (!placement) return {ok: false, error: "no free space to place the note beside its target"};
        const size = annotationSize(text, "note");
        const mark = {
          id, kind: name, x: placement.rect.x, y: placement.rect.y, ...size, text,
          color, target, leader: placement.leader,
        };
        pendingAnnotations.current.set(id, placement.rect);
        motion.enqueue(async (queue) => {
          await queue.moveTo({x: target.x + target.w / 2, y: target.y + target.h / 2});
          addMark(mark);
          pendingAnnotations.current.delete(id);
        });
        return {ok: true, target, annotation: placement.rect};
      }
      const x = name === "note" ? target.x : target.x + target.w / 2;
      const y = name === "note" ? target.y : target.y + target.h / 2;
      const exactText = typeof args.target_text === "string" && args.target_text.length > 0;
      const width = exactText ? target.w : isNumber(args.w) ? args.w : target.w || (name === "point" ? 12 : 120);
      const height = exactText ? target.h : isNumber(args.h) ? args.h : target.h || (name === "point" ? 12 : 38);
      const mark: BoardMark = {id, kind: name, x, y, w: width, h: height, text, color, fill: name === "highlight" ? highlightFill : null};
      if (name === "underline" || name === "highlight") {
        const start = {x: x - width / 2, y: y + height / 2};
        const end = {x: x + width / 2, y: y + height / 2};
        motion.enqueue(async (queue) => {
          await queue.moveTo(start);
          addMark({...mark, progress: 0});
          await waitForPaint();
          await queue.moveTo(end, (progress) => updateMarkProgress(id, progress));
        });
      } else if (name === "circle") {
        const start = {x: x + width / 2, y};
        motion.enqueue(async (queue) => {
          await queue.moveTo(start);
          addMark({...mark, progress: 0});
          await waitForPaint();
          for (let segment = 1; segment <= 4; segment += 1) {
            const angle = segment * Math.PI / 2;
            const end = {x: x + width / 2 * Math.cos(angle), y: y + height / 2 * Math.sin(angle)};
            await queue.moveTo(end, (progress) => updateMarkProgress(id, (segment - 1 + progress) / 4));
          }
        });
      } else {
        motion.enqueue(async (queue) => {
          await queue.moveTo({x, y});
          addMark({...mark, progress: 1});
        });
      }
      return {ok: true, target: {x, y}};
    }
    return {ok: false, error: `unknown board tool: ${name}`};
  };
  useEffect(() => {
    window.geraldBoard = {snapshot, elements, exec: executeWebTool, waitForAnimations: () => cursorMotion.current!.waitForAnimations()};
    return () => { delete window.geraldBoard; };
  });
  const down = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (e.button > 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    strokes.current.push({
      pts: [{x: e.clientX, y: e.clientY, p: e.pressure || .5}],
      erase: tool === "eraser",
      color: penColor,
    });
  };
  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
    const stroke = strokes.current[strokes.current.length - 1];
    for (const event of e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent]) {
      stroke.pts.push({x: event.clientX, y: event.clientY, p: event.pressure || .5});
    }
    redraw();
  };
  const act = (id: string) => {
    if (id === "undo") { strokes.current.pop(); redraw(); }
    else if (id === "clear") { strokes.current = []; redraw(); }
    else if (id === "plot") setPlotVisible((visible) => !visible);
    else setTool(id);
    tick((value) => value + 1);
  };
  const renderTool = (item: (typeof tools)[number]) => <button key={item.id}
    className={(item.id === tool || (item.id === "plot" && plotVisible)) ? "on" : ""}
    onClick={() => act(item.id)} title={item.label} aria-label={item.label}>
    <svg viewBox="0 0 20 20"><path d={item.d}/></svg>
  </button>;
  return <main className="board">
    <canvas ref={canvas} className={tool} onPointerDown={down} onPointerMove={move}/>
    {!liveMode&&<aside className="ex-card" ref={exerciseCard} data-gerald-id="100"><div className="ex-label"><i/>{title.toUpperCase()}</div>{lines.map((line, index) => <p key={index} data-gerald-id={101 + index}>{line}</p>)}</aside>}
    <div className="gerald-text-layer">
      {geraldTexts.map((item,index) => <div key={item.id} className="gerald-write" data-gerald-id={300+index} style={{left: item.x, top: item.y, fontSize: item.size, color: item.color}}>
        {item.html ? <span dangerouslySetInnerHTML={{__html: item.html}}/> : item.parts
          ? item.parts.map((part, partIndex) => part.html
            ? <span key={partIndex} dangerouslySetInnerHTML={{__html: part.html}}/>
            : <span key={partIndex}>{part.value}</span>)
          : item.text}
      </div>)}
    </div>
    <svg className="gerald-marks" width={innerWidth} height={innerHeight}>
      <defs>
        <marker id="gerald-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker>
        {marks.filter((mark) => mark.kind === "arrow" && mark.color).map((mark) =>
          <marker key={mark.id} id={`gerald-arrow-${mark.id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" style={{fill: mark.color!}}/>
          </marker>)}
      </defs>
      {marks.filter((mark) => mark.kind === "circle").map((mark) => {
        const length = ellipseCircumference(mark.w / 2, mark.h / 2);
        const progress = mark.progress ?? 1;
        return <ellipse key={mark.id} data-gerald-mark-kind="circle" cx={mark.x} cy={mark.y} rx={mark.w / 2} ry={mark.h / 2}
          strokeDasharray={`${length} ${length}`} strokeDashoffset={length * (1 - progress)} style={{stroke: mark.color ?? undefined}}/>;
      })}
      {marks.filter((mark) => mark.kind === "underline").map((mark) =>
        <line key={mark.id} data-gerald-mark-kind="underline" x1={mark.x - mark.w / 2} x2={mark.x - mark.w / 2 + mark.w * (mark.progress ?? 1)} y1={mark.y + mark.h / 2} y2={mark.y + mark.h / 2} style={{stroke: mark.color ?? undefined}}/>)}
      {marks.filter((mark) => mark.kind === "point").map((mark) =>
        <g key={mark.id} data-gerald-mark-kind="point"><circle cx={mark.x} cy={mark.y} r="5" style={{fill: mark.color ?? undefined}}/><text x={mark.x + 8} y={mark.y - 8} style={{fill: mark.color ?? undefined}}>{mark.text}</text></g>)}
      {marks.filter((mark) => mark.kind === "highlight").map((mark) =>
        <rect key={mark.id} data-gerald-mark-kind="highlight" x={mark.x - mark.w / 2} y={mark.y - mark.h / 2} width={mark.w * (mark.progress ?? 1)} height={mark.h} style={{fill: mark.fill ?? undefined, stroke: mark.color ?? undefined}}/>)}
      {marks.filter((mark) => mark.kind === "arrow").map((mark) =>
        <line key={mark.id} data-gerald-mark-kind="arrow" x1={mark.x} y1={mark.y} x2={mark.x + mark.w * (mark.progress ?? 1)} y2={mark.y + mark.h * (mark.progress ?? 1)} markerEnd={mark.color ? `url(#gerald-arrow-${mark.id})` : "url(#gerald-arrow)"} style={{stroke: mark.color ?? undefined}}/>)}
      {marks.filter((mark) => (mark.kind === "note" || mark.kind === "tip") && mark.leader && mark.target).map((mark) => {
        const line = annotationLeader(mark.target!, {x: mark.x, y: mark.y, w: mark.w, h: mark.h});
        return <line key={`${mark.id}-leader`} x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} style={{stroke: mark.color ?? undefined}}/>;
      })}
      {marks.filter((mark) => mark.kind === "note").map((mark) =>
        <foreignObject key={mark.id} data-gerald-note={mark.id} x={mark.x} y={mark.y} width={mark.w} height={mark.h}>
          <div className="gerald-note" data-gerald-note={mark.id} data-gerald-mark-kind="note"
            style={mark.color ? {color: mark.color, border: `1px solid ${mark.color}`} : undefined}>{mark.text}</div>
        </foreignObject>)}
    </svg>
    {marks.filter((mark) => mark.kind === "tip").map((mark) =>
      <div key={mark.id} className="gerald-tip" data-gerald-tip={mark.id}
        data-gerald-mark-kind="tip"
        style={{left: mark.x, top: mark.y, width: mark.w, height: mark.h, color: mark.color ?? undefined, border: mark.color ? `1px solid ${mark.color}` : undefined}}>{mark.text}</div>)}
    <div className="gerald-pointer" aria-hidden="true" style={{left:cursor.x,top:cursor.y,opacity:cursor.visible?1:0}}>➤</div>
    {plotVisible && plotData && <PlotWindow key={plotRevision} data={plotData} initialBox={plotBox}
      onClose={() => setPlotVisible(false)} onBoxChange={setPlotBox}/>}
    <nav className="board-tools">
      {tools.slice(0, 2).map(renderTool)}
      {penColors.map((color) => <button key={color.value} className="swatch"
        style={{"--swatch-color": color.value} as React.CSSProperties}
        onClick={() => {setPenColor(color.value); setTool("pen");}}
        title={`Couleur du stylo : ${color.name}`}
        aria-label={`Couleur du stylo : ${color.name}`}
        aria-pressed={penColor === color.value}/>)}
      <span className="sep"/>
      {tools.slice(2).map(renderTool)}
      <span className="sep"/>
      <button className="close" onClick={() => window.parent !== window && window.parent.geraldTD?.close ? window.parent.geraldTD.close() : history.length > 1 ? history.back() : window.close()} aria-label="Fermer le tableau">Fermer</button>
    </nav>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Board/>);
if (!window.qt && !serverDemoMode) {
  const host = document.createElement("div");
  host.className = "preview-notch-host";
  document.body.appendChild(host);
  mountNotch(host);
}
