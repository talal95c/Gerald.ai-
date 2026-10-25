import {createRoot} from "react-dom/client";
import {useCallback, useEffect, useRef, useState} from "react";
import {DesktopIcon, type DesktopApp} from "./desktop-icons";
import {DesktopWindow} from "./desktop-window";
import {useCompanion} from "./companion";
import {mountNotch} from "./notch";
import "./desktop.css";

type WindowState = {open: boolean; minimized: boolean; x: number; y: number; width: number; height: number; zIndex: number; token: number};
type WindowMap = Partial<Record<"Photoshop" | "Notes", WindowState>>;
const dockApps: DesktopApp[] = ["Photoshop", "Notes", "Mail", "Musique", "Photos"];
const runningApps = ["Photoshop", "Notes"] as const;

document.body.classList.add("desktop-page");

function Desktop() {
  const [windows, setWindows] = useState<WindowMap>({});
  const [selected, setSelected] = useState<DesktopApp | null>(null);
  const [hovered, setHovered] = useState<DesktopApp | null>(null);
  const [bouncing, setBouncing] = useState<DesktopApp | null>(null);
  const [bounceKey, setBounceKey] = useState(0);
  const [focused, setFocused] = useState<"Photoshop" | "Notes" | null>(null);
  const notch = useRef<HTMLDivElement>(null);
  const notesFrame = useRef<HTMLIFrameElement>(null);
  const paintFrame = useRef<HTMLIFrameElement>(null);
  const zCounter = useRef(10);
  const cascade = useRef(0);
  const hotkeyHeld = useRef(false);
  const hotkeyTarget = useRef<"Photoshop" | "Notes" | null>(null);
  const demo = new URLSearchParams(location.search).get("demo") === "1";

  const usableArea = useCallback(() => {
    const top = 52;
    const bottom = Math.max(top, window.innerHeight - 112);
    return {top, bottom, height: bottom - top};
  }, []);
  const clampDrag = useCallback((x: number, y: number, width: number) => ({
    x: Math.max(0, Math.min(x, window.innerWidth - width)),
    y: Math.max(0, Math.min(y, window.innerHeight - 38)),
  }), []);
  const clampToUsable = useCallback((x: number, y: number, width: number, height: number, area: ReturnType<typeof usableArea>) => ({
    x: Math.max(0, Math.min(x, window.innerWidth - width)),
    y: Math.max(area.top, Math.min(y, area.bottom - height)),
  }), []);
  const openWindow = useCallback((app: "Photoshop" | "Notes") => {
    setWindows(previous => {
      const current = previous[app];
      const zIndex = ++zCounter.current;
      if (current?.open) return {...previous, [app]: {...current, minimized: false, zIndex}};
      const area = usableArea();
      const width = Math.min(1100, Math.max(0, window.innerWidth * .86 - 56));
      const height = Math.min(720, Math.max(0, area.height - 56));
      const startX = (window.innerWidth - width) / 2;
      const startY = area.top;
      const offset = cascade.current * 28;
      const fits = startX + offset + width <= window.innerWidth && startY + offset + height <= area.bottom;
      const position = clampToUsable(
        fits ? startX + offset : startX,
        fits ? startY + offset : startY,
        width,
        height,
        area,
      );
      cascade.current = fits ? cascade.current + 1 : 0;
      return {...previous, [app]: {open: true, minimized: false, ...position, width, height, zIndex, token: (current?.token ?? 0) + 1}};
    });
    setFocused(app);
  }, [clampToUsable, usableArea]);
  const focusWindow = useCallback((app: "Photoshop" | "Notes") => {
    setFocused(app);
    setWindows(previous => previous[app]?.open
      ? {...previous, [app]: {...previous[app]!, minimized: false, zIndex: ++zCounter.current}}
      : previous);
  }, []);
  const companion = useCompanion({demo, handleHotkeys: false, onActivate: () => openWindow("Notes")});
  const talkHandler = useRef<(pressed: boolean) => void>(() => undefined);
  const postHotkey = useCallback((app: "Photoshop" | "Notes", pressed: boolean) => {
    const frame = app === "Notes" ? notesFrame.current : paintFrame.current;
    frame?.contentWindow?.postMessage({type: "gerald-hotkey", pressed}, location.origin);
  }, []);
  const handleTalk = useCallback((pressed: boolean) => {
    if (pressed) {
      if (hotkeyHeld.current) return;
      let target = focused;
      if (!target || !windows[target]?.open || windows[target]?.minimized) {
        const visible = runningApps.filter(app => windows[app]?.open && !windows[app]?.minimized)
          .sort((a, b) => (windows[b]?.zIndex ?? 0) - (windows[a]?.zIndex ?? 0))[0] ?? null;
        target = visible ?? "Notes";
        openWindow(target);
        if (!visible) companion.openLiveBoard(false);
      }
      hotkeyHeld.current = true;
      hotkeyTarget.current = target;
      postHotkey(target, true);
      return;
    }
    if (!hotkeyHeld.current) return;
    hotkeyHeld.current = false;
    if (hotkeyTarget.current) postHotkey(hotkeyTarget.current, false);
    hotkeyTarget.current = null;
  }, [companion.openLiveBoard, companion.src, focused, openWindow, postHotkey, windows]);
  talkHandler.current = handleTalk;
  const stableTalk = useCallback((pressed: boolean) => talkHandler.current(pressed), []);

  useEffect(() => {
    if (notch.current) mountNotch(notch.current, stableTalk);
  }, [stableTalk]);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (!event.ctrlKey || !event.shiftKey || event.repeat || hotkeyHeld.current) return;
      event.preventDefault();
      stableTalk(true);
    };
    const up = (event: KeyboardEvent) => {
      if (event.key === "Control" || event.key === "Shift") stableTalk(false);
    };
    const blur = () => stableTalk(false);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, [stableTalk]);

  useEffect(() => {
    const ready = (event: MessageEvent) => {
      if (event.origin !== location.origin || event.data?.type !== "gerald-ready" || !hotkeyHeld.current) return;
      const target = hotkeyTarget.current;
      const frame = target === "Notes" ? notesFrame.current : target === "Photoshop" ? paintFrame.current : null;
      if (frame?.contentWindow === event.source && target) postHotkey(target, true);
    };
    window.addEventListener("message", ready);
    return () => window.removeEventListener("message", ready);
  }, [postHotkey]);

  useEffect(() => {
    const reclamp = () => {
      const area = usableArea();
      setWindows(previous => {
        const next = {...previous};
        runningApps.forEach(app => {
          const item = previous[app];
          if (!item?.open) return;
          const width = Math.min(item.width, window.innerWidth * .86, 1100);
          const height = Math.min(item.height, area.height, 720);
          const position = clampToUsable(item.x, item.y, width, height, area);
          next[app] = {...item, ...position, width, height};
        });
        return next;
      });
    };
    window.addEventListener("resize", reclamp);
    return () => window.removeEventListener("resize", reclamp);
  }, [clampToUsable, usableArea]);

  const openApp = (app: DesktopApp) => {
    setSelected(app);
    if (app === "Mail" || app === "Musique" || app === "Photos") {
      setBouncing(app);
      setBounceKey(value => value + 1);
      window.setTimeout(() => setBouncing(current => current === app ? null : current), 600);
      return;
    }
    if (app === "Notes" && !companion.src) companion.openLiveBoard(false);
    openWindow(app);
  };
  const moveWindow = (app: "Photoshop" | "Notes", x: number, y: number) => {
    setWindows(previous => {
      const item = previous[app];
      if (!item) return previous;
      return {...previous, [app]: {...item, ...clampDrag(x, y, item.width)}};
    });
  };
  const closeWindow = (app: "Photoshop" | "Notes") => {
    setWindows(previous => {
      const next = {...previous, [app]: {...previous[app]!, open: false, minimized: false}};
      const nextFocus = runningApps
        .filter(name => name !== app && next[name]?.open && !next[name]?.minimized)
        .sort((a, b) => (next[b]?.zIndex ?? 0) - (next[a]?.zIndex ?? 0))[0] ?? null;
      setFocused(nextFocus);
      return next;
    });
  };
  const minimizeWindow = (app: "Photoshop" | "Notes") => {
    setWindows(previous => {
      const next = {...previous, [app]: {...previous[app]!, minimized: true}};
      if (focused === app) {
        const nextFocus = runningApps.filter(name => name !== app && next[name]?.open && !next[name]?.minimized)
          .sort((a, b) => (next[b]?.zIndex ?? 0) - (next[a]?.zIndex ?? 0))[0] ?? null;
        setFocused(nextFocus);
      }
      return next;
    });
  };
  const hoverIndex = hovered ? dockApps.indexOf(hovered) : -1;

  return <main className="desktop-stage" onPointerDown={event=>{if(event.target===event.currentTarget)setSelected(null);}}>
    <div className="desktop-shortcuts">
      {(["Photoshop", "Notes"] as const).map(app=><button
        type="button" key={app} className={`desktop-shortcut${selected===app?" selected":""}`}
        onClick={()=>setSelected(app)} onDoubleClick={()=>openApp(app)} aria-label={`Open ${app}`}
      ><DesktopIcon app={app}/><span>{app}</span></button>)}
    </div>
    {runningApps.map(app=>{
      const item=windows[app];
      if(!item?.open)return null;
      return <DesktopWindow
        key={`${app}-${item.token}`} app={app} title={app} x={item.x} y={item.y} width={item.width} height={item.height}
        zIndex={item.zIndex} minimized={item.minimized} entering onFocus={()=>focusWindow(app)}
        onMove={(x,y)=>moveWindow(app,x,y)} onClose={()=>closeWindow(app)} onMinimize={()=>minimizeWindow(app)}
      >
        {app==="Notes"
          ? companion.src && <iframe key={companion.src} ref={notesFrame} title="Notes" src={companion.src} allow="microphone; autoplay" onFocus={()=>focusWindow("Notes")} onLoad={()=>{if(hotkeyHeld.current&&hotkeyTarget.current==="Notes")postHotkey("Notes",true);}}/>
          : <iframe ref={paintFrame} title="Photoshop" src={`./td.html?voice=1&embed=1&app=paint${demo?"&demo=1":""}`} allow="microphone; autoplay" onFocus={()=>focusWindow("Photoshop")} onLoad={()=>{if(hotkeyHeld.current&&hotkeyTarget.current==="Photoshop")postHotkey("Photoshop",true);}}/>}
      </DesktopWindow>;
    })}
    <div className="desktop-notch-host" ref={notch}/>
    <nav className="desktop-dock" aria-label="Applications">
      {dockApps.map((app,index)=><span key={app} className="dock-entry">
        {index===2&&<i className="dock-divider" aria-hidden="true"/>}
        <button type="button" className={`dock-item${hovered===app?" hovered":""}${Math.abs(hoverIndex-index)===1?" neighbor":""}${bouncing===app?" bouncing":""}`}
          style={bouncing===app?{animationDelay:`${bounceKey%2*1}ms`}:undefined}
          onMouseEnter={()=>setHovered(app)} onMouseLeave={()=>setHovered(null)}
          onClick={()=>openApp(app)} aria-label={app}>
          <span className="dock-label">{app}</span><DesktopIcon app={app}/>
          {(app==="Notes"||app==="Photoshop")&&windows[app]?.open&&<i className="dock-running" aria-label="Running"/>}
        </button>
      </span>)}
    </nav>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Desktop/>);
