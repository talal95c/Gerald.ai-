import React from "react";
import { Audio } from "@remotion/media";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Cta, Demo1, Demo2, Demo3, Demo4, Hook, Meet, Numbers, Problem, Vs } from "./pitch/short";
import { VOP2 as VOP } from "./voPitch2";

export type PitchProps = { readonly music: string; readonly musicVolume: number; readonly voiceOver: boolean };

/** Visual minimum per slide; the demo clips play (almost) whole. */
const MIN = { hook: 6, problem: 10, meet: 7, demo1: 9.5, demo2: 14, demo3: 7.5, demo4: 15, vs: 8, numbers: 8, cta: 6.5 } as const;
type Id = keyof typeof MIN;
export const PITCH_SCENES = (Object.keys(MIN) as Id[]).map((id) => ({ id, s: Math.max(MIN[id], Math.ceil((VOP[id].dur + 0.9) * 2) / 2) }));
const X = 0.5;
export const pitchSeconds = PITCH_SCENES.reduce((a, s) => a + s.s, 0) - X * (PITCH_SCENES.length - 1);
const start = (id: Id) => { let acc = 0; for (const s of PITCH_SCENES) { if (s.id === id) return acc; acc += s.s - X; } return acc; };
const dur = (id: Id) => PITCH_SCENES.find((s) => s.id === id)!.s;
const COMP: Record<Id, React.FC> = { hook: Hook, problem: Problem, meet: Meet, demo1: Demo1, demo2: Demo2, demo3: Demo3, demo4: Demo4, vs: Vs, numbers: Numbers, cta: Cta };

const Music: React.FC<{ src: string; volume: number; voiceOver: boolean }> = ({ src, volume, voiceOver }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  let duck = 1;
  if (voiceOver) for (const sc of PITCH_SCENES) { const a = start(sc.id) + 0.5; const b = a + VOP[sc.id].dur; duck = Math.min(duck, interpolate(t, [a - 0.4, a, b, b + 0.6], [1, 0.35, 0.35, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })); }
  const env = interpolate(frame, [0, 0.1 * fps, durationInFrames - 3 * fps, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <Audio src={staticFile(`audio/${src}`)} loop volume={volume * duck * env} />;
};

export const Pitch: React.FC<PitchProps> = ({ music, musicVolume, voiceOver }) => {
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  const t = linearTiming({ durationInFrames: f(X) });
  return (
    <>
      <Music src={music} volume={musicVolume} voiceOver={voiceOver} />
      {voiceOver && PITCH_SCENES.map((s) => <Audio key={s.id} src={staticFile(`audio/${VOP[s.id].file}`)} from={f(start(s.id) + 0.5)} />)}
      <TransitionSeries>
        {PITCH_SCENES.flatMap((s, i) => {
          const C = COMP[s.id];
          const seq = <TransitionSeries.Sequence key={s.id} name={s.id} durationInFrames={f(dur(s.id))}><C /></TransitionSeries.Sequence>;
          return i < PITCH_SCENES.length - 1 ? [seq, <TransitionSeries.Transition key={`${s.id}-t`} presentation={fade()} timing={t} />] : [seq];
        })}
      </TransitionSeries>
    </>
  );
};
