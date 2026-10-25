import {useRef, useState, type PointerEvent, type ReactNode} from "react";

export function DesktopWindow({
  title, x, y, width, height, zIndex, minimized, phase, originX, originY, focused, onFocus, onMove, onClose, onMinimize, onAnimationEnd, children,
}: {
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex: number;
  minimized: boolean;
  phase: "opening" | "minimizing" | "restoring" | "closing" | null;
  originX: number;
  originY: number;
  focused: boolean;
  onFocus: () => void;
  onMove: (x: number, y: number) => void;
  onClose: () => void;
  onMinimize: () => void;
  onAnimationEnd: (phase: "opening" | "minimizing" | "restoring" | "closing") => void;
  children: ReactNode;
}) {
  const [dragging, setDragging] = useState(false);
  const drag = useRef({x: 0, y: 0, left: 0, top: 0});
  const start = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    onFocus();
    setDragging(true);
    drag.current = {x: event.clientX, y: event.clientY, left: x, top: y};
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const move = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    onMove(drag.current.left + event.clientX - drag.current.x, drag.current.top + event.clientY - drag.current.y);
  };
  const stop = () => setDragging(false);
  return <section
    className={`desktop-window${dragging ? " dragging" : ""}${minimized ? " minimized" : ""}${phase ? ` phase-${phase}` : ""}${focused ? " focused" : ""}`}
    style={{left: x, top: y, width, height, zIndex, transformOrigin: `${originX}px ${originY}px`}}
    onPointerDown={onFocus}
    onAnimationEnd={event=>{if(event.target===event.currentTarget&&phase)onAnimationEnd(phase);}}
    aria-label={`${title} window`}
  >
    <div className="desktop-window-titlebar" onPointerDown={start} onPointerMove={move} onPointerUp={stop} onPointerCancel={stop} onLostPointerCapture={stop}>
      <div className="desktop-window-controls">
        <button className="window-light close" type="button" aria-label={`Close ${title}`} onPointerDown={event=>event.stopPropagation()} onClick={onClose}/>
        <button className="window-light minimize" type="button" aria-label={`Minimize ${title}`} onPointerDown={event=>event.stopPropagation()} onClick={onMinimize}/>
      </div>
      <span className="window-title">{title}</span>
    </div>
    <div className="desktop-window-body">{children}</div>
  </section>;
}
