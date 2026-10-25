import {Orb} from "./orb";
import type {CSSProperties} from "react";

export type DemoStep = 1 | 2 | 3 | 4 | 5 | "done" | null;

export function GuidePoint({className = "", style}: {className?: string; style?: CSSProperties}) {
  return <svg className={`demo-guide-point ${className}`} style={style} viewBox="-32 -32 64 64" aria-hidden="true">
    <g className="guide-point">
      <circle className="gp-halo" r="20"/>
      <circle className="gp-ripple" r="12"/>
      <circle className="gp-ripple gp-late" r="12"/>
      <circle className="gp-core" r="4"/>
    </g>
  </svg>;
}

const steps: Record<Exclude<DemoStep, null | "done">, string> = {
  1: "Ouvre Notes dans le dock.",
  2: "Ouvre Documents, puis le TD 4.",
  3: "Maintiens Ctrl + Shift et demande : « Explique-moi l'exercice 1 ».",
  4: "Dis : « On va au tableau ».",
  5: "Écris au stylo Δ = 25 + 24 = 49, puis demande : « C'est juste ? »",
};

export function GuidedDemo({
  step,
  inkReady,
  onAsk,
  onSkip,
  onFinish,
}: {
  step: DemoStep;
  inkReady: boolean;
  onAsk: (text: string) => void;
  onSkip: () => void;
  onFinish: () => void;
}) {
  if (step === null) return null;
  const done = step === "done";
  const action = step === 3
    ? {label: "Envoyer la question", text: "Explique-moi l'exercice 1"}
    : step === 4
      ? {label: "Envoyer", text: "On va au tableau"}
      : step === 5
        ? {label: "Demander « C'est juste ? »", text: "C'est juste ?", disabled: !inkReady}
        : null;
  return <aside className="guided-demo" aria-label="Démo guidée">
    <div className="guided-demo-content" key={String(step)}>
      <div className="guided-demo-head">
        <Orb status="listening" size={28}/>
        {!done && <span className="guided-demo-counter">{step}/5</span>}
      </div>
      <p>{done ? "Bravo. Essaie aussi Photoshop : « Je veux faire un carré rouge »." : steps[step]}</p>
      {action && <button type="button" className="guided-demo-action" disabled={action.disabled} onClick={() => onAsk(action.text)}>{action.label}</button>}
      {done
        ? <button type="button" className="guided-demo-action" onClick={onFinish}>Terminer</button>
        : <button type="button" className="guided-demo-skip" onClick={onSkip}>Passer</button>}
    </div>
  </aside>;
}
