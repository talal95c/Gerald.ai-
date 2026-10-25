import React from "react";

export function Reveal({text}: {text: string}) {
  const words = text.split(/(\s+)/);
  return <>{words.map((word,index)=>/^\s+$/.test(word)?word:<span className="reveal-word" style={{animationDelay:`${index*40}ms`}} key={`${word}-${index}`}>{word}</span>)}</>;
}
