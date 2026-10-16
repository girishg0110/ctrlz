import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import narration from "./narration.json";
import { AnyProject, Built, Catch, Checks, Fix, Fork, Setup } from "./scenes/footage";
import { Close, ColdOpen, Idea } from "./scenes/motion";
import { C, FPS, inter } from "./theme";

type Word = { w: string; s: number; e: number };
type Scene = { n: number; title: string; audio: string; duration: number; words: Word[] };

export const REPO = "github.com/girishg0110/ctrlz";
export const TEAM = "random deforestation";

const LEAD = 0.3; // silence before each scene's narration
const TAIL = 0.5; // silence after it
const END_HOLD = 2.2; // extra hold on the final card
const MUSIC_VOLUME = 0.18; // Apple Loops bed, kept well under the voice

const scenes = (narration.scenes as Scene[]).map((s) => ({ ...s }));

export const timeline = (() => {
  let t = 0;
  return scenes.map((s, i) => {
    const len = LEAD + s.duration + TAIL + (i === scenes.length - 1 ? END_HOLD : 0);
    const item = { ...s, start: t, len, from: Math.round(t * FPS), frames: Math.round(len * FPS) };
    t += len;
    return item;
  });
})();

export const TOTAL_FRAMES = timeline.reduce((a, s) => a + s.frames, 0);

const body = (title: string, words: Word[]) => {
  switch (title) {
    case "Cold open": return <ColdOpen />;
    case "The idea": return <Idea />;
    case "The setup": return <Setup split={Math.min(6, (words.find((w) => w.w.toLowerCase().startsWith("we"))?.s ?? 5) + LEAD)} />;
    case "The fork": return <Fork words={shift(words)} />;
    case "The checks": return <Checks words={shift(words)} />;
    case "The catch": return <Catch />;
    case "The fix": return <Fix />;
    case "Any project": return <AnyProject words={shift(words)} />;
    case "How it's built": return <Built words={shift(words)} />;
    default: return <Close repo={REPO} team={TEAM} />;
  }
};

// Word times are relative to the clip; scenes start LEAD seconds before the clip.
const shift = (words: Word[]) => words.map((w) => ({ ...w, s: w.s + LEAD, e: w.e + LEAD }));

/** Bottom captions: the current phrase, with the spoken word highlighted. */
const Captions: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const scene = timeline.find((s) => t >= s.start && t < s.start + s.len);
  if (!scene) return null;
  const local = t - scene.start - LEAD;
  const chunks: Word[][] = [];
  let cur: Word[] = [];
  for (const w of scene.words) {
    cur.push(w);
    if (cur.length >= 8 || /[.?!:,]$/.test(w.w) && cur.length >= 4 || /[.?!]$/.test(w.w)) {
      chunks.push(cur);
      cur = [];
    }
  }
  if (cur.length) chunks.push(cur);
  const chunk = chunks.find((c) => local >= c[0].s - 0.05 && local <= c[c.length - 1].e + 0.35);
  if (!chunk) return null;
  return (
    <div style={{ position: "absolute", bottom: 54, width: "100%", display: "flex", justifyContent: "center" }}>
      <div style={{ background: "#0b0d12e6", borderRadius: 14, padding: "12px 26px", fontFamily: inter, fontSize: 38, fontWeight: 600, maxWidth: 1500, textAlign: "center", border: `1px solid ${C.line}` }}>
        {chunk.map((w, i) => (
          <span key={i} style={{ color: local >= w.s ? C.text : "#6b7180" }}>{w.w} </span>
        ))}
      </div>
    </div>
  );
};

export const CtrlZVideo: React.FC = () => (
  <AbsoluteFill style={{ background: C.bg, fontFamily: inter, color: C.text }}>
    {timeline.map((s) => (
      <Sequence key={s.n} from={s.from} durationInFrames={s.frames} name={`scene ${s.n}`}>
        {body(s.title, s.words)}
        <Sequence from={Math.round(LEAD * FPS)}>
          <Audio src={staticFile(s.audio)} />
        </Sequence>
      </Sequence>
    ))}
    <Audio
      src={staticFile("audio/music.m4a")}
      volume={(f) => interpolate(f, [0, 30, TOTAL_FRAMES - 75, TOTAL_FRAMES], [0, MUSIC_VOLUME, MUSIC_VOLUME, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
    />
    <Captions />
  </AbsoluteFill>
);
