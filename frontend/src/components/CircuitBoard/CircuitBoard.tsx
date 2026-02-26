/**
 * CircuitBoard
 * Renders a fixed-position PCB-style wireframe background:
 * multi-layer traces (green signal + cyan inner-layer), 45° routing,
 * solder pads, vias, and component footprints (SOIC, QFP, crystal,
 * connector, inductor, resistors, caps).
 * Purely decorative — pointer events disabled.
 */

import React from 'react';
import './CircuitBoard.css';

/** Pad positions shared between solder pads and component pins. */
const PADS: readonly [number, number][] = [
  [40,60],[40,80],[40,140],[40,300],
  [60,40],[60,100],[60,200],[60,240],[60,280],
  [80,40],[80,60],[80,80],[80,200],[80,240],
  [100,40],[100,120],[100,140],[100,160],[100,200],
  [120,200],
  [140,20],[140,60],
  [160,40],[160,80],[160,120],[160,160],[160,240],[160,280],
  [200,40],[200,140],[200,220],[200,300],
  [220,60],[220,80],[220,120],[220,200],
  [240,240],[240,280],
  [260,60],[260,200],[260,240],
  [280,80],[280,120],[280,140],[280,200],[280,280],
  [300,60],[300,120],[300,140],
  [20,60],[20,180],
];

/** Via positions (rendered as ring + centre dot). */
const VIAS: readonly [number, number][] = [
  [80,120],[160,200],[220,140],[40,200],[120,280],
  [280,60],[20,180],[300,200],[140,0],[260,120],[80,280],
];

/** A single 320×320 PCB tile. */
function PcbTile(): React.ReactElement {
  const tg = 'rgba(57,255,20,0.16)';   // green signal trace
  const tc = 'rgba(0,220,240,0.11)';   // cyan inner-layer trace
  const tp = 'rgba(57,255,20,0.24)';   // power / ground bus
  const p  = 'rgba(57,255,20,0.30)';   // solder pad
  const pr = 'rgba(57,255,20,0.22)';   // component outline / ring
  const sw = 1;
  const pw = 2;

  return (
    <g>
      {/* ── Power / Ground bus ── */}
      <line x1="0"   y1="200" x2="320" y2="200" stroke={tp} strokeWidth={pw} />
      <line x1="80"  y1="0"   x2="80"  y2="200" stroke={tp} strokeWidth={pw} />

      {/* ── Horizontal traces — green signal layer ── */}
      <line x1="0"   y1="40"  x2="60"  y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="40"  x2="100" y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="120" y1="40"  x2="200" y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="60"  x2="80"  y2="60"  stroke={tg} strokeWidth={sw} />
      <line x1="180" y1="60"  x2="260" y2="60"  stroke={tg} strokeWidth={sw} />
      <line x1="280" y1="60"  x2="320" y2="60"  stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="80"  x2="40"  y2="80"  stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="80"  x2="280" y2="80"  stroke={tg} strokeWidth={sw} />
      <line x1="100" y1="120" x2="160" y2="120" stroke={tg} strokeWidth={sw} />
      <line x1="220" y1="120" x2="280" y2="120" stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="140" x2="40"  y2="140" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="140" x2="100" y2="140" stroke={tg} strokeWidth={sw} />
      <line x1="200" y1="140" x2="320" y2="140" stroke={tg} strokeWidth={sw} />
      <line x1="100" y1="160" x2="160" y2="160" stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="240" x2="80"  y2="240" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="240" x2="320" y2="240" stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="280" x2="60"  y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="280" x2="240" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="280" y1="280" x2="320" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="0"   y1="300" x2="40"  y2="300" stroke={tg} strokeWidth={sw} />
      <line x1="200" y1="300" x2="320" y2="300" stroke={tg} strokeWidth={sw} />

      {/* ── Horizontal traces — cyan inner layer ── */}
      <line x1="140" y1="20"  x2="220" y2="20"  stroke={tc} strokeWidth={sw} />
      <line x1="0"   y1="100" x2="60"  y2="100" stroke={tc} strokeWidth={sw} />
      <line x1="160" y1="100" x2="220" y2="100" stroke={tc} strokeWidth={sw} />
      <line x1="0"   y1="180" x2="60"  y2="180" stroke={tc} strokeWidth={sw} />
      <line x1="260" y1="180" x2="320" y2="180" stroke={tc} strokeWidth={sw} />
      <line x1="60"  y1="220" x2="160" y2="220" stroke={tc} strokeWidth={sw} />
      <line x1="200" y1="220" x2="320" y2="220" stroke={tc} strokeWidth={sw} />
      <line x1="0"   y1="260" x2="40"  y2="260" stroke={tc} strokeWidth={sw} />
      <line x1="120" y1="320" x2="200" y2="320" stroke={tc} strokeWidth={sw} />

      {/* ── Vertical traces — green signal layer ── */}
      <line x1="40"  y1="0"   x2="40"  y2="140" stroke={tg} strokeWidth={sw} />
      <line x1="40"  y1="200" x2="40"  y2="300" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="0"   x2="60"  y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="100" x2="60"  y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="240" x2="60"  y2="320" stroke={tg} strokeWidth={sw} />
      <line x1="100" y1="0"   x2="100" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="0"   x2="160" y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="80"  x2="160" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="200" x2="160" y2="280" stroke={tg} strokeWidth={sw} />
      <line x1="220" y1="0"   x2="220" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="260" y1="0"   x2="260" y2="60"  stroke={tg} strokeWidth={sw} />
      <line x1="260" y1="200" x2="260" y2="240" stroke={tg} strokeWidth={sw} />
      <line x1="280" y1="80"  x2="280" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="280" y1="200" x2="280" y2="320" stroke={tg} strokeWidth={sw} />
      <line x1="120" y1="200" x2="120" y2="320" stroke={tg} strokeWidth={sw} />
      <line x1="240" y1="240" x2="240" y2="320" stroke={tg} strokeWidth={sw} />

      {/* ── Vertical traces — cyan inner layer ── */}
      <line x1="140" y1="0"   x2="140" y2="60"  stroke={tc} strokeWidth={sw} />
      <line x1="200" y1="40"  x2="200" y2="140" stroke={tc} strokeWidth={sw} />
      <line x1="200" y1="200" x2="200" y2="300" stroke={tc} strokeWidth={sw} />
      <line x1="20"  y1="60"  x2="20"  y2="200" stroke={tc} strokeWidth={sw} />
      <line x1="20"  y1="200" x2="20"  y2="320" stroke={tc} strokeWidth={sw} />
      <line x1="300" y1="60"  x2="300" y2="140" stroke={tc} strokeWidth={sw} />
      <line x1="300" y1="200" x2="300" y2="320" stroke={tc} strokeWidth={sw} />

      {/* ── 45° routing ── */}
      <line x1="80"  y1="60"  x2="100" y2="40"  stroke={tg} strokeWidth={sw} />
      <line x1="200" y1="40"  x2="220" y2="60"  stroke={tg} strokeWidth={sw} />
      <line x1="140" y1="60"  x2="160" y2="80"  stroke={tc} strokeWidth={sw} />
      <line x1="280" y1="60"  x2="260" y2="80"  stroke={tg} strokeWidth={sw} />
      <line x1="280" y1="140" x2="300" y2="120" stroke={tg} strokeWidth={sw} />
      <line x1="300" y1="120" x2="320" y2="120" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="200" x2="40"  y2="240" stroke={tg} strokeWidth={sw} />
      <line x1="220" y1="200" x2="240" y2="240" stroke={tg} strokeWidth={sw} />
      <line x1="160" y1="160" x2="120" y2="200" stroke={tg} strokeWidth={sw} />
      <line x1="60"  y1="100" x2="80"  y2="80"  stroke={tc} strokeWidth={sw} />
      <line x1="20"  y1="60"  x2="40"  y2="80"  stroke={tc} strokeWidth={sw} />
      <line x1="200" y1="220" x2="220" y2="200" stroke={tc} strokeWidth={sw} />
      <line x1="200" y1="300" x2="220" y2="320" stroke={tc} strokeWidth={sw} />
      <line x1="60"  y1="180" x2="80"  y2="200" stroke={tc} strokeWidth={sw} />
      <line x1="260" y1="180" x2="280" y2="200" stroke={tc} strokeWidth={sw} />

      {/* ── Solder pads ── */}
      {PADS.map(([cx, cy]) => (
        <circle key={`pad-${cx}-${cy}`} cx={cx} cy={cy} r="2.5" fill={p} />
      ))}

      {/* ── Through-hole vias (ring + centre dot) ── */}
      {VIAS.map(([cx, cy]) => (
        <g key={`via-${cx}-${cy}`}>
          <circle cx={cx} cy={cy} r="5"   fill="none" stroke={pr} strokeWidth="1" />
          <circle cx={cx} cy={cy} r="2"   fill={p} />
        </g>
      ))}

      {/* ── SOIC-8 chip (centre ~140, 110) ── */}
      <rect x="126" y="90" width="28" height="40" rx="2"
            fill="none" stroke={pr} strokeWidth="1" />
      {([97, 103, 109, 115] as const).map((y) => (
        <g key={`soic-${y}`}>
          <line x1="126" y1={y} x2="120" y2={y} stroke={pr} strokeWidth="0.75" />
          <line x1="154" y1={y} x2="160" y2={y} stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      {/* Pin-1 indicator */}
      <circle cx="129" cy="93" r="1.5" fill={pr} />

      {/* ── QFP-style larger chip (228–280, 20–72) ── */}
      <rect x="228" y="20" width="52" height="52" rx="2"
            fill="none" stroke={pr} strokeWidth="1" />
      {([28, 36, 44, 52, 60] as const).map((y) => (
        <g key={`qfp-v-${y}`}>
          <line x1="228" y1={y} x2="222" y2={y} stroke={pr} strokeWidth="0.75" />
          <line x1="280" y1={y} x2="286" y2={y} stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      {([236, 244, 252, 260, 268] as const).map((x) => (
        <g key={`qfp-h-${x}`}>
          <line x1={x} y1="20" x2={x} y2="14" stroke={pr} strokeWidth="0.75" />
          <line x1={x} y1="72" x2={x} y2="78" stroke={pr} strokeWidth="0.75" />
        </g>
      ))}
      {/* Notch on top-left corner */}
      <path d="M248,20 a3,3 0 0,0 6,0" fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── Crystal oscillator (centre 60, 260) ── */}
      <ellipse cx="60" cy="260" rx="12" ry="8" fill="none" stroke={pr} strokeWidth="0.75" />
      <line x1="48" y1="260" x2="40" y2="260" stroke={pr} strokeWidth="0.75" />
      <line x1="72" y1="260" x2="80" y2="260" stroke={pr} strokeWidth="0.75" />
      {/* Load caps */}
      <rect x="20"  y="257" width="7" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="83"  y="257" width="7" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── 6-pin connector header (x=192–258, y=250–268) ── */}
      <rect x="192" y="250" width="66" height="18" rx="1"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {([198, 208, 218, 228, 238, 248] as const).map((x) => (
        <circle key={`conn-${x}`} cx={x+2} cy="259" r="2.5"
                fill="none" stroke={pr} strokeWidth="0.75" />
      ))}

      {/* ── Inductor (coil) bridging the power trace ── */}
      <path d="M175,200 q5,-8 10,0 q5,-8 10,0 q5,-8 10,0 q5,-8 10,0"
            fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── Resistors ── */}
      {/* R1: horizontal, y=40 between x=38–60 */}
      <rect x="38"  y="37" width="20" height="6" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {/* R2: vertical, x=100 between y=60–80 */}
      <rect x="97"  y="60" width="6" height="20" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {/* R3: horizontal, y=140 between x=200–220 */}
      <rect x="202" y="137" width="16" height="6" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {/* R4: vertical, x=280 between y=97–117 */}
      <rect x="277" y="97" width="6" height="20" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── SMD Capacitors (two-pad style) ── */}
      {/* C1: vertical near crystal power rail */}
      <rect x="77"  y="250" width="6" height="5" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="77"  y="258" width="6" height="5" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C2: horizontal decoupling near power */}
      <rect x="37"  y="157" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="45"  y="157" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C3: near QFP chip */}
      <rect x="278" y="52" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="278" y="62" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C4: near SOIC */}
      <rect x="137" y="35" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="145" y="35" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      {/* C5: bottom section */}
      <rect x="177" y="277" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="185" y="277" width="5" height="6" rx="0.5" fill="none" stroke={pr} strokeWidth="0.75" />
    </g>
  );
}

export const CircuitBoard: React.FC = () => (
  <div className="circuit-board-bg" aria-hidden="true">
    <svg
      className="circuit-board-svg"
      xmlns="http://www.w3.org/2000/svg"
      width="100%"
      height="100%"
    >
      <defs>
        <pattern
          id="pcb-tile"
          x="0"
          y="0"
          width="320"
          height="320"
          patternUnits="userSpaceOnUse"
        >
          <PcbTile />
        </pattern>
      </defs>

      {/* Blurred glow layer */}
      <rect
        width="100%"
        height="100%"
        fill="url(#pcb-tile)"
        className="circuit-board-glow-layer"
      />
      {/* Sharp detail layer */}
      <rect
        width="100%"
        height="100%"
        fill="url(#pcb-tile)"
      />
    </svg>
  </div>
);
