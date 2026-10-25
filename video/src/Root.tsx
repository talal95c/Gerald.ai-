import React from "react";
import { Composition } from "remotion";
import { Launch, totalSeconds } from "./Video";
import "./fonts";

const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Launch"
        component={Launch}
        durationInFrames={Math.round(totalSeconds * FPS)}
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={{
          music: "training.mp3",
          musicVolume: 0.34,
          voiceOver: true,
          footage: { board: "clip2.mp4", photoshop: "clip3.mp4", td: "clip1.mp4", trim: { board: 9, photoshop: 8, td: 7 } },
        }}
      />
    </>
  );
};
