import type {ReactNode} from "react";

export type DesktopApp = "Photoshop" | "Notes" | "Mail" | "Musique" | "Photos";

const squircle = "M50 0C77.5 0 89 0 94.5 5.5S100 22.5 100 50s0 39-5.5 44.5S77.5 100 50 100s-39 0-44.5-5.5S0 77.5 0 50 0 11 5.5 5.5 22.5 0 50 0Z";
const tileTransform = "translate(9 9) scale(.82)";
const artworkTransform = "translate(9 9) scale(1.28125)";
const petals = ["#ff9500", "#ffcc00", "#a8d600", "#34c759", "#00b7a8", "#1689ff", "#8e5bdb", "#f05b9b"];

export function DesktopIcon({app, className = ""}: {app: DesktopApp; className?: string}) {
  const key = app.toLowerCase();
  const artwork: Record<DesktopApp, ReactNode> = {
    Photoshop: <g>
      <rect x="9" y="9" width="46" height="46" rx="8" fill="#00121F" stroke="#31A8FF" strokeWidth="2"/>
      <text x="13" y="40" fill="#31A8FF" fontSize="25" fontWeight="700" letterSpacing="-2">Ps</text>
    </g>,
    Notes: <g>
      <path d="M2 4Q2 2 5 2H59Q62 2 62 5V20H2Z" fill="url(#notes-band)"/>
      <path d="M8 23v3m6-3v3m6-3v3m6-3v3m6-3v3m6-3v3m6-3v3m6-3v3m6-3v3" stroke="#c7c7c7" strokeWidth="1" strokeDasharray="1 2"/>
      <path d="M12 34h40M12 43h40M12 52h30" stroke="#d7dce2" strokeWidth="1.6" strokeLinecap="round"/>
    </g>,
    Mail: <g filter="url(#mail-shadow)">
      <path d="M10 19h44v31H10z" fill="#fff"/>
      <path d="M11 21 32 38 53 21" fill="none" stroke="#68b7ff" strokeWidth="3" strokeLinejoin="round"/>
      <path d="m11 48 15-13m27 13L38 35" fill="none" stroke="#d9ebff" strokeWidth="2"/>
    </g>,
    Musique: <g fill="#fff">
      <ellipse cx="20" cy="47" rx="7" ry="5" transform="rotate(-20 20 47)"/>
      <ellipse cx="43" cy="39" rx="7" ry="5" transform="rotate(-20 43 39)"/>
      <path d="M25 17v27M48 13v25" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round"/>
      <path d="M25 17 48 12v6l-23 5z"/>
    </g>,
    Photos: <g style={{mixBlendMode: "multiply"}}>
      {petals.map((color, index) => <ellipse key={color} cx="32" cy="17" rx="6.5" ry="10.5" fill={color} opacity=".72" transform={`rotate(${index * 45} 32 32)`}/>)}
    </g>,
  };
  return <svg className={`desktop-icon-svg ${className}`} viewBox="0 0 100 100" aria-hidden="true">
    <defs>
      <linearGradient id={`${key}-base`} x1="0" y1="0" x2="0" y2="1">
        {app === "Photoshop" ? <><stop stopColor="#001E36"/><stop offset="1" stopColor="#00121F"/></>
          : app === "Mail" ? <><stop stopColor="#1E90FF"/><stop offset="1" stopColor="#0A6CF0"/></>
          : app === "Musique" ? <><stop stopColor="#FF5E7A"/><stop offset="1" stopColor="#FA233B"/></>
          : <><stop stopColor="#fff"/><stop offset="1" stopColor={app === "Notes" ? "#f4f4f4" : "#fff"}/></>}
      </linearGradient>
      <linearGradient id="notes-band" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#FFD84D"/><stop offset="1" stopColor="#FFC72C"/></linearGradient>
      <linearGradient id="base-shade" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stopColor="#fff" stopOpacity="0"/><stop offset="1" stopColor="#000" stopOpacity=".11"/></linearGradient>
      <linearGradient id="base-gloss" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#fff" stopOpacity=".12"/><stop offset=".5" stopColor="#fff" stopOpacity="0"/><stop offset="1" stopColor="#fff" stopOpacity="0"/></linearGradient>
      <filter id="mail-shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="#003b85" floodOpacity=".28"/></filter>
      <clipPath id={`${key}-clip`}><path d={squircle} transform={tileTransform}/></clipPath>
    </defs>
    <path d={squircle} transform={tileTransform} fill={`url(#${key}-base)`}/>
    <g clipPath={`url(#${key}-clip)`}>
      <g transform={artworkTransform}>{artwork[app]}</g>
      <path d={squircle} transform={tileTransform} fill="url(#base-shade)"/>
      <path d={squircle} transform={tileTransform} fill="url(#base-gloss)"/>
      <path d={squircle} transform={tileTransform} fill="none" stroke="rgba(255,255,255,.18)" strokeWidth="1.8"/>
    </g>
  </svg>;
}
