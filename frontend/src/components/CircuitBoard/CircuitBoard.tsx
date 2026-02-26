/**
 * CircuitBoard
 * Renders a subtle, fixed-position PCB-style wireframe background:
 * traces, L-bends, T-junctions, solder pads, and component outlines.
 * Purely decorative — pointer events disabled.
 */

import React from 'react';
import './CircuitBoard.css';

/** A single 160×160 PCB tile, drawn at very low opacity. */
function PcbTile(): React.ReactElement {
  const t  = 'rgba(57,255,20,0.07)';   // trace colour
  const p  = 'rgba(57,255,20,0.16)';   // solder-pad fill
  const pr = 'rgba(57,255,20,0.10)';   // through-hole ring / component stroke
  const sw = 1;                         // stroke-width for traces

  return (
    <g>
      {/* ── Traces ── */}
      {/* Horizontal */}
      <line x1="0"   y1="40"  x2="60"  y2="40"  stroke={t} strokeWidth={sw} />
      <line x1="60"  y1="40"  x2="100" y2="40"  stroke={t} strokeWidth={sw} />
      <line x1="100" y1="40"  x2="160" y2="40"  stroke={t} strokeWidth={sw} />
      <line x1="0"   y1="100" x2="40"  y2="100" stroke={t} strokeWidth={sw} />
      <line x1="40"  y1="100" x2="80"  y2="100" stroke={t} strokeWidth={sw} />
      <line x1="120" y1="100" x2="160" y2="100" stroke={t} strokeWidth={sw} />
      <line x1="20"  y1="140" x2="80"  y2="140" stroke={t} strokeWidth={sw} />
      <line x1="100" y1="20"  x2="160" y2="20"  stroke={t} strokeWidth={sw} />

      {/* Vertical */}
      <line x1="60"  y1="0"   x2="60"  y2="40"  stroke={t} strokeWidth={sw} />
      <line x1="60"  y1="40"  x2="60"  y2="80"  stroke={t} strokeWidth={sw} />
      <line x1="40"  y1="80"  x2="40"  y2="140" stroke={t} strokeWidth={sw} />
      <line x1="100" y1="20"  x2="100" y2="100" stroke={t} strokeWidth={sw} />
      <line x1="120" y1="60"  x2="120" y2="160" stroke={t} strokeWidth={sw} />
      <line x1="80"  y1="100" x2="80"  y2="160" stroke={t} strokeWidth={sw} />
      <line x1="20"  y1="120" x2="20"  y2="160" stroke={t} strokeWidth={sw} />

      {/* ── Solder pads (filled circles at junctions / endpoints) ── */}
      <circle cx="60"  cy="40"  r="2.5" fill={p} />
      <circle cx="100" cy="40"  r="2.5" fill={p} />
      <circle cx="40"  cy="100" r="2.5" fill={p} />
      <circle cx="80"  cy="100" r="2.5" fill={p} />
      <circle cx="100" cy="100" r="2.5" fill={p} />
      <circle cx="100" cy="20"  r="2.5" fill={p} />
      <circle cx="120" cy="100" r="2.5" fill={p} />
      <circle cx="60"  cy="0"   r="2.5" fill={p} />
      <circle cx="40"  cy="140" r="2.5" fill={p} />
      <circle cx="80"  cy="160" r="2.5" fill={p} />
      <circle cx="20"  cy="120" r="2.5" fill={p} />

      {/* ── Through-hole pads (ring + inner dot) ── */}
      <circle cx="60"  cy="80"  r="4"   fill="none" stroke={pr} strokeWidth="0.75" />
      <circle cx="60"  cy="80"  r="1.5" fill={p} />

      <circle cx="120" cy="60"  r="4"   fill="none" stroke={pr} strokeWidth="0.75" />
      <circle cx="120" cy="60"  r="1.5" fill={p} />

      <circle cx="20"  cy="140" r="4"   fill="none" stroke={pr} strokeWidth="0.75" />
      <circle cx="20"  cy="140" r="1.5" fill={p} />

      {/* ── Resistor outline (small rect bridging a trace) ── */}
      {/* Bridges the horizontal trace at y=40 between x=60 and x=100 */}
      <rect x="70" y="36" width="20" height="8" rx="1.5"
            fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── IC chip outline (DIP footprint, bridging y=40..100 column near x=100) ── */}
      <rect x="92" y="55" width="16" height="38" rx="2"
            fill="none" stroke={pr} strokeWidth="0.75" />
      {/* Pin indicators on left and right */}
      <line x1="92" y1="62" x2="88" y2="62" stroke={pr} strokeWidth="0.75" />
      <line x1="92" y1="70" x2="88" y2="70" stroke={pr} strokeWidth="0.75" />
      <line x1="92" y1="78" x2="88" y2="78" stroke={pr} strokeWidth="0.75" />
      <line x1="108" y1="62" x2="112" y2="62" stroke={pr} strokeWidth="0.75" />
      <line x1="108" y1="70" x2="112" y2="70" stroke={pr} strokeWidth="0.75" />
      <line x1="108" y1="78" x2="112" y2="78" stroke={pr} strokeWidth="0.75" />
      {/* Notch on top */}
      <path d="M98,55 a2,2 0 0,0 4,0" fill="none" stroke={pr} strokeWidth="0.75" />

      {/* ── Capacitor outline (small square pads) ── */}
      <rect x="32" y="97" width="5" height="6" rx="0.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
      <rect x="43" y="97" width="5" height="6" rx="0.5"
            fill="none" stroke={pr} strokeWidth="0.75" />
    </g>
  );
}

export const CircuitBoard: React.FC = () => {
  return (
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
            x="0" y="0"
            width="160" height="160"
            patternUnits="userSpaceOnUse"
          >
            <PcbTile />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#pcb-tile)" />
      </svg>
    </div>
  );
};
