import {createRoot} from "react-dom/client";
import {useCallback, useEffect, useRef, useState} from "react";
import {DesktopIcon, type DesktopApp} from "./desktop-icons";
import {DesktopAppContent} from "./desktop-apps";
import {DesktopWindow} from "./desktop-window";
import {useCompanion} from "./companion";
import {mountNotch} from "./notch";
import "./desktop.css";

type WindowPhase = "opening" | "minimizing" | "restoring" | "closing" | null;
type WindowState = {open: boolean; minimized: boolean; x: number; y: number; width: number; height: number; zIndex: number; token: number; phase: WindowPhase; originX: number; originY: number};
type WindowMap = Partial<Record<DesktopApp, WindowState>>;
const dockApps: DesktopApp[] = ["Photoshop", "Notes", "Mail", "Musique", "Photos"];
const runningApps = dockApps;
const voiceApps = ["Photoshop", "Notes"] as const;

document.body.classList.add("desktop-page");

function Desktop() {
  const [windows, setWindows] = useState<WindowMap>({});
  const [selected, setSelected] = useState<DesktopApp | null>(null);
  const [hovered, setHovered] = useState<DesktopApp | null>(null);
  const [bouncing, setBouncing] = useState<DesktopApp | null>(null);
  const [bounceKey, setBounceKey] = useState(0);
  const [focused, setFocused] = useState<DesktopApp | null>(null);
  const [now, setNow] = useState(new Date());
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
  const openWindow = useCallback((app: DesktopApp) => {
    setWindows(previous => {
      const current = previous[app];
      const zIndex = ++zCounter.current;
      if (current?.open) return {...previous, [app]: {...current, minimized: false, zIndex, phase: current.minimized ? "restoring" : null}};
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
      const dock = document.querySelector<HTMLElement>(`.dock-item[aria-label="${app}"]`)?.getBoundingClientRect();
      return {...previous, [app]: {
        open: true, minimized: false, ...position, width, height, zIndex,
        token: (current?.token ?? 0) + 1, phase: "opening",
        originX: dock ? dock.left + dock.width / 2 - position.x : width / 2,
        originY: dock ? dock.top + dock.height / 2 - position.y : height / 2,
      }};
    });
    setFocused(app);
  }, [clampToUsable, usableArea]);
  const focusWindow = useCallback((app: DesktopApp) => {
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
      let target = focused && voiceApps.includes(focused as "Photoshop" | "Notes") ? focused as "Photoshop" | "Notes" : null;
      if (!target || !windows[target]?.open || windows[target]?.minimized) {
        const visible = voiceApps.filter(app => windows[app]?.open && !windows[app]?.minimized)
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
    const update = () => setNow(new Date());
    const timer = window.setInterval(update, 60000);
    return () => window.clearInterval(timer);
  }, []);

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
          const width = Math.min(item.width, window.innerWidth * .86 - 56, 1100);
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
    if (!windows[app]?.open) {
      setBouncing(app);
      setBounceKey(value => value + 1);
      window.setTimeout(() => setBouncing(current => current === app ? null : current), 700);
    }
    if (app === "Notes" && !companion.src) companion.openLiveBoard(false);
    openWindow(app);
  };
  const moveWindow = (app: DesktopApp, x: number, y: number) => {
    setWindows(previous => {
      const item = previous[app];
      if (!item) return previous;
      return {...previous, [app]: {...item, ...clampDrag(x, y, item.width)}};
    });
  };
  const closeWindow = (app: DesktopApp) => {
    setWindows(previous => {
      const next = {...previous, [app]: {...previous[app]!, phase: "closing" as const}};
      const nextFocus = runningApps
        .filter(name => name !== app && next[name]?.open && !next[name]?.minimized)
        .sort((a, b) => (next[b]?.zIndex ?? 0) - (next[a]?.zIndex ?? 0))[0] ?? null;
      setFocused(nextFocus);
      return next;
    });
  };
  const minimizeWindow = (app: DesktopApp) => {
    setWindows(previous => {
      const next = {...previous, [app]: {...previous[app]!, phase: "minimizing" as const}};
      if (focused === app) {
        const nextFocus = runningApps.filter(name => name !== app && next[name]?.open && !next[name]?.minimized)
          .sort((a, b) => (next[b]?.zIndex ?? 0) - (next[a]?.zIndex ?? 0))[0] ?? null;
        setFocused(nextFocus);
      }
      return next;
    });
  };
  const finishAnimation = (app: DesktopApp, phase: Exclude<WindowPhase, null>) => {
    setWindows(previous => {
      const item = previous[app];
      if (!item || item.phase !== phase) return previous;
      if (phase === "closing") return {...previous, [app]: {...item, open: false, minimized: false, phase: null}};
      if (phase === "minimizing") return {...previous, [app]: {...item, minimized: true, phase: null}};
      return {...previous, [app]: {...item, phase: null}};
    });
  };
  const hoverIndex = hovered ? dockApps.indexOf(hovered) : -1;
  const clock = new Intl.DateTimeFormat("fr-FR", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(now).replace(",", "").replace(" à ", " ");

  return <main className="desktop-stage" onPointerDown={event=>{if(event.target===event.currentTarget)setSelected(null);}}>
    <header className="desktop-menubar">
      <div className="menu-left">
        <svg className="menu-gerald" viewBox="0 0 24 16" aria-hidden="true"><rect x="2" y="2" width="6" height="12" rx="3" fill="currentColor"/><circle cx="17" cy="8" r="6" fill="currentColor"/></svg>
        <strong>{focused ?? "Finder"}</strong>
        <nav><span>Fichier</span><span>Édition</span><span>Présentation</span><span>Fenêtre</span><span>Aide</span></nav>
      </div>
      <div className="menu-right">
        <svg viewBox="0 0 20 16" aria-label="Wi-Fi"><path d="M2 5a12 12 0 0 1 16 0M5 8a7.5 7.5 0 0 1 10 0m-7 3a3.5 3.5 0 0 1 4 0M10 14h.01" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
        <svg viewBox="0 0 24 14" aria-label="Batterie 82%"><rect x="1" y="1" width="19" height="12" rx="3" fill="none" stroke="currentColor" strokeWidth="1.4"/><path d="M22 5v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/><rect x="3" y="3" width="14" height="8" rx="1.5" fill="currentColor"/></svg>
        <time>{clock}</time>
      </div>
    </header>
    <div className="desktop-shortcuts">
      {(["Photoshop", "Notes"] as const).map(app=><button
        type="button" key={app} className={`desktop-shortcut${selected===app?" selected":""}`}
        onClick={()=>setSelected(app)} onDoubleClick={()=>openApp(app)} aria-label={`Open ${app}`}
      ><DesktopIcon app={app}/><span>{app}</span></button>)}
    </div>
    {runningApps.map(app=>{
      const item=windows[app];
      if(!item?.open||item.minimized)return null;
      return <DesktopWindow
        key={`${app}-${item.token}`} title={app} x={item.x} y={item.y} width={item.width} height={item.height}
        zIndex={item.zIndex} minimized={item.minimized} phase={item.phase} originX={item.originX} originY={item.originY}
        focused={focused===app} onFocus={()=>focusWindow(app)} onMove={(x,y)=>moveWindow(app,x,y)}
        onClose={()=>closeWindow(app)} onMinimize={()=>minimizeWindow(app)} onAnimationEnd={phase=>finishAnimation(app,phase)}
      >
        {app==="Notes"
          ? companion.src && <iframe key={companion.src} ref={notesFrame} title="Notes" src={companion.src} allow="microphone; autoplay" onFocus={()=>focusWindow("Notes")} onLoad={()=>{if(hotkeyHeld.current&&hotkeyTarget.current==="Notes")postHotkey("Notes",true);}}/>
          : app==="Photoshop"
            ? <iframe ref={paintFrame} title="Photoshop" src={`./td.html?voice=1&embed=1&app=paint${demo?"&demo=1":""}`} allow="microphone; autoplay" onFocus={()=>focusWindow("Photoshop")} onLoad={()=>{if(hotkeyHeld.current&&hotkeyTarget.current==="Photoshop")postHotkey("Photoshop",true);}}/>
            : <DesktopAppContent app={app}/>}
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
          {windows[app]?.open&&<i className="dock-running" aria-label="Running"/>}
        </button>
      </span>)}
    </nav>
  </main>;
}

createRoot(document.getElementById("root")!).render(<Desktop/>);
