export type AnnotationRect = {x: number; y: number; w: number; h: number};
export type AnnotationKind = "note" | "tip";
export type AnnotationPlacement = {rect: AnnotationRect; leader: boolean};
export type BoardTextPart = {type: "text" | "math"; value: string};

const gap = 12;
const mathRuns = /[\\abcxyΔ0-9²√±=+*×\/^().,\s\-−]+/giu;

function isMathRun(value: string): boolean {
  return /[=Δ²√±+*×/^\\\-−]/u.test(value)
    || (/\d/u.test(value) && /[abcxyΔ]/iu.test(value))
    || /^a\s*,\s*b(?:\s*,\s*c)?$/iu.test(value);
}

function trimMathRun(value: string): string {
  let result = value.trim();
  while (/[.,]$/u.test(result)) result = result.slice(0, -1).trimEnd();
  while (result.endsWith("(") && (result.match(/\(/gu)?.length ?? 0) > (result.match(/\)/gu)?.length ?? 0)) {
    result = result.slice(0, -1).trimEnd();
  }
  return result;
}

export function segmentBoardText(value: string): BoardTextPart[] {
  const explicit: BoardTextPart[] = [];
  const dollarMath = /\$([^$]+)\$/gu;
  let cursor = 0;
  for (const match of value.matchAll(dollarMath)) {
    const start = match.index ?? 0;
    if (start > cursor) explicit.push({type: "text", value: value.slice(cursor, start)});
    explicit.push({type: "math", value: match[1]});
    cursor = start + match[0].length;
  }
  if (cursor > 0) {
    if (cursor < value.length) explicit.push({type: "text", value: value.slice(cursor)});
    return explicit;
  }

  const parts: BoardTextPart[] = [];
  cursor = 0;
  for (const match of value.matchAll(mathRuns)) {
    const raw = match[0];
    const start = (match.index ?? 0) + (raw.length - raw.trimStart().length);
    const expression = trimMathRun(raw);
    const end = start + expression.length;
    if (!expression || start < cursor || !isMathRun(expression)) continue;
    if (start > cursor) parts.push({type: "text", value: value.slice(cursor, start)});
    parts.push({type: "math", value: expression});
    cursor = end;
  }
  if (cursor < value.length) parts.push({type: "text", value: value.slice(cursor)});
  return parts.length ? parts : [{type: "text", value}];
}

export function annotationSize(text: string, kind: AnnotationKind): {w: number; h: number} {
  const w = Math.min(280, Math.max(120, text.length * 7 + 24));
  const lineCount = Math.max(1, Math.ceil(text.length * 7 / Math.max(1, w - 24)));
  return {w, h: Math.min(160, Math.max(kind === "note" ? 42 : 52, lineCount * 19 + (kind === "note" ? 16 : 24)))};
}

function intersects(a: AnnotationRect, b: AnnotationRect): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function inBounds(rect: AnnotationRect, width: number, height: number): boolean {
  return rect.x >= 0 && rect.y >= 0 && rect.x + rect.w <= width && rect.y + rect.h <= height;
}

export function placeAnnotation(
  target: AnnotationRect,
  size: {w: number; h: number},
  occupied: AnnotationRect[],
  viewport: {w: number; h: number},
): AnnotationPlacement | null {
  const directions = [
    {name: "right", rect: {x: target.x + target.w + gap, y: target.y + (target.h - size.h) / 2, ...size}},
    {name: "above", rect: {x: target.x + (target.w - size.w) / 2, y: target.y - size.h - gap, ...size}},
    {name: "below", rect: {x: target.x + (target.w - size.w) / 2, y: target.y + target.h + gap, ...size}},
    {name: "left", rect: {x: target.x - size.w - gap, y: target.y + (target.h - size.h) / 2, ...size}},
  ] as const;

  for (const direction of directions) {
    let rect = {...direction.rect};
    for (let attempt = 0; attempt < 128; attempt += 1) {
      if (!inBounds(rect, viewport.w, viewport.h)) break;
      const collision = occupied.find((item) => intersects(rect, item));
      if (!collision) {
        const distance = direction.name === "right" ? rect.x - (target.x + target.w)
          : direction.name === "left" ? target.x - (rect.x + rect.w)
          : direction.name === "above" ? target.y - (rect.y + rect.h)
          : rect.y - (target.y + target.h);
        return {rect, leader: distance > gap + 4};
      }
      if (direction.name === "right") rect.x = collision.x + collision.w + gap;
      else if (direction.name === "left") rect.x = collision.x - rect.w - gap;
      else if (direction.name === "above") rect.y = collision.y - rect.h - gap;
      else rect.y = collision.y + collision.h + gap;
    }
  }
  return null;
}

export function annotationLeader(target: AnnotationRect, bubble: AnnotationRect) {
  const centerX = target.x + target.w / 2;
  const centerY = target.y + target.h / 2;
  const dx = bubble.x + bubble.w / 2 - centerX;
  const dy = bubble.y + bubble.h / 2 - centerY;
  const scale = Math.min(
    dx === 0 ? Infinity : target.w / 2 / Math.abs(dx),
    dy === 0 ? Infinity : target.h / 2 / Math.abs(dy),
    1,
  );
  const x = centerX + dx * scale;
  const y = centerY + dy * scale;
  return {
    x1: x,
    y1: y,
    x2: Math.max(bubble.x, Math.min(x, bubble.x + bubble.w)),
    y2: Math.max(bubble.y, Math.min(y, bubble.y + bubble.h)),
  };
}
