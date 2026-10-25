import React from "react";
import { Video } from "@remotion/media";
import { staticFile, useVideoConfig } from "remotion";
import { FONT, T } from "./theme";

/** Real screen recordings (public/footage/*.mp4). `null` = not delivered yet → mock placeholder is shown. */
export type FootageMap = {
  readonly board: string | null;
  readonly photoshop: string | null;
  readonly td: string | null;
  readonly trim: { readonly board: number; readonly photoshop: number; readonly td: number };
};

export const Footage: React.FC<{ src: string | null; trimSeconds?: number; label: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ src, trimSeconds = 0, label, children, style }) => {
  const { fps } = useVideoConfig();
  return (
  <div style={{ position: "absolute", inset: 0, ...style }}>
    {src ? (
      <Video src={staticFile(`footage/${src}`)} trimBefore={Math.round(trimSeconds * fps)} muted objectFit="contain" style={{ width: "100%", height: "100%" }} />
    ) : (
      <>
        {children}
        <div style={{ position: "absolute", right: 16, top: 16, padding: "6px 12px", borderRadius: 8, border: "1px dashed rgba(0,0,0,.25)", font: `14px ${FONT.body}`, color: T.mut2, background: "rgba(255,255,255,.7)" }}>placeholder · {label}</div>
      </>
    )}
  </div>
);
};
