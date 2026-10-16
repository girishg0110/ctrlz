import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FPS, inter, mono } from "./theme";

export const ease = Easing.bezier(0.22, 1, 0.36, 1);

export const fadeIn = (frame: number, start: number, dur = 12) =>
  interpolate(frame, [start, start + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

export const rise = (frame: number, start: number, dist = 24, dur = 16) =>
  interpolate(frame, [start, start + dur], [dist, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

export const Bg: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ background: C.bg, fontFamily: inter, color: C.text }}>
    <AbsoluteFill
      style={{
        backgroundImage: `radial-gradient(circle at 50% 40%, #1a2240 0%, transparent 55%), linear-gradient(${C.line}55 1px, transparent 1px), linear-gradient(90deg, ${C.line}55 1px, transparent 1px)`,
        backgroundSize: "100% 100%, 64px 64px, 64px 64px",
        opacity: 0.6,
      }}
    />
    {children}
  </AbsoluteFill>
);

/** A slice of the real screen recording, played at `rate`, with an optional slow push-in. */
export const Footage: React.FC<{
  from: number; // seconds into the recording
  rate?: number;
  zoom?: [number, number];
  origin?: string;
  dim?: number;
  speedLabel?: string;
}> = ({ from, rate = 1, zoom = [1, 1], origin = "50% 50%", dim = 0, speedLabel }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], zoom, { easing: Easing.inOut(Easing.quad) });
  return (
    <AbsoluteFill style={{ background: C.bg }}>
      <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: origin }}>
        <OffthreadVideo src={staticFile("footage/run.mp4")} trimBefore={Math.round(from * FPS)} playbackRate={rate} muted />
      </AbsoluteFill>
      {dim > 0 && <AbsoluteFill style={{ background: C.bg, opacity: dim }} />}
      {speedLabel && (
        <div style={{ position: "absolute", top: 28, right: 32, fontFamily: mono, fontSize: 22, color: C.dim, background: "#0b0d12cc", padding: "6px 14px", borderRadius: 8, border: `1px solid ${C.line}` }}>
          {speedLabel}
        </div>
      )}
    </AbsoluteFill>
  );
};

export const Callout: React.FC<{ at: number; x: number; y: number; color?: string; children: React.ReactNode; size?: number }> = ({ at, x, y, color = C.text, children, size = 44 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 16, mass: 0.7 } });
  return (
    <div
      style={{
        position: "absolute", left: x, top: y, transform: `translateY(${(1 - s) * 20}px) scale(${0.96 + 0.04 * s})`, opacity: s,
        background: "#0b0d12ee", border: `1.5px solid ${color}`, color, borderRadius: 16, padding: "16px 26px",
        fontSize: size, fontWeight: 700, letterSpacing: -0.5, boxShadow: "0 20px 60px #000a", fontFamily: inter, whiteSpace: "nowrap",
      }}
    >
      {children}
    </div>
  );
};

export const Wordmark: React.FC<{ size?: number; typed?: number }> = ({ size = 160, typed = 6 }) => {
  const text = "Ctrl+Z";
  const shown = text.slice(0, Math.max(0, Math.min(6, Math.floor(typed))));
  return (
    <div style={{ fontFamily: inter, fontWeight: 800, fontSize: size, letterSpacing: -size * 0.04, lineHeight: 1 }}>
      {shown.split("").map((ch, i) => (
        <span key={i} style={{ color: ch === "+" ? C.blue : C.text }}>{ch}</span>
      ))}
    </div>
  );
};
