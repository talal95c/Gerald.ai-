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
          music: "driving-ambition.mp3",
          musicVolume: 0.55,
          footage: { board: null, photoshop: null, td: null },
        }}
      />
    </>
  );
};
