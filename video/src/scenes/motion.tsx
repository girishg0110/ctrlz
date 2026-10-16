// Pure animation scenes: 1 (cold open), 2 (problem), 3 (idea), 10 (close).
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, mono } from "../theme";
import { Bg, ease, fadeIn, rise, Wordmark } from "../ui";

const ROWS = [
  ["#199997", "Kai Haddad", "2026-10-14", "$1,009.18"],
  ["#199999", "Noah Rossi", "2026-10-14", "$2,058.31"],
  ["#199996", "Kai Silva", "2026-10-14", "$1,361.82"],
  ["#200000", "Omar Garcia", "2026-10-14", "$1,219.50"],
  ["#199998", "Kai Okafor", "2026-10-14", "$1,270.78"],
  ["#199995", "Liam Nguyen", "2026-10-14", "$749.18"],
  ["#199994", "Ava Kim", "2026-10-14", "$286.35"],
  ["#199993", "Omar Silva", "2026-10-14", "$1,243.65"],
  ["#199991", "Liam Patel", "2026-10-13", "$612.40"],
  ["#199990", "Rosa Chen", "2026-10-13", "$98.12"],
  ["#199988", "Zoe Smith", "2026-10-13", "$1,875.00"],
  ["#199987", "Theo Kim", "2026-10-13", "$433.29"],
];

export const ColdOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const start = 1.6 * fps;
  const gap = 0.32 * fps;
  return (
    <Bg>
      <div style={{ position: "absolute", top: 70, left: 110, fontFamily: mono, fontSize: 30, color: C.dim, opacity: fadeIn(frame, 4) }}>
        July 2025 · production database
      </div>
      <div style={{ position: "absolute", top: 150, left: 110, right: 110, opacity: fadeIn(frame, 0, 18) }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr 1.2fr 1fr", fontFamily: mono, fontSize: 24, color: C.dim, padding: "0 28px 14px", borderBottom: `1px solid ${C.line}` }}>
          <span>ORDER</span><span>CUSTOMER</span><span>PLACED</span><span style={{ textAlign: "right" }}>TOTAL</span>
        </div>
        {ROWS.map((r, i) => {
          const fromBottom = ROWS.length - 1 - i;
          const t = start + fromBottom * gap;
          const flicker = frame > t && frame < t + 6 ? (Math.floor(frame) % 2 ? 0.15 : 1) : 1;
          const gone = interpolate(frame, [t + 6, t + 10], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const red = frame > t;
          return (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "1fr 1.6fr 1.2fr 1fr", fontFamily: mono, fontSize: 30, padding: "15px 28px",
              borderBottom: `1px solid ${C.line}`, opacity: gone * flicker, color: red ? C.red : C.text,
              background: red ? "#ef5a5a14" : "transparent",
            }}>
              <span>{r[0]}</span><span>{r[1]}</span><span>{r[2]}</span><span style={{ textAlign: "right" }}>{r[3]}</span>
            </div>
          );
        })}
      </div>
      <div style={{ position: "absolute", bottom: 150, width: "100%", textAlign: "center", fontFamily: mono, fontSize: 34, color: C.red, opacity: fadeIn(frame, start + ROWS.length * gap + 8) }}>
        0 rows
      </div>
    </Bg>
  );
};

const Agent: React.FC<{ x: number; y: number; color: string; scale?: number; label?: string }> = ({ x, y, color, scale = 1, label }) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <rect x={-60} y={-60} width={120} height={120} rx={30} fill={C.panel2} stroke={color} strokeWidth={4} />
    <circle cx={-22} cy={-6} r={10} fill={color} />
    <circle cx={22} cy={-6} r={10} fill={color} />
    <rect x={-26} y={24} width={52} height={8} rx={4} fill={color} />
    <line x1={0} y1={-60} x2={0} y2={-84} stroke={color} strokeWidth={4} />
    <circle cx={0} cy={-90} r={8} fill={color} />
    {label && <text x={0} y={110} textAnchor="middle" fill={C.dim} fontSize={30} fontFamily="Inter">{label}</text>}
  </g>
);

export const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const flash = frame > 1.4 * fps;
  const pulse = flash ? 0.5 + 0.5 * Math.sin(frame / 3) : 0;
  const len = 760;
  const drawn = interpolate(frame, [1.8 * fps, 4.2 * fps], [0, len * 0.86], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const stop = fadeIn(frame, 4.2 * fps, 8);
  return (
    <Bg>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: "absolute" }}>
        {[0, 1, 2].map((i) => {
          const isBad = i === 1;
          const color = isBad && flash ? (pulse > 0.5 ? C.red : "#ff8a8a") : C.amber;
          return (
            <g key={i} opacity={fadeIn(frame, i * 5)}>
              <Agent x={420} y={260 + i * 280} color={color} label={isBad && flash ? "mistake" : undefined} />
            </g>
          );
        })}
        <line x1={500} y1={540} x2={500 + len} y2={540} stroke={C.red} strokeWidth={6} strokeDasharray={`${drawn} ${len}`} strokeLinecap="round" />
        <g opacity={stop} transform={`translate(${500 + len * 0.86 + 40} 540)`}>
          <line x1={-22} y1={-22} x2={22} y2={22} stroke={C.red} strokeWidth={8} strokeLinecap="round" />
          <line x1={22} y1={-22} x2={-22} y2={22} stroke={C.red} strokeWidth={8} strokeLinecap="round" />
        </g>
        <g transform="translate(1480 540)" opacity={fadeIn(frame, 10)}>
          {[-70, 0, 70].map((dx, i) => (
            <g key={i} transform={`translate(${dx} ${i === 1 ? -20 : 10})`}>
              <circle cx={0} cy={-40} r={32} fill={C.blue} opacity={0.9} />
              <path d="M -55 60 Q 0 -10 55 60 Z" fill={C.blue} opacity={0.9} />
            </g>
          ))}
          <text x={0} y={140} textAnchor="middle" fill={C.text} fontSize={40} fontWeight={600} fontFamily="Inter">Customers</text>
        </g>
      </svg>
    </Bg>
  );
};

const Box: React.FC<{ x: number; y: number; w: number; h: number; color: string; label: string; sub?: string; opacity?: number }> = ({ x, y, w, h, color, label, sub, opacity = 1 }) => (
  <div style={{
    position: "absolute", left: x - w / 2, top: y - h / 2, width: w, height: h, opacity, borderRadius: 18,
    background: C.panel2, border: `3px solid ${color}`, display: "flex", flexDirection: "column", justifyContent: "center", paddingLeft: 34,
    boxShadow: `0 0 60px ${color}22`,
  }}>
    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 10, background: color, borderRadius: "14px 0 0 14px" }} />
    <div style={{ fontSize: 36, fontWeight: 700 }}>{label}</div>
    {sub && <div style={{ fontFamily: mono, fontSize: 22, color: C.dim, marginTop: 6 }}>{sub}</div>}
  </div>
);

export const Idea: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const typed = interpolate(frame, [0, 0.8 * fps], [0, 6], { extrapolateRight: "clamp" });
  const split = spring({ frame: frame - 3.2 * fps, fps, config: { damping: 18 } });
  const checks = (i: number) => fadeIn(frame, 8.5 * fps + i * 6, 8);
  const promote = spring({ frame: frame - 12.6 * fps, fps, config: { damping: 18 } });
  const prodY = 470;
  const copyY = 790;
  const xs = [560, 960, 1360];
  const tagline = fadeIn(frame, durationInFrames - 4.2 * fps);
  return (
    <Bg>
      <div style={{ position: "absolute", top: 70, width: "100%", display: "flex", justifyContent: "center" }}>
        <Wordmark size={130} typed={typed} />
      </div>
      <div style={{ position: "absolute", top: 230, width: "100%", textAlign: "center", fontSize: 40, color: C.dim, opacity: tagline, transform: `translateY(${rise(frame, durationInFrames - 4.2 * fps)}px)` }}>
        Agents work on copies. Production moves only to a copy that passes.
      </div>
      <svg width={1920} height={1080} style={{ position: "absolute" }}>
        {xs.map((x, i) => (
          <path key={i} d={`M 960 ${prodY + 60} C 960 ${prodY + 160}, ${x} ${copyY - 160}, ${x} ${copyY - 70}`} stroke={C.amber} strokeWidth={4} fill="none" strokeDasharray="12 10" opacity={split * (1 - promote)} />
        ))}
      </svg>
      <Box x={960} y={prodY} w={440} h={120} color={C.blue} label="Production" sub="customers use this" opacity={1 - promote} />
      {xs.map((x, i) => {
        const winner = i === 0;
        const y = interpolate(split, [0, 1], [prodY, copyY]);
        const px = interpolate(split, [0, 1], [960, x]);
        const fy = winner ? interpolate(promote, [0, 1], [y, prodY]) : y;
        const fx = winner ? interpolate(promote, [0, 1], [px, 960]) : px;
        const passed = frame > 10.6 * fps;
        const color = passed ? (winner ? C.green : C.red) : C.amber;
        return (
          <React.Fragment key={i}>
            <Box x={fx} y={fy} w={340} h={120} color={color} label={winner && promote > 0.5 ? "Production" : `Copy ${i + 1}`}
              sub={winner && promote > 0.5 ? "passed every check" : "agent at work"} opacity={split * (winner ? 1 : 1 - promote * 0.75)} />
            <div style={{ position: "absolute", left: x - 120, top: copyY + 82, width: 240, display: "flex", justifyContent: "center", gap: 14, opacity: 1 - promote }}>
              {[0, 1, 2, 3].map((k) => {
                const fail = !winner && k === (i === 1 ? 2 : 0);
                return (
                  <div key={k} style={{
                    width: 40, height: 40, borderRadius: 20, opacity: checks(k),
                    background: passed ? (fail ? C.red : C.green) : C.line, display: "grid", placeItems: "center", fontSize: 24, fontWeight: 800, color: "#000",
                  }}>{passed ? (fail ? "✕" : "✓") : ""}</div>
                );
              })}
            </div>
          </React.Fragment>
        );
      })}
    </Bg>
  );
};

export const Close: React.FC<{ repo: string; team: string }> = ({ repo, team }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 14 } });
  return (
    <Bg>
      <AbsoluteFill style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 34 }}>
        <div style={{ transform: `scale(${0.85 + 0.15 * s})`, opacity: s }}><Wordmark size={200} /></div>
        <div style={{ fontSize: 40, color: C.dim, opacity: fadeIn(frame, 0.8 * fps) }}>Agents work on copies. Customers never see the mistakes.</div>
        <div style={{ marginTop: 40, fontFamily: mono, fontSize: 38, color: C.blue, opacity: fadeIn(frame, 1.4 * fps) }}>{repo}</div>
        <div style={{ fontSize: 32, color: C.text, opacity: fadeIn(frame, 1.9 * fps) }}>
          team <b>{team}</b> · Daytona HackSprint NYC 2026
        </div>
      </AbsoluteFill>
    </Bg>
  );
};
