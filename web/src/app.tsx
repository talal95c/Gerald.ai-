import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { mountNotch } from "./notch";
import "./app.css";

type Exercise = {title: string; lines: string[]};
const LIVE_BOARD = "./td.html?voice=1&embed=1&live=1";

function App() {
  const [src, setSrc] = useState<string | null>(null);
  const notch = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const held = useRef(false);
  const lastExercise = useRef<Exercise | null>(null);

  useEffect(() => {
    if (notch.current) mountNotch(notch.current);
    const openDocument = (event: Event) => {
      const id = Number((event as CustomEvent<{id: number}>).detail?.id);
      if (!Number.isFinite(id)) return;
      setSrc(id === -4
        ? "./td.html?voice=1&embed=1"
        : `./td.html?voice=1&embed=1&doc=${encodeURIComponent(id)}`);
    };
    const openBoard = (event: Event) => {
      const detail = (event as CustomEvent<Exercise>).detail;
      const exercise = detail?.title && detail.lines?.length ? detail : lastExercise.current;
      if (!exercise) {
        setSrc(LIVE_BOARD);
        return;
      }
      const params = new URLSearchParams({
        voice: "1",
        embed: "1",
        board: "1",
        title: exercise.title,
        lines: JSON.stringify(exercise.lines),
      });
      setSrc(`./td.html?${params}`);
    };
    const message = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) return;
      if (event.data?.type === "gerald-last-exercise") {
        lastExercise.current = {title: String(event.data.title), lines: Array.isArray(event.data.lines) ? event.data.lines.map(String) : []};
      }
    };
    window.addEventListener("gerald-open-document", openDocument);
    window.addEventListener("gerald-open-board", openBoard);
    window.addEventListener("message", message);
    return () => {
      window.removeEventListener("gerald-open-document", openDocument);
      window.removeEventListener("gerald-open-board", openBoard);
      window.removeEventListener("message", message);
    };
  }, []);

  useEffect(() => {
    const sendHotkey = (pressed: boolean) => frame.current?.contentWindow?.postMessage(
      {type: "gerald-hotkey", pressed},
      location.origin,
    );
    const down = (event: KeyboardEvent) => {
      if (!event.ctrlKey || !event.shiftKey || event.repeat || held.current) return;
      event.preventDefault();
      held.current = true;
      if (!src) setSrc(LIVE_BOARD);
      else sendHotkey(true);
    };
    const up = (event: KeyboardEvent) => {
      if ((event.key !== "Control" && event.key !== "Shift") || !held.current) return;
      held.current = false;
      sendHotkey(false);
    };
    const blur = () => {
      if (!held.current) return;
      held.current = false;
      sendHotkey(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, [src]);

  return <main className="app-root">
    {src && <iframe
      key={src}
      ref={frame}
      className="app-frame"
      title="Gerald"
      src={src}
      allow="microphone; autoplay"
      onLoad={() => {
        if (held.current) frame.current?.contentWindow?.postMessage({type: "gerald-hotkey", pressed: true}, location.origin);
      }}
    />}
    <div className="app-notch-host" ref={notch}/>
  </main>;
}

document.body.classList.add("app-page");
createRoot(document.getElementById("root")!).render(<App/>);
