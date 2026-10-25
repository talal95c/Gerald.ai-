import React from "react";
import { Audio } from "@remotion/media";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Chat, Hook, Morning, Stat, Thesis } from "./scenes/Problem";
import { Board, Desktop, Meet, Td } from "./scenes/Solution";
import { Cta, How, Proof } from "./scenes/Explain";
import type { FootageMap } from "./footage";

export type LaunchProps = {
  readonly music: string;
  readonly musicVolume: number;
  readonly footage: FootageMap;
};

/** Scene durations in seconds. Transitions overlap by `X` seconds each. */
export const SCENES = [
  { id: "hook", s: 6 },
  { id: "chat", s: 8 },
  { id: "morning", s: 6 },
  { id: "stat", s: 6.5 },
  { id: "thesis", s: 5.5 },
  { id: "meet", s: 6 },
  { id: "board", s: 12.5 },
  { id: "desktop", s: 11.5 },
  { id: "td", s: 9 },
  { id: "how", s: 9 },
  { id: "proof", s: 7 },
  { id: "cta", s: 7 },
] as const;
export const X = 0.5;
export const totalSeconds = SCENES.reduce((a, s) => a + s.s, 0) - X * (SCENES.length - 1);

const Music: React.FC<{ src: string; volume: number }> = ({ src, volume }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  return (
    <Audio
      src={staticFile(`audio/${src}`)}
      volume={interpolate(frame, [0, 1.5 * fps, durationInFrames - 3 * fps, durationInFrames], [0, volume, volume, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
    />
  );
};

const Sfx: React.FC<{ at: number; src: string; volume?: number }> = ({ at, src, volume = 0.6 }) => {
  const { fps } = useVideoConfig();
  return <Audio src={src} from={Math.round(at * fps)} volume={volume} />;
};

export const Launch: React.FC<LaunchProps> = ({ music, musicVolume, footage }) => {
  const { fps } = useVideoConfig();
  const f = (s: number) => Math.round(s * fps);
  const t = linearTiming({ durationInFrames: f(X) });
  const start = (id: (typeof SCENES)[number]["id"]) => {
    let acc = 0;
    for (const s of SCENES) {
      if (s.id === id) return acc;
      acc += s.s - X;
    }
    return acc;
  };
  return (
    <>
      <Music src={music} volume={musicVolume} />
      <Sfx at={start("chat") + 2.2} src="https://remotion.media/whoosh.wav" volume={0.35} />
      <Sfx at={start("meet")} src="https://remotion.media/whoosh.wav" volume={0.5} />
      <Sfx at={start("board") + 4.7} src="https://remotion.media/mouse-click.wav" volume={0.5} />
      <Sfx at={start("board") + 9.4} src="https://remotion.media/ding.wav" volume={0.5} />
      <Sfx at={start("desktop") + 3.9} src="https://remotion.media/mouse-click.wav" volume={0.5} />
      <Sfx at={start("desktop") + 7.6} src="https://remotion.media/mouse-click.wav" volume={0.5} />
      <Sfx at={start("cta") + 0.1} src="https://remotion.media/ding.wav" volume={0.4} />
      <TransitionSeries>
        <TransitionSeries.Sequence name="Hook" durationInFrames={f(6)}><Hook /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Chat" durationInFrames={f(8)}><Chat /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Morning" durationInFrames={f(6)}><Morning /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Stat" durationInFrames={f(6.5)}><Stat /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Thesis" durationInFrames={f(5.5)}><Thesis /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Meet" durationInFrames={f(6)}><Meet /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Board" durationInFrames={f(12.5)}><Board footage={footage.board} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Desktop" durationInFrames={f(11.5)}><Desktop footage={footage.photoshop} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="TD" durationInFrames={f(9)}><Td footage={footage.td} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="How" durationInFrames={f(9)}><How /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="Proof" durationInFrames={f(7)}><Proof /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t} />
        <TransitionSeries.Sequence name="CTA" durationInFrames={f(7)}><Cta /></TransitionSeries.Sequence>
      </TransitionSeries>
    </>
  );
};
