export type AnnotationRect = {x: number; y: number; w: number; h: number};
export type AnnotationKind = "note" | "tip";
export type AnnotationPlacement = {rect: AnnotationRect; leader: boolean};
export type BoardTextPart = {type: "text" | "math"; value: string};
export type ColorIntent = "correction" | "valide" | "remarque";
export type ArrowEndpoints = {x1: number; y1: number; x2: number; y2: number};
export type CursorPoint = {x: number; y: number};
export type CursorVisual = CursorPoint & {visible: boolean};
export type CursorMotion = {
  moveTo: (to: CursorPoint, onProgress?: (progress: number) => void) => Promise<void>;
  enqueue: (action: (motion: CursorMotion) => void | Promise<void>) => Promise<void>;
  clear: () => void;
  waitForAnimations: () => Promise<void>;
  current: () => CursorPoint;
};

export function arrowEndpoints(
  from: AnnotationRect,
  to: AnnotationRect,
  gap = 10,
  viewport?: {w: number; h: number},
): ArrowEndpoints | null {
  if (![from.x, from.y, from.w, from.h, to.x, to.y, to.w, to.h, gap].every(Number.isFinite)) return null;
  const separationX = Math.max(0, to.x - (from.x + from.w), from.x - (to.x + to.w));
  const separationY = Math.max(0, to.y - (from.y + from.h), from.y - (to.y + to.h));
  const overlaps = separationX <= gap * 2 && separationY <= gap * 2;
  const fromCenter = {x: from.x + from.w / 2, y: from.y + from.h / 2};
  const toCenter = {x: to.x + to.w / 2, y: to.y + to.h / 2};
  const dx = toCenter.x - fromCenter.x;
  const dy = toCenter.y - fromCenter.y;
  const length = Math.hypot(dx, dy);
  const unit = length ? {x: dx / length, y: dy / length} : {x: 0, y: 0};
  const boundaryDistance = (rect: AnnotationRect, direction: {x: number; y: number}) => Math.min(
    direction.x === 0 ? Infinity : (rect.w / 2 + gap) / Math.abs(direction.x),
    direction.y === 0 ? Infinity : (rect.h / 2 + gap) / Math.abs(direction.y),
  );
  const startDistance = boundaryDistance(from, unit);
  const endDistance = boundaryDistance(to, unit);
  const clippedLength = length - startDistance - endDistance;

  if (!overlaps && clippedLength >= 24) {
    return {
      x1: fromCenter.x + unit.x * startDistance,
      y1: fromCenter.y + unit.y * startDistance,
      x2: toCenter.x - unit.x * endDistance,
      y2: toCenter.y - unit.y * endDistance,
    };
  }

  const corner = {x: to.x - gap, y: to.y - gap};
  const bounds = viewport ?? (typeof window === "undefined" ? undefined : {w: window.innerWidth, h: window.innerHeight});
  const start = {
    x: Math.max(0, Math.min(bounds?.w ?? Infinity, corner.x - 70)),
    y: Math.max(0, Math.min(bounds?.h ?? Infinity, corner.y - 70)),
  };
  return {x1: start.x, y1: start.y, x2: corner.x, y2: corner.y};
}

export function animateCursor(
  from: CursorPoint,
  to: CursorPoint,
  onFrame: (point: CursorPoint, progress: number) => void,
): Promise<void> {
  const distance = Math.hypot(to.x - from.x, to.y - from.y);
  const reducedMotion = typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reducedMotion || distance < 1) {
    onFrame(to, 1);
    return Promise.resolve();
  }

  const duration = Math.min(900, Math.max(280, distance / 1.6));
  const perpendicular = {x: -(to.y - from.y) / distance, y: (to.x - from.x) / distance};
  const control = {
    x: (from.x + to.x) / 2 + perpendicular.x * distance * 0.12,
    y: (from.y + to.y) / 2 + perpendicular.y * distance * 0.12,
  };
  const startedAt = performance.now();

  return new Promise((resolve) => {
    const frame = (now: number) => {
      const linear = Math.min(1, (now - startedAt) / duration);
      const progress = linear < 0.5
        ? 4 * linear ** 3
        : 1 - ((-2 * linear + 2) ** 3) / 2;
      const remaining = 1 - progress;
      onFrame({
        x: remaining ** 2 * from.x + 2 * remaining * progress * control.x + progress ** 2 * to.x,
        y: remaining ** 2 * from.y + 2 * remaining * progress * control.y + progress ** 2 * to.y,
      }, progress);
      if (linear < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

export function createCursorMotion(
  initial: CursorPoint,
  onUpdate: (cursor: CursorVisual) => void,
): CursorMotion {
  let position = {...initial};
  let queue = Promise.resolve();
  const reducedMotion = typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const motion: CursorMotion = {
    async moveTo(to, onProgress) {
      const from = {...position};
      onUpdate({...position, visible: true});
      if (!reducedMotion) {
        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      }
      await animateCursor(from, to, (point, progress) => {
        position = point;
        onUpdate({...position, visible: true});
        onProgress?.(progress);
      });
      position = {...to};
    },
    enqueue(action) {
      queue = queue.then(() => action(motion)).catch((error: unknown) => {
        console.error("Gerald cursor motion failed", error);
      });
      return queue;
    },
    clear() {
      onUpdate({...position, visible: false});
    },
    async waitForAnimations() {
      await queue;
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    },
    current() {
      return {...position};
    },
  };
  return motion;
}

export function ellipseCircumference(rx: number, ry: number): number {
  return Math.PI * (3 * (rx + ry) - Math.sqrt((3 * rx + ry) * (rx + 3 * ry)));
}

const intentColors: Record<ColorIntent, string> = {
  correction: "#DC2626",
  valide: "#16A34A",
  remarque: "#2563EB",
};

export function intentColor(intent: unknown, fallback: string | null = null, alpha = 1): string | null {
  const mapped = typeof intent === "string" && Object.prototype.hasOwnProperty.call(intentColors, intent)
    ? intentColors[intent as ColorIntent]
    : undefined;
  const color = mapped ?? fallback;
  if (!color || alpha >= 1) return color;
  const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/iu.exec(color);
  if (!match) return color;
  const [red, green, blue] = match.slice(1).map((channel) => Number.parseInt(channel, 16));
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

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
