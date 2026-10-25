import React from "react";
import { Audio } from "@remotion/media";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Chat, Hook, Stat } from "./scenes/Problem";
import { Board, Desktop, Meet, Td } from "./scenes/Solution";
import { Cta, Proof } from "./scenes/Explain";
import type { FootageMap } from "./footage";
import { VO } from "./vo";

export type LaunchProps = {
  readonly music: string;
  readonly musicVolume: number;
  readonly voiceOver: boolean;
  readonly footage: FootageMap;
};

/** Scene durations (s) = voice-over length + breathing room, never below the visual minimum. */
const MIN = { hook: 7, chat: 6.5, stat: 5.5, meet: 5, board: 12, desktop: 10, td: 7, proof: 7.5, cta: 6.5 } as const;
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

const Music: React.FC<{ src: string; volume: number }> = ({ src, volume }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const meet = sceneStart("meet") * fps;
  return (
    <Audio
      src={staticFile(`audio/${src}`)}
      volume={interpolate(frame, [0, 1 * fps, meet - 10, meet, durationInFrames - 2.5 * fps, durationInFrames], [0, volume * 0.75, volume * 0.75, volume, volume, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
    />
  );
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
      <Music src={music} volume={musicVolume} />
      {voiceOver && SCENES.map((s) => <Voice key={s.id} id={s.id} at={sceneStart(s.id) + 0.35} />)}
      <Sfx at={sceneStart("meet")} src="https://remotion.media/whoosh.wav" volume={0.5} />
      <Sfx at={sceneStart("board") + 4.7} src="https://remotion.media/mouse-click.wav" />
      <Sfx at={sceneStart("board") + 9.4} src="https://remotion.media/ding.wav" />
      <Sfx at={sceneStart("desktop") + 3.9} src="https://remotion.media/mouse-click.wav" />
      <Sfx at={sceneStart("desktop") + 7.6} src="https://remotion.media/mouse-click.wav" />
      <Sfx at={sceneStart("cta") + 0.1} src="https://remotion.media/ding.wav" volume={0.4} />
      <TransitionSeries>
        <TransitionSeries.Sequence name="Hook" durationInFrames={f(dur("hook"))}><Hook /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Chat" durationInFrames={f(dur("chat"))}><Chat /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Stat" durationInFrames={f(dur("stat"))}><Stat /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Meet" durationInFrames={f(dur("meet"))}><Meet /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Board" durationInFrames={f(dur("board"))}><Board footage={footage.board} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Desktop" durationInFrames={f(dur("desktop"))}><Desktop footage={footage.photoshop} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="TD" durationInFrames={f(dur("td"))}><Td footage={footage.td} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Proof" durationInFrames={f(dur("proof"))}><Proof /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="CTA" durationInFrames={f(dur("cta"))}><Cta /></TransitionSeries.Sequence>
      </TransitionSeries>
    </>
  );
};
