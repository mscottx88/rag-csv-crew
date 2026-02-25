/**
 * Cog Progress Component
 * Two interlocking gears (large + small) rotating in opposite directions,
 * neon pink on black, pure CSS animation — no JS loop required.
 */

import React from 'react';
import './CogProgress.css';

interface CogProgressProps {
  label?: string;
}

/**
 * Build an SVG path string for a gear polygon centred at (0,0).
 * Alternates between outer (tooth tip) and inner (tooth root) radius
 * at evenly-spaced angles.
 */
function gearPath(teeth: number, rInner: number, rOuter: number, offsetDeg: number = 0): string {
  const points: string[] = [];
  const total: number = teeth * 2; // alternating inner/outer vertices

  for (let i: number = 0; i < total; i++) {
    const angleDeg: number = (i / total) * 360 + offsetDeg;
    const angleRad: number = (angleDeg * Math.PI) / 180;
    const r: number = i % 2 === 0 ? rOuter : rInner;
    const x: number = parseFloat((r * Math.cos(angleRad)).toFixed(3));
    const y: number = parseFloat((r * Math.sin(angleRad)).toFixed(3));
    points.push(`${x},${y}`);
  }

  return `M ${points.join(' L ')} Z`;
}

// Large gear: 10 teeth, centred at (36, 60)
const LARGE_CX: number = 36;
const LARGE_CY: number = 60;
const LARGE_INNER: number = 15;
const LARGE_OUTER: number = 22;
const LARGE_TEETH: number = 10;
const LARGE_HOLE: number = 7;

// Small gear: 6 teeth, centred at (69, 38)
// Distance between centres ≈ LARGE_OUTER + SMALL_OUTER so teeth mesh
const SMALL_CX: number = 69;
const SMALL_CY: number = 38;
const SMALL_INNER: number = 9;
const SMALL_OUTER: number = 13;
const SMALL_TEETH: number = 6;
const SMALL_HOLE: number = 4;

const largePath: string = gearPath(LARGE_TEETH, LARGE_INNER, LARGE_OUTER, 9);
const smallPath: string = gearPath(SMALL_TEETH, SMALL_INNER, SMALL_OUTER, 15);

export const CogProgress: React.FC<CogProgressProps> = ({ label = 'Complete!' }) => {
  return (
    <div className="cog-progress-container">
      <svg
        viewBox="0 0 100 115"
        className="cog-svg"
        role="img"
        aria-label="Upload complete"
      >
        <defs>
          <filter id="cog-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Black background */}
        <rect x="0" y="0" width="100" height="115" fill="#000" rx="4" />

        <g filter="url(#cog-bloom)">
          {/* Large gear — rotates clockwise */}
          <g
            className="cog-large"
            transform={`translate(${LARGE_CX}, ${LARGE_CY})`}
          >
            <path d={largePath} fill="none" stroke="#ffd700" strokeWidth="1.4" />
            {/* Hub circle */}
            <circle r={LARGE_HOLE} fill="none" stroke="#ffd700" strokeWidth="1.2" />
            {/* Spokes */}
            {[0, 60, 120, 180, 240, 300].map((deg: number) => {
              const rad: number = (deg * Math.PI) / 180;
              return (
                <line
                  key={deg}
                  x1={(LARGE_HOLE * Math.cos(rad)).toFixed(2)}
                  y1={(LARGE_HOLE * Math.sin(rad)).toFixed(2)}
                  x2={(LARGE_INNER * 0.85 * Math.cos(rad)).toFixed(2)}
                  y2={(LARGE_INNER * 0.85 * Math.sin(rad)).toFixed(2)}
                  stroke="#ffd700"
                  strokeWidth="1"
                  opacity="0.6"
                />
              );
            })}
          </g>

          {/* Small gear — rotates counter-clockwise at correct speed ratio */}
          <g
            className="cog-small"
            transform={`translate(${SMALL_CX}, ${SMALL_CY})`}
          >
            <path d={smallPath} fill="none" stroke="#ffaa00" strokeWidth="1.2" />
            <circle r={SMALL_HOLE} fill="none" stroke="#ffaa00" strokeWidth="1" />
            {[0, 90, 180, 270].map((deg: number) => {
              const rad: number = (deg * Math.PI) / 180;
              return (
                <line
                  key={deg}
                  x1={(SMALL_HOLE * Math.cos(rad)).toFixed(2)}
                  y1={(SMALL_HOLE * Math.sin(rad)).toFixed(2)}
                  x2={(SMALL_INNER * 0.85 * Math.cos(rad)).toFixed(2)}
                  y2={(SMALL_INNER * 0.85 * Math.sin(rad)).toFixed(2)}
                  stroke="#ffaa00"
                  strokeWidth="0.9"
                  opacity="0.6"
                />
              );
            })}
          </g>
        </g>
      </svg>

      <div className="cog-progress-label">{label}</div>
    </div>
  );
};
