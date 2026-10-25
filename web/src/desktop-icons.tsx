import type {ReactNode} from "react";

export type DesktopApp = "Photoshop" | "Notes" | "Mail" | "Musique" | "Photos";

export function DesktopIcon({app, className = ""}: {app: DesktopApp; className?: string}) {
  const svg: Record<DesktopApp, ReactNode> = {
    Photoshop: <><rect width="64" height="64" rx="16" fill="#001E36"/><text x="8" y="41" fill="#31A8FF" fontSize="27" fontWeight="700" letterSpacing="-2">Ps</text></>,
    Notes: <><rect width="64" height="64" rx="16" fill="url(#note)"/><path d="M0 16Q0 0 16 0h32q16 0 16 16v4H0z" fill="#F4D35E"/><path d="M13 31h38M13 40h38M13 49h28" stroke="#9B9B9B" strokeWidth="2" strokeLinecap="round"/></>,
    Mail: <><rect width="64" height="64" rx="16" fill="url(#mail)"/><path d="M12 20h40v28H12z" fill="#fff" opacity=".96"/><path d="m13 22 19 16 19-16" fill="none" stroke="#70B8FF" strokeWidth="3" strokeLinejoin="round"/><path d="M13 47 27 35m24 12L37 35" stroke="#D9ECFF" strokeWidth="2"/></>,
    Musique: <><rect width="64" height="64" rx="16" fill="url(#music)"/><path d="M39 13v28a8 8 0 1 1-5-7V20l18-4v23a8 8 0 1 1-5-7V11z" fill="#fff"/></>,
    Photos: <><rect width="64" height="64" rx="16" fill="#fff"/>{["#EA4335","#FBBC05","#34A853","#4285F4","#9C5DE5","#F06292"].map((color,i)=><ellipse key={color} cx="32" cy="18" rx="7" ry="12" fill={color} transform={`rotate(${i*60} 32 32)`}/>)}<circle cx="32" cy="32" r="5" fill="#fff"/></>,
  };
  const defs = app === "Notes"
    ? <defs><linearGradient id="note" x2="0" y2="1"><stop stopColor="#fff"/><stop offset="1" stopColor="#FFF7CC"/></linearGradient></defs>
    : app === "Mail"
      ? <defs><linearGradient id="mail" x2="1" y2="1"><stop stopColor="#5DBBFF"/><stop offset="1" stopColor="#1673D1"/></linearGradient></defs>
      : app === "Musique"
        ? <defs><linearGradient id="music" x2="1" y2="1"><stop stopColor="#F76DA5"/><stop offset="1" stopColor="#D92756"/></linearGradient></defs>
        : null;
  return <svg className={`desktop-icon-svg ${className}`} viewBox="0 0 64 64" aria-hidden="true">{defs}{svg[app]}</svg>;
}
