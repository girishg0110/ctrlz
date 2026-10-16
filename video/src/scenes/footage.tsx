// Scenes built on the real screen recording of a live run: 4-9.
import React from "react";
import { AbsoluteFill, Img, interpolate, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FPS, mono } from "../theme";
import { Bg, Callout, fadeIn, Footage, rise } from "../ui";

type Word = { w: string; s: number; e: number };

/** Seconds into the scene's audio when `needle` is first spoken (falls back to `fallback`). */
export const cue = (words: Word[], needle: string, fallback: number) => {
  const w = words.find((x) => x.w.toLowerCase().replace(/[^a-z0-9]/g, "").startsWith(needle));
  return w ? w.s : fallback;
};

export const Setup: React.FC<{ split: number }> = ({ split }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <Sequence durationInFrames={Math.round(split * fps)}>
        <Footage from={2} zoom={[1, 1.9]} origin="4% 36%" />
        <Callout at={1.2 * fps} x={560} y={640} color={C.red} size={56}>2–4 s per page load</Callout>
      </Sequence>
      <Sequence from={Math.round(split * fps)}>
        <Footage from={8.4} zoom={[1.25, 1.35]} origin="30% 0%" />
      </Sequence>
      <AbsoluteFill style={{ opacity: interpolate(frame, [0, 8], [1, 0], { extrapolateRight: "clamp" }), background: C.bg }} />
    </AbsoluteFill>
  );
};

const Pill: React.FC<{ at: number; x: number; y: number; color: string; children: React.ReactNode }> = ({ at, x, y, color, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 15 } });
  return (
    <div style={{
      position: "absolute", left: x, top: y, transform: `translate(-50%, ${(1 - s) * 16}px)`, opacity: s,
      background: "#0b0d12f0", border: `2px solid ${color}`, color, borderRadius: 999, padding: "10px 22px", fontSize: 28, fontWeight: 700, whiteSpace: "nowrap",
    }}>{children}</div>
  );
};

export const Fork: React.FC<{ words: Word[] }> = ({ words }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <Footage from={11.4} rate={3} zoom={[1.15, 1.2]} origin="72% 25%" speedLabel="real run · 3× speed" />
      <Callout at={0.6 * fps} x={70} y={190} color={C.amber} size={50}>3 copies on Daytona</Callout>
      <Pill at={cue(words, "careful", 4) * fps} x={1075} y={470} color={C.green}>careful database expert</Pill>
      <Pill at={cue(words, "rewrite", 6) * fps} x={1365} y={540} color={C.blue}>allowed to rewrite code</Pill>
      <Pill at={cue(words, "third", 8) * fps} x={1660} y={470} color={C.red}>told to act recklessly</Pill>
    </AbsoluteFill>
  );
};

const ICONS: Record<string, React.ReactNode> = {
  db: (<g fill="none" stroke="currentColor" strokeWidth={5}><ellipse cx={40} cy={18} rx={26} ry={10} /><path d="M14 18v44c0 6 12 10 26 10s26-4 26-10V18" /><path d="M14 40c0 6 12 10 26 10s26-4 26-10" /></g>),
  list: (<g fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round"><path d="M28 20h40M28 40h40M28 60h40" /><circle cx={14} cy={20} r={3} fill="currentColor" /><circle cx={14} cy={40} r={3} fill="currentColor" /><circle cx={14} cy={60} r={3} fill="currentColor" /></g>),
  clock: (<g fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round"><circle cx={40} cy={44} r={28} /><path d="M40 44V28M40 44l12 8M32 8h16" /></g>),
  gavel: (<g fill="none" stroke="currentColor" strokeWidth={5} strokeLinecap="round"><path d="M30 14l26 26M22 22l26 26M26 18l18-8 18 18-8 18" /><path d="M38 36L12 62" /><path d="M8 72h40" /></g>),
};

export const Checks: React.FC<{ words: Word[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cards = [
    { icon: "db", title: "Integrity", q: "Did we lose data?", at: cue(words, "did", 2.4) },
    { icon: "list", title: "Correctness", q: "Right orders on the page?", at: cue(words, "does", 4.2) },
    { icon: "clock", title: "Speed", q: "At least twice as fast?", at: cue(words, "is", 6.4) },
    { icon: "gavel", title: "Judge", q: "Safe to ship?", at: cue(words, "and", 8.4) },
  ];
  return (
    <AbsoluteFill>
      <Footage from={32} rate={2} dim={0.78} zoom={[1.3, 1.4]} origin="60% 80%" />
      <div style={{ position: "absolute", top: 150, width: "100%", textAlign: "center", fontSize: 52, fontWeight: 700, opacity: fadeIn(frame, 0) }}>
        Every copy, the same four checks
      </div>
      <div style={{ position: "absolute", top: 330, left: 150, right: 150, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 36 }}>
        {cards.map((c, i) => {
          const s = spring({ frame: frame - c.at * fps, fps, config: { damping: 14 } });
          return (
            <div key={i} style={{
              background: "#12151cf2", border: `2px solid ${C.line}`, borderRadius: 24, padding: "40px 34px", height: 380,
              transform: `translateY(${(1 - s) * -60}px)`, opacity: s, boxShadow: "0 30px 80px #000c",
            }}>
              <svg width={80} height={80} viewBox="0 0 80 80" style={{ color: C.blue }}>{ICONS[c.icon]}</svg>
              <div style={{ fontSize: 46, fontWeight: 800, marginTop: 30 }}>{c.title}</div>
              <div style={{ fontSize: 32, color: C.dim, marginTop: 14, lineHeight: 1.3 }}>{c.q}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Catch: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rate = 1.6;
  const at = (recSec: number) => ((recSec - 60.5) / rate) * fps;
  const count = Math.round(interpolate(frame, [at(64.5), at(67)], [200000, 45850], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  return (
    <AbsoluteFill>
      <Footage from={60.5} rate={rate} zoom={[1, 1.06]} origin="20% 40%" speedLabel="real run · 1.6× speed" />
      <Sequence from={Math.round(at(64.2))} durationInFrames={Math.round(at(71.4) - at(64.2))}>
        <Callout at={0} x={760} y={140} color={C.red} size={46}>
          {count.toLocaleString("en-US")} orders left · −77% · $193M gone
        </Callout>
      </Sequence>
      <Sequence from={Math.round(at(73.2))}>
        <Callout at={0} x={760} y={140} color={C.blue} size={46}>Production: untouched · 200,000 orders</Callout>
      </Sequence>
    </AbsoluteFill>
  );
};

export const Fix: React.FC = () => {
  const { fps } = useVideoConfig();
  const rate = 1.35;
  const at = (recSec: number) => ((recSec - 129.3) / rate) * fps;
  return (
    <AbsoluteFill>
      <Footage from={129.3} rate={rate} zoom={[1, 1.08]} origin="20% 40%" speedLabel="real run · 1.35× speed" />
      <Callout at={at(136.4)} x={830} y={140} color={C.green} size={56}>2,075 ms → 1 ms</Callout>
      <Callout at={at(138.4)} x={830} y={260} color={C.green} size={44}>0 orders lost</Callout>
    </AbsoluteFill>
  );
};

const Panel: React.FC<{ at: number; title: string; sub: string; color: string; children: React.ReactNode }> = ({ at, title, sub, color, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at * fps, fps, config: { damping: 16 } });
  return (
    <div style={{ opacity: s, transform: `translateY(${(1 - s) * 40}px)`, display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
        <div style={{ fontSize: 46, fontWeight: 800, color }}>{title}</div>
        <div style={{ fontSize: 26, color: C.dim }}>{sub}</div>
      </div>
      <div style={{ height: 640, borderRadius: 18, overflow: "hidden", border: `2px solid ${C.line}`, background: C.panel, position: "relative", boxShadow: "0 30px 80px #000c" }}>
        {children}
      </div>
    </div>
  );
};

export const Built: React.FC<{ words: Word[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tA = cue(words, "arize", 2.2);
  const tF = cue(words, "fireworks", 5.6);
  const swap = fadeIn(frame, (tA + 2.2) * fps, 14);
  const sandboxes = [
    ["production", C.blue], ["copy · careful", C.green], ["copy · rewrite", C.amber], ["copy · reckless", C.red],
  ];
  return (
    <Bg>
      <div style={{ position: "absolute", top: 120, left: 80, right: 80, display: "grid", gridTemplateColumns: "1fr 1.35fr 1fr", gap: 40 }}>
        <Panel at={0.1} title="Daytona" sub="every copy" color={C.text}>
          <div style={{ padding: 30, display: "flex", flexDirection: "column", gap: 18 }}>
            {sandboxes.map(([name, color], i) => (
              <div key={i} style={{ opacity: fadeIn(frame, 6 + i * 5), transform: `translateX(${rise(frame, 6 + i * 5, 30)}px)`, background: C.panel2, borderRadius: 14, padding: "22px 24px", border: `1px solid ${C.line}`, borderLeft: `8px solid ${color}` }}>
                <div style={{ fontSize: 30, fontWeight: 700 }}>{name}</div>
                <div style={{ fontFamily: mono, fontSize: 20, color: C.dim, marginTop: 6 }}>sandbox · <span style={{ color: C.green }}>● running</span></div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel at={tA} title="Arize" sub="every command, model call, verdict" color={C.text}>
          <Img src={staticFile("arize/trace-tree.jpg")} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", objectPosition: "left top", opacity: 1 - swap }} />
          <Img src={staticFile("arize/eval-discard.jpg")} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", objectPosition: "right top", opacity: swap }} />
        </Panel>
        <Panel at={tF} title="Fireworks" sub="Kimi K3 agents" color={C.text}>
          <div style={{ position: "absolute", width: 1920, height: 1080, left: -813 * 1.0, top: -548 * 1.0 }}>
            <OffthreadVideo src={staticFile("footage/run.mp4")} trimBefore={Math.round(40 * FPS)} muted />
          </div>
        </Panel>
      </div>
    </Bg>
  );
};
