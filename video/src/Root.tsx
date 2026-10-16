import React from "react";
import { Composition } from "remotion";
import { CtrlZVideo, TOTAL_FRAMES } from "./Video";
import { FPS } from "./theme";

export const Root: React.FC = () => (
  <Composition id="CtrlZ" component={CtrlZVideo} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} />
);
