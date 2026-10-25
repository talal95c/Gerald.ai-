import {useCallback, useEffect, useRef, useState} from "react";
import type {RefObject} from "react";

type Exercise = {title: string; lines: string[]};

export type Companion = {
  src: string | null;
  frame: RefObject<HTMLIFrameElement | null>;
  openLiveBoard: (activate?: boolean) => void;
  sendHotkey: (pressed: boolean) => void;
  onFrameLoad: () => void;
};

export function useCompanion({
  demo = new URLSearchParams(location.search).get("demo") === "1",
  handleHotkeys = true,
  onActivate,
}: {
  demo?: boolean;
  handleHotkeys?: boolean;
  onActivate?: () => void;
} = {}): Companion {
  const [src, setSrc] = useState<string | null>(null);
  const srcRef = useRef<string | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const held = useRef(false);
  const lastExercise = useRef<Exercise | null>(null);
  const updateSrc = useCallback((next: string) => {
    srcRef.current = next;
    setSrc(next);
  }, []);
  const withDemo = useCallback((url: string) => {
    if (!demo) return url;
    const [path, query = ""] = url.split("?");
    const params = new URLSearchParams(query);
    params.set("demo", "1");
    return `${path}?${params}`;
  }, [demo]);
  const sendHotkey = useCallback((pressed: boolean) => {
    frame.current?.contentWindow?.postMessage({type: "gerald-hotkey", pressed}, location.origin);
  }, []);
  const openLiveBoard = useCallback((activate = true) => {
    updateSrc(withDemo("./td.html?voice=1&embed=1&live=1"));
    if (activate) onActivate?.();
  }, [onActivate, updateSrc, withDemo]);
  const openDocument = useCallback((id: number) => {
    const url = id === -4
      ? "./td.html?voice=1&embed=1"
      : `./td.html?voice=1&embed=1&doc=${encodeURIComponent(id)}`;
    updateSrc(withDemo(url));
    onActivate?.();
  }, [onActivate, updateSrc, withDemo]);
  const openBoard = useCallback((detail: {title?: string; lines?: string[]} | null) => {
    const lines = Array.isArray(detail?.lines) ? detail.lines.map(String) : [];
    const exercise = detail?.title && lines.length ? {title: detail.title, lines} : lastExercise.current;
    if (!exercise) {
      openLiveBoard();
      return;
    }
    const params = new URLSearchParams({
      voice: "1",
      embed: "1",
      board: "1",
      title: exercise.title,
      lines: JSON.stringify(exercise.lines),
    });
    updateSrc(withDemo(`./td.html?${params}`));
    onActivate?.();
  }, [onActivate, openLiveBoard, updateSrc, withDemo]);
  const onFrameLoad = useCallback(() => {
    if (held.current) sendHotkey(true);
  }, [sendHotkey]);

  useEffect(() => {
    const documentOpen = (event: Event) => {
      const id = Number((event as CustomEvent<{id: number}>).detail?.id);
      if (Number.isFinite(id)) openDocument(id);
    };
    const boardOpen = (event: Event) => openBoard((event as CustomEvent<Exercise>).detail ?? null);
    const message = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) return;
      if (event.data?.type === "gerald-ready") {
        if (held.current) sendHotkey(true);
        return;
      }
      if (event.data?.type !== "gerald-last-exercise") return;
      lastExercise.current = {
        title: String(event.data.title),
        lines: Array.isArray(event.data.lines) ? event.data.lines.map(String) : [],
      };
    };
    window.addEventListener("gerald-open-document", documentOpen);
    window.addEventListener("gerald-open-board", boardOpen);
    window.addEventListener("message", message);
    return () => {
      window.removeEventListener("gerald-open-document", documentOpen);
      window.removeEventListener("gerald-open-board", boardOpen);
      window.removeEventListener("message", message);
    };
  }, [openBoard, openDocument, sendHotkey]);

  useEffect(() => {
    if (!handleHotkeys) return;
    const down = (event: KeyboardEvent) => {
      if (!event.ctrlKey || !event.shiftKey || event.repeat || held.current) return;
      event.preventDefault();
      held.current = true;
      if (!srcRef.current) openLiveBoard(false);
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
  }, [handleHotkeys, openLiveBoard, sendHotkey]);

  return {src, frame, openLiveBoard, sendHotkey, onFrameLoad};
}
