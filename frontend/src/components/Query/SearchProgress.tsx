/**
 * SearchProgress Component
 * Wireframe magnifying glass with a rotating radar sweep inside the lens.
 * Small "blips" appear when the sweep detects data.
 * Color: cyan (#00eeff)
 */

import React, { useEffect, useRef, useState } from 'react';
import './SearchProgress.css';

interface SearchProgressProps {
  label?: string;
}

interface Blip {
  angle: number; // radians
  dist: number;  // distance from center (0–1)
  life: number;  // 1=fresh 0=gone
}

const CX: number = 50;
const CY: number = 50;
const R: number = 27;
const COLOR: string = '#00eeff';
const MAX_BLIPS: number = 7;

export const SearchProgress: React.FC<SearchProgressProps> = ({ label = 'Searching...' }) => {
  const sweepRef = useRef<number>(0);
  const blipsRef = useRef<Blip[]>([]);
  const rafRef = useRef<number>(0);
  const [, tick] = useState<number>(0);

  useEffect(() => {
    const loop = (): void => {
      sweepRef.current = (sweepRef.current + 0.028) % (Math.PI * 2);

      blipsRef.current = blipsRef.current
        .map((b: Blip): Blip => ({ ...b, life: b.life - 0.012 }))
        .filter((b: Blip): boolean => b.life > 0);

      if (Math.random() < 0.05 && blipsRef.current.length < MAX_BLIPS) {
        blipsRef.current.push({
          angle: sweepRef.current + Math.random() * 0.4,
          dist: 0.25 + Math.random() * 0.65,
          life: 1,
        });
      }

      tick((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const sweep: number = sweepRef.current;
  const blips: Blip[] = blipsRef.current;

  // Sweep line endpoint
  const sweepX: number = CX + R * Math.cos(sweep);
  const sweepY: number = CY + R * Math.sin(sweep);

  // Sweep trail arc (last 80°)
  const trailAngle: number = sweep - (Math.PI * 0.44);
  const trailX: number = CX + R * Math.cos(trailAngle);
  const trailY: number = CY + R * Math.sin(trailAngle);
  const arcD: string = `M ${trailX.toFixed(2)} ${trailY.toFixed(2)} A ${R} ${R} 0 0 1 ${sweepX.toFixed(2)} ${sweepY.toFixed(2)}`;

  // Handle goes from lens edge at ~45° down-right to outside
  const handleAngle: number = Math.PI * 0.72;
  const hx1: number = CX + R * Math.cos(handleAngle);
  const hy1: number = CY + R * Math.sin(handleAngle);
  const hx2: number = hx1 + 14;
  const hy2: number = hy1 + 14;

  return (
    <div className="search-progress-container">
      <svg viewBox="0 0 100 115" className="search-svg" role="img" aria-label="Searching data">
        <defs>
          <filter id="srch-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id="srch-clip">
            <circle cx={CX} cy={CY} r={R} />
          </clipPath>
        </defs>

        {/* Black background */}
        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* Interior grid */}
        <g clipPath="url(#srch-clip)" opacity="0.10">
          {[-18, -9, 0, 9, 18].map((d: number) => (
            <React.Fragment key={d}>
              <line x1={CX + d} y1={CY - R} x2={CX + d} y2={CY + R} stroke={COLOR} strokeWidth="0.5" />
              <line x1={CX - R} y1={CY + d} x2={CX + R} y2={CY + d} stroke={COLOR} strokeWidth="0.5" />
            </React.Fragment>
          ))}
        </g>

        {/* Range rings (faint) */}
        {[R * 0.35, R * 0.68].map((r: number, i: number) => (
          <circle key={i} cx={CX} cy={CY} r={r} fill="none" stroke={COLOR} strokeWidth="0.4" opacity="0.18" />
        ))}

        {/* Sweep trail + sweep line + blips (clipped to lens) */}
        <g clipPath="url(#srch-clip)" filter="url(#srch-bloom)">
          {/* Sweep fill (fan-shaped glow) */}
          <path d={arcD} fill="none" stroke={COLOR} strokeWidth="20" opacity="0.10" strokeLinecap="butt" />
          {/* Sweep line */}
          <line x1={CX} y1={CY} x2={sweepX} y2={sweepY} stroke={COLOR} strokeWidth="1.1" opacity="0.9" />
          {/* Center dot */}
          <circle cx={CX} cy={CY} r="1.8" fill={COLOR} opacity="0.85" />
          {/* Blips */}
          {blips.map((b: Blip, i: number) => {
            const bx: number = CX + b.dist * R * Math.cos(b.angle);
            const by: number = CY + b.dist * R * Math.sin(b.angle);
            return (
              <circle key={i} cx={bx} cy={by} r={2.8 * b.life} fill={COLOR} opacity={b.life * 0.85} />
            );
          })}
        </g>

        {/* Lens outline */}
        <circle cx={CX} cy={CY} r={R} fill="none" stroke={COLOR} strokeWidth="2" filter="url(#srch-bloom)" />

        {/* Crosshairs extending past lens */}
        <line x1={CX - R - 5} y1={CY} x2={CX + R + 5} y2={CY} stroke={COLOR} strokeWidth="0.7" opacity="0.25" />
        <line x1={CX} y1={CY - R - 5} x2={CX} y2={CY + R + 5} stroke={COLOR} strokeWidth="0.7" opacity="0.25" />

        {/* Handle */}
        <line x1={hx1} y1={hy1} x2={hx2} y2={hy2}
          stroke={COLOR} strokeWidth="3.5" strokeLinecap="round" filter="url(#srch-bloom)" />
      </svg>
      <div className="search-progress-label">{label}</div>
    </div>
  );
};
