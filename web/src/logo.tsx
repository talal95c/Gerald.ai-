import React from "react";

export function GeraldMark({size}: {size: number}) {
  return <svg
    className="gerald-mark"
    width={size * 40 / 24}
    height={size}
    viewBox="0 0 40 24"
    fill="#fff"
    aria-hidden="true"
  >
    <rect x="2" y="2" width="10" height="20" rx="5"/>
    <circle className="gerald-mark-circle" cx="27" cy="12" r="10"/>
  </svg>;
}
