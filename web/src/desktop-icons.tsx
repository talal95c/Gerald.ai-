import type {ReactNode} from "react";

export type DesktopApp = "Photoshop" | "Notes" | "Mail" | "Musique" | "Photos";

const squircle = "M32 1C12.5 1 1 12.5 1 32s11.5 31 31 31 31-11.5 31-31S51.5 1 32 1Z";
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
      <path d="M25 17v27.5a7.5 7.5 0 1 1-4.5-6.9V21l26-6v28.5a7.5 7.5 0 1 1-4.5-6.9V20z"/>
      <path d="M43 15v4l8-2v-4z"/>
    </g>,
    Photos: <g style={{mixBlendMode: "multiply"}}>
      {petals.map((color, index) => <ellipse key={color} cx="32" cy="17" rx="7.5" ry="12.5" fill={color} opacity=".72" transform={`rotate(${index * 45} 32 32)`}/>)}
    </g>,
  };
  return <svg className={`desktop-icon-svg ${className}`} viewBox="0 0 64 64" aria-hidden="true">
    <defs>
      <linearGradient id={`${key}-base`} x1="0" y1="0" x2="0" y2="1">
        {app === "Photoshop" ? <><stop stopColor="#001E36"/><stop offset="1" stopColor="#00121F"/></>
          : app === "Mail" ? <><stop stopColor="#1E90FF"/><stop offset="1" stopColor="#0A6CF0"/></>
          : app === "Musique" ? <><stop stopColor="#FF5E7A"/><stop offset="1" stopColor="#FA233B"/></>
          : <><stop stopColor="#fff"/><stop offset="1" stopColor={app === "Notes" ? "#f4f4f4" : "#fff"}/></>}
      </linearGradient>
      <linearGradient id="notes-band" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#FFD84D"/><stop offset="1" stopColor="#FFC72C"/></linearGradient>
      <linearGradient id="base-shade" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stopColor="#fff" stopOpacity="0"/><stop offset="1" stopColor="#000" stopOpacity=".11"/></linearGradient>
      <filter id="mail-shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="#003b85" floodOpacity=".28"/></filter>
      <clipPath id={`${key}-clip`}><path d={squircle}/></clipPath>
    </defs>
    <path d={squircle} fill={`url(#${key}-base)`}/>
    <g clipPath={`url(#${key}-clip)`}>{artwork[app]}<path d={squircle} fill="url(#base-shade)"/></g>
    <path d="M32 1.5C13 1.5 1.5 13 1.5 32" fill="none" stroke="#fff" strokeOpacity=".62" strokeWidth="1"/>
  </svg>;
}
