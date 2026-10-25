import React from "react";
import { Audio } from "@remotion/media";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Chat, Hook } from "./scenes/Problem";
import { Board, Desktop, Meet, Td } from "./scenes/Solution";
import { Cta } from "./scenes/Explain";
import type { FootageMap } from "./footage";
import { VO } from "./vo";

export type LaunchProps = {
  readonly music: string;
  readonly musicVolume: number;
  readonly voiceOver: boolean;
  readonly footage: FootageMap;
};

/** Scene durations (s) = voice-over length + breathing room, never below the visual minimum. */
const MIN = { hook: 6, chat: 5.5, meet: 4.5, td: 7, board: 9, desktop: 10, cta: 6 } as const;
export const SCENES = (Object.keys(MIN) as (keyof typeof MIN)[]).map((id) => ({ id, s: Math.max(MIN[id], Math.ceil((VO[id].dur + 1.0) * 2) / 2) }));
export const X = 0.5;
export const totalSeconds = SCENES.reduce((a, s) => a + s.s, 0) - X * (SCENES.length - 1);
export const sceneStart = (id: keyof typeof MIN) => {
  let acc = 0;
  for (const s of SCENES) {
    if (s.id === id) return acc;
    acc += s.s - X;
  }
  return acc;
};

/** Background music, ducked (×0.45) while a voice-over line is playing, full in the gaps. */
const Music: React.FC<{ src: string; volume: number; voiceOver: boolean }> = ({ src, volume, voiceOver }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = frame / fps;
  let duck = 1;
  if (voiceOver) {
    for (const sc of SCENES) {
      const a = sceneStart(sc.id) + 0.35;
      const b = a + VO[sc.id].dur;
      const d = interpolate(t, [a - 0.4, a, b, b + 0.6], [1, 0.45, 0.45, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      duck = Math.min(duck, d);
    }
  }
  const env = interpolate(frame, [0, 1 * fps, durationInFrames - 2.5 * fps, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <Audio src={staticFile(`audio/${src}`)} volume={volume * duck * env} />;
};

const Voice: React.FC<{ id: keyof typeof MIN; at: number }> = ({ id, at }) => {
  const { fps } = useVideoConfig();
  return <Audio src={staticFile(`audio/${VO[id].file}`)} from={Math.round(at * fps)} volume={1} />;
};

const Sfx: React.FC<{ at: number; src: string; volume?: number }> = ({ at, src, volume = 0.5 }) => {
  const { fps } = useVideoConfig();
  return <Audio src={src} from={Math.round(at * fps)} volume={volume} />;
};

export const Launch: React.FC<LaunchProps> = ({ music, musicVolume, voiceOver, footage }) => {
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  const t = linearTiming({ durationInFrames: f(X) });
  const dur = (id: keyof typeof MIN) => SCENES.find((s) => s.id === id)!.s;
  return (
    <>
      <Music src={music} volume={musicVolume} voiceOver={voiceOver} />
      {voiceOver && SCENES.map((s) => <Voice key={s.id} id={s.id} at={sceneStart(s.id) + 0.35} />)}
      <Sfx at={sceneStart("meet")} src="https://remotion.media/whoosh.wav" volume={0.5} />
            <Sfx at={sceneStart("cta") + 0.1} src="https://remotion.media/ding.wav" volume={0.4} />
      <TransitionSeries>
        <TransitionSeries.Sequence name="Hook" durationInFrames={f(dur("hook"))}><Hook /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Chat" durationInFrames={f(dur("chat"))}><Chat /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Meet" durationInFrames={f(dur("meet"))}><Meet /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="TD" durationInFrames={f(dur("td"))}><Td footage={footage.td} trim={footage.trim.td} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Board" durationInFrames={f(dur("board"))}><Board footage={footage.board} trim={footage.trim.board} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Desktop" durationInFrames={f(dur("desktop"))}><Desktop footage={footage.photoshop} trim={footage.trim.photoshop} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="CTA" durationInFrames={f(dur("cta"))}><Cta /></TransitionSeries.Sequence>
      </TransitionSeries>
    </>
  );
};
