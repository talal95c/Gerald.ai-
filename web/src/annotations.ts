export type AnnotationRect = {x: number; y: number; w: number; h: number};
export type AnnotationKind = "note" | "tip";
export type AnnotationPlacement = {rect: AnnotationRect; leader: boolean};
export type BoardTextPart = {type: "text" | "math"; value: string};
export type ColorIntent = "correction" | "valide" | "remarque";
export type ArrowEndpoints = {x1: number; y1: number; x2: number; y2: number};
export type CursorPoint = {x: number; y: number};
export type CursorVisual = CursorPoint & {visible: boolean};
export const SAFE_GAP = 12;
export const POINTER_OFFSET = {x: 12, y: 16};
export const POINTER_SIZE = {w: 100, h: 34};
export type CursorMotion = {
  moveTo: (to: CursorPoint, onProgress?: (progress: number) => void) => Promise<void>;
  moveAlong: (points: CursorPoint[], durationMs: number, onProgress?: (progress: number) => void) => Promise<void>;
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

  const bounds = viewport ?? (typeof window === "undefined" ? undefined : {w: window.innerWidth, h: window.innerHeight});
  const aboveSpace = to.y;
  const belowSpace = (bounds?.h ?? to.y + to.h + 80) - (to.y + to.h);
  const direction = aboveSpace >= belowSpace ? -1 : 1;
  const edgeY = direction < 0 ? to.y : to.y + to.h;
  const centerX = to.x + to.w / 2;
  const clampY = (value: number) => Math.max(0, Math.min(bounds?.h ?? Infinity, value));
  return {
    x1: centerX,
    y1: clampY(edgeY + direction * 70),
    x2: centerX,
    y2: clampY(edgeY + direction * gap),
  };
}

function segmentIntersectsRect(start: CursorPoint, end: CursorPoint, rect: AnnotationRect): boolean {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  let low = 0;
  let high = 1;
  for (const [p, q] of [
    [-dx, start.x - rect.x],
    [dx, rect.x + rect.w - start.x],
    [-dy, start.y - rect.y],
    [dy, rect.y + rect.h - start.y],
  ]) {
    if (p === 0) {
      if (q < 0) return false;
      continue;
    }
    const ratio = q / p;
    if (p < 0) low = Math.max(low, ratio);
    else high = Math.min(high, ratio);
    if (low > high) return false;
  }
  return true;
}

function arrowTouchesRect(start: CursorPoint, end: CursorPoint, rect: AnnotationRect): boolean {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy) || 1;
  const unit = {x: dx / length, y: dy / length};
  const wing = {x: end.x - unit.x * 12, y: end.y - unit.y * 12};
  const side = {x: -unit.y * 7, y: unit.x * 7};
  return segmentIntersectsRect(start, end, rect)
    || segmentIntersectsRect(end, {x: wing.x + side.x, y: wing.y + side.y}, rect)
    || segmentIntersectsRect(end, {x: wing.x - side.x, y: wing.y - side.y}, rect);
}

export function arrowEndpointsAroundTarget(
  target: AnnotationRect,
  obstacles: AnnotationRect[],
  viewport: {w: number; h: number},
): ArrowEndpoints | null {
  const center = {x: target.x + target.w / 2, y: target.y + target.h / 2};
  const candidates = [
    {x: target.x + target.w + 70, y: target.y + target.h + 70},
    {x: target.x + target.w + 70, y: center.y},
    {x: target.x + target.w + 70, y: target.y - 70},
    {x: center.x, y: target.y + target.h + 70},
  ];
  const otherRects = obstacles.filter((rect) =>
    !(target.x >= rect.x && target.y >= rect.y
      && target.x + target.w <= rect.x + rect.w && target.y + target.h <= rect.y + rect.h),
  );
  for (const start of candidates) {
    if (start.x < 0 || start.y < 0 || start.x > viewport.w || start.y > viewport.h) continue;
    const dx = start.x - center.x;
    const dy = start.y - center.y;
    const length = Math.hypot(dx, dy) || 1;
    const unit = {x: dx / length, y: dy / length};
    const edge = Math.min(
      unit.x === 0 ? Infinity : target.w / 2 / Math.abs(unit.x),
      unit.y === 0 ? Infinity : target.h / 2 / Math.abs(unit.y),
    );
    const tip = {x: center.x + unit.x * (edge + 2), y: center.y + unit.y * (edge + 2)};
    const inflated = otherRects.map((rect) => ({x: rect.x - 4, y: rect.y - 4, w: rect.w + 8, h: rect.h + 8}));
    if (inflated.some((rect) => arrowTouchesRect(start, tip, rect))) continue;
    return {x1: start.x, y1: start.y, x2: tip.x, y2: tip.y};
  }
  return null;
}

export function arrowEndpointsFromSource(
  source: AnnotationRect,
  target: AnnotationRect,
  obstacles: AnnotationRect[],
  viewport: {w: number; h: number},
): ArrowEndpoints | null {
  const clipped = arrowEndpoints(source, target, 2, viewport);
  if (!clipped) return null;
  const center = {x: target.x + target.w / 2, y: target.y + target.h / 2};
  const direction = Math.atan2(clipped.y1 - center.y, clipped.x1 - center.x);
  const otherRects = obstacles.filter((rect) => {
    const contains = (inner: AnnotationRect, outer: AnnotationRect) =>
      inner.x >= outer.x && inner.y >= outer.y
      && inner.x + inner.w <= outer.x + outer.w && inner.y + inner.h <= outer.y + outer.h;
    return !contains(target, rect) && !contains(source, rect);
  }).map((rect) => ({x: rect.x - 4, y: rect.y - 4, w: rect.w + 8, h: rect.h + 8}));
  for (const offset of [0, 0.35, -0.35, 0.7, -0.7]) {
    const angle = direction + offset;
    const unit = {x: Math.cos(angle), y: Math.sin(angle)};
    const edge = Math.min(
      unit.x === 0 ? Infinity : target.w / 2 / Math.abs(unit.x),
      unit.y === 0 ? Infinity : target.h / 2 / Math.abs(unit.y),
    );
    const tip = {x: center.x + unit.x * (edge + 2), y: center.y + unit.y * (edge + 2)};
    if (otherRects.some((rect) => arrowTouchesRect({x: clipped.x1, y: clipped.y1}, tip, rect))) continue;
    return {...clipped, x2: tip.x, y2: tip.y};
  }
  return null;
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
  let last: number | null = null;
  let elapsed = 0;

  return new Promise((resolve) => {
    const frame = (now: number) => {
      if (last !== null) elapsed += Math.min(now - last, 28);
      last = now;
      const linear = Math.min(1, elapsed / (duration * 1.2));
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
  let hasAppeared = false;
  let queue = Promise.resolve();
  const reducedMotion = typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const appearNear = (point: CursorPoint) => {
    const width = typeof window === "undefined" ? Infinity : window.innerWidth;
    const height = typeof window === "undefined" ? Infinity : window.innerHeight;
    position = {
      x: Math.max(0, Math.min(width - 80, point.x - 48)),
      y: Math.max(0, Math.min(height - 50, point.y - 34)),
    };
    hasAppeared = true;
  };
  const motion: CursorMotion = {
    async moveTo(to, onProgress) {
      if (!hasAppeared) appearNear(to);
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
    moveAlong(points, durationMs, onProgress) {
      if (!points.length) {
        onProgress?.(1);
        return Promise.resolve();
      }
      if (!hasAppeared) {
        appearNear(points[0]);
        points = [position, ...points];
      }
      const end = points[points.length - 1];
      const cumulative = [0];
      for (let index = 1; index < points.length; index += 1) {
        cumulative.push(cumulative[index - 1] + Math.hypot(points[index].x - points[index - 1].x, points[index].y - points[index - 1].y));
      }
      const totalLength = cumulative[cumulative.length - 1];
      if (reducedMotion || totalLength < 1 || durationMs <= 0) {
        position = {...end};
        onUpdate({...position, visible: true});
        onProgress?.(1);
        return Promise.resolve();
      }
      onUpdate({...position, visible: true});
      let last: number | null = null;
      let elapsed = 0;
      return new Promise<void>((resolve) => {
        const frame = (now: number) => {
          if (last !== null) elapsed += Math.min(now - last, 34);
          last = now;
          const linear = Math.min(1, elapsed / (durationMs * 2));
          const progress = linear < 0.5
            ? 4 * linear ** 3
            : 1 - ((-2 * linear + 2) ** 3) / 2;
          const distance = totalLength * progress;
          let segment = 1;
          while (segment < points.length - 1 && cumulative[segment] < distance) segment += 1;
          while (segment < points.length - 1 && cumulative[segment] === cumulative[segment - 1]) segment += 1;
          const segmentLength = cumulative[segment] - cumulative[segment - 1];
          const segmentProgress = segmentLength
            ? Math.max(0, Math.min(1, (distance - cumulative[segment - 1]) / segmentLength))
            : 1;
          const from = points[segment - 1], to = points[segment];
          position = {
            x: from.x + (to.x - from.x) * segmentProgress,
            y: from.y + (to.y - from.y) * segmentProgress,
          };
          onUpdate({...position, visible: true});
          onProgress?.(progress);
          if (linear < 1) requestAnimationFrame(frame);
          else {
            position = {...end};
            onUpdate({...position, visible: true});
            onProgress?.(1);
            resolve();
          }
        };
        requestAnimationFrame(frame);
      });
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
  const w = Math.min(360, Math.max(140, text.length * 7.6 + 64));
  const lineCount = Math.max(1, Math.ceil(text.length * 7.6 / Math.max(1, w - 64)));
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
  const inflate = (rect: AnnotationRect): AnnotationRect => ({
    x: rect.x - SAFE_GAP,
    y: rect.y - SAFE_GAP,
    w: rect.w + SAFE_GAP * 2,
    h: rect.h + SAFE_GAP * 2,
  });
  const expandedOccupied = occupied.map(inflate);
  const directions = [
    {name: "right", rect: {x: target.x + target.w + SAFE_GAP, y: target.y + (target.h - size.h) / 2, ...size}},
    {name: "above", rect: {x: target.x + (target.w - size.w) / 2, y: target.y - size.h - SAFE_GAP, ...size}},
    {name: "below", rect: {x: target.x + (target.w - size.w) / 2, y: target.y + target.h + SAFE_GAP, ...size}},
    {name: "left", rect: {x: target.x - size.w - SAFE_GAP, y: target.y + (target.h - size.h) / 2, ...size}},
  ] as const;

  for (const direction of directions) {
    let rect = {...direction.rect};
    for (let attempt = 0; attempt < 128; attempt += 1) {
      if (!inBounds(rect, viewport.w, viewport.h)) break;
      const collision = expandedOccupied.find((item) => intersects(rect, item));
      if (!collision) {
        const distance = direction.name === "right" ? rect.x - (target.x + target.w)
          : direction.name === "left" ? target.x - (rect.x + rect.w)
          : direction.name === "above" ? target.y - (rect.y + rect.h)
          : rect.y - (target.y + target.h);
        return {rect, leader: distance > SAFE_GAP + 4};
      }
      if (direction.name === "right") rect.x = collision.x + collision.w;
      else if (direction.name === "left") rect.x = collision.x - rect.w;
      else if (direction.name === "above") rect.y = collision.y - rect.h;
      else rect.y = collision.y + collision.h;
    }
  }
  return null;
}

function inflateRect(rect: AnnotationRect, amount: number): AnnotationRect {
  return {x: rect.x - amount, y: rect.y - amount, w: rect.w + amount * 2, h: rect.h + amount * 2};
}

export function cursorRestBeside(
  target: AnnotationRect,
  occupied: AnnotationRect[],
  viewport: {w: number; h: number},
): CursorPoint {
  const belowRight = {x: target.x + target.w - 20, y: target.y + target.h + SAFE_GAP};
  const candidates = [
    belowRight,
    {x: target.x + target.w + SAFE_GAP, y: target.y + target.h / 2 - POINTER_SIZE.h / 2},
    {x: target.x - POINTER_SIZE.w + 20, y: belowRight.y},
    {x: belowRight.x, y: target.y - POINTER_SIZE.h - SAFE_GAP},
  ];
  const blockers = [target, ...occupied].map((rect) => inflateRect(rect, SAFE_GAP));
  const toCursor = (pill: CursorPoint): CursorPoint => ({
    x: pill.x - POINTER_OFFSET.x,
    y: pill.y - POINTER_OFFSET.y,
  });
  const isClear = (pill: CursorPoint) => {
    const rect = {...pill, w: POINTER_SIZE.w, h: POINTER_SIZE.h};
    return rect.x >= 0
      && rect.y >= 0
      && rect.x + rect.w <= viewport.w
      && rect.y + rect.h <= viewport.h
      && blockers.every((blocker) => !intersects(rect, blocker));
  };
  for (const candidate of candidates) {
    if (isClear(candidate)) return toCursor(candidate);
  }
  for (let attempt = 1; attempt <= 40; attempt += 1) {
    const candidate = {x: belowRight.x, y: belowRight.y + attempt * 8};
    if (isClear(candidate)) return toCursor(candidate);
  }
  return toCursor(belowRight);
}

function seededRandom(seed: number): () => number {
  let state = Math.floor((((seed % 1) + 1) % 1) * 0x100000000) >>> 0;
  return () => {
    let value = state += 0x6D2B79F5;
    value = Math.imul(value ^ value >>> 15, value | 1);
    value ^= value + Math.imul(value ^ value >>> 7, value | 61);
    return ((value ^ value >>> 14) >>> 0) / 0x100000000;
  };
}

export function seedFrom(id: string): number {
  let hash = 0x811C9DC5;
  for (let index = 0; index < id.length; index += 1) {
    hash ^= id.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0) / 0x100000000;
}

export function sketchEllipsePoints(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  seed: number,
  samples = 56,
): CursorPoint[] {
  const random = seededRandom(seed);
  const phaseA = random() * Math.PI * 2;
  const phaseB = random() * Math.PI * 2;
  const rotation = (-6 + random() * 4) * Math.PI / 180;
  const cosine = Math.cos(rotation);
  const sine = Math.sin(rotation);
  const paddedRx = rx + 6;
  const paddedRy = ry + 6;
  const start = -0.6 * Math.PI;
  const sweep = Math.PI * 2 + 0.35;
  return Array.from({length: Math.max(2, samples)}, (_, index) => {
    const angle = start + sweep * index / (Math.max(2, samples) - 1);
    const wobble = 1 + 0.02 * Math.sin(2 * angle + phaseA) + 0.02 * Math.sin(3 * angle + phaseB);
    const x = paddedRx * Math.cos(angle) * wobble;
    const y = paddedRy * Math.sin(angle) * wobble;
    return {x: cx + x * cosine - y * sine, y: cy + x * sine + y * cosine};
  });
}

export function sketchArrow(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  seed: number,
): {shaft: CursorPoint[]; head: [CursorPoint, CursorPoint, CursorPoint]} {
  const random = seededRandom(seed);
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.hypot(dx, dy);
  const perpendicular = length ? {x: -dy / length, y: dx / length} : {x: 0, y: 0};
  const bend = (0.06 + random() * 0.04) * length * (random() < 0.5 ? -1 : 1);
  const control = {x: (x1 + x2) / 2 + perpendicular.x * bend, y: (y1 + y2) / 2 + perpendicular.y * bend};
  const shaft = Array.from({length: 24}, (_, index) => {
    const t = index / 23;
    const remaining = 1 - t;
    return {
      x: remaining ** 2 * x1 + 2 * remaining * t * control.x + t ** 2 * x2,
      y: remaining ** 2 * y1 + 2 * remaining * t * control.y + t ** 2 * y2,
    };
  });
  const tangent = {x: x2 - control.x, y: y2 - control.y};
  const backAngle = Math.atan2(-tangent.y, -tangent.x);
  const wingLength = Math.min(14, 0.3 * length);
  const wing = (angle: number): CursorPoint => ({
    x: x2 + Math.cos(backAngle + angle) * wingLength,
    y: y2 + Math.sin(backAngle + angle) * wingLength,
  });
  return {shaft, head: [wing(-Math.PI / 180 * 28), {x: x2, y: y2}, wing(Math.PI / 180 * 28)]};
}

export function pointsToPath(points: CursorPoint[]): string {
  if (!points.length) return "";
  const position = (point: CursorPoint) => `${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  let path = `M ${position(points[0])}`;
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const midpoint = {x: (previous.x + current.x) / 2, y: (previous.y + current.y) / 2};
    path += ` Q ${position(previous)} ${position(midpoint)}`;
  }
  if (points.length > 1) path += ` Q ${position(points[points.length - 1])} ${position(points[points.length - 1])}`;
  return path;
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
