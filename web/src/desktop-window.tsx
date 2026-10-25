import {useRef, useState, type PointerEvent, type ReactNode} from "react";

type ResizeDirection = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
type WindowRect = {x: number; y: number; width: number; height: number};

export function DesktopWindow({
  title, x, y, width, height, zIndex, minimized, maximized, zoomTransition, phase, originX, originY,
  focused, onFocus, onMove, onResize, onRestoreForDrag, onZoom, onClose, onMinimize, onAnimationEnd, children,
}: {
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  minimized: boolean;
  maximized: boolean;
  zoomTransition: boolean;
  phase: "opening" | "minimizing" | "restoring" | "closing" | null;
  originX: number;
  originY: number;
  focused: boolean;
  onFocus: () => void;
  onMove: (x: number, y: number) => void;
  onResize: (x: number, y: number, width: number, height: number) => void;
  onRestoreForDrag: (clientX: number, clientY: number, grabX: number, grabY: number) => WindowRect;
  onZoom: () => void;
  onClose: () => void;
  onMinimize: () => void;
  onAnimationEnd: (phase: "opening" | "minimizing" | "restoring" | "closing") => void;
  children: ReactNode;
}) {
  const [dragging, setDragging] = useState(false);
  const [resizing, setResizing] = useState(false);
  const drag = useRef<{pointerId: number; x: number; y: number; left: number; top: number; wasMaximized: boolean; grabX: number; grabY: number} | null>(null);
  const resize = useRef<{pointerId: number; direction: ResizeDirection; x: number; y: number; rect: WindowRect} | null>(null);
  const start = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    onFocus();
    setDragging(true);
    drag.current = {
      pointerId: event.pointerId, x: event.clientX, y: event.clientY, left: x, top: y,
      wasMaximized: maximized, grabX: event.clientX - x, grabY: event.clientY - y,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const current = drag.current;
    if (!dragging || !current || current.pointerId !== event.pointerId) return;
    const dx = event.clientX - current.x;
    const dy = event.clientY - current.y;
    if (current.wasMaximized) {
      if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
      const restored = onRestoreForDrag(event.clientX, event.clientY, current.grabX, current.grabY);
      drag.current = {...current, x: event.clientX, y: event.clientY, left: restored.x, top: restored.y, wasMaximized: false};
      onMove(restored.x, restored.y);
      return;
    }
    onMove(current.left + dx, current.top + dy);
  };
  const stop = (event: PointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId !== event.pointerId) return;
    drag.current = null;
    setDragging(false);
  };
  const startResize = (direction: ResizeDirection, event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    onFocus();
    resize.current = {pointerId: event.pointerId, direction, x: event.clientX, y: event.clientY, rect: {x, y, width, height}};
    setResizing(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const resizeMove = (event: PointerEvent<HTMLDivElement>) => {
    const current = resize.current;
    if (!resizing || !current || current.pointerId !== event.pointerId) return;
    const dx = event.clientX - current.x;
    const dy = event.clientY - current.y;
    let nextX = current.rect.x;
    let nextY = current.rect.y;
    let nextWidth = current.rect.width;
    let nextHeight = current.rect.height;
    if (current.direction.includes("e")) nextWidth = Math.max(480, current.rect.width + dx);
    if (current.direction.includes("s")) nextHeight = Math.max(320, current.rect.height + dy);
    if (current.direction.includes("w")) {
      nextWidth = Math.max(480, current.rect.width - dx);
      nextX = current.rect.x + current.rect.width - nextWidth;
    }
    if (current.direction.includes("n")) {
      nextHeight = Math.max(320, current.rect.height - dy);
      nextY = current.rect.y + current.rect.height - nextHeight;
    }
    onResize(nextX, nextY, nextWidth, nextHeight);
  };
  const stopResize = (event: PointerEvent<HTMLDivElement>) => {
    if (resize.current?.pointerId !== event.pointerId) return;
    resize.current = null;
    setResizing(false);
  };
  const directions: ResizeDirection[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];
  return <section
    className={`desktop-window${dragging ? " dragging" : ""}${resizing ? " resizing" : ""}${minimized ? " minimized" : ""}${maximized ? " maximized" : ""}${zoomTransition && !dragging && !resizing ? " zoom-transition" : ""}${phase ? ` phase-${phase}` : ""}${focused ? " focused" : ""}`}
    style={{left: x, top: y, width, height, zIndex, transformOrigin: `${originX}px ${originY}px`}}
    onPointerDown={onFocus}
    onAnimationEnd={event=>{if(event.target===event.currentTarget&&phase)onAnimationEnd(phase);}}
    aria-label={`${title} window`}
  >
    <div className="desktop-window-titlebar" onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onLostPointerCapture={stop}
      onDoubleClick={event=>{if(event.target instanceof Element&&event.target.closest("button"))return;event.preventDefault();onFocus();onZoom();}}>
      <div className="desktop-window-controls">
        <button className="window-light close" type="button" aria-label={`Close ${title}`} onPointerDown={event=>event.stopPropagation()} onClick={onClose}/>
        <button className="window-light minimize" type="button" aria-label={`Minimize ${title}`} onPointerDown={event=>event.stopPropagation()} onClick={onMinimize}/>
        <button className="window-light zoom" type="button" aria-label={`Zoom ${title}`} onPointerDown={event=>event.stopPropagation()} onClick={()=>{onFocus();onZoom();}}/>
      </div>
      <span className="window-title">{title}</span>
    </div>
    <div className="desktop-window-body">{children}</div>
    {!maximized && directions.map(direction=><div
      key={direction} className={`window-resize-handle resize-${direction}`} aria-hidden="true"
      onPointerDown={event=>startResize(direction,event)} onPointerMove={resizeMove}
      onPointerUp={stopResize} onPointerCancel={stopResize} onLostPointerCapture={stopResize}
    />)}
  </section>;
}
