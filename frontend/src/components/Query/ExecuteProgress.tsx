/**
 * ExecuteProgress Component
 * Wireframe database cylinder — data "beams" (particles) stream in from the
 * left through the cylinder and emerge as result rows on the right.
 * Represents the "executing SQL query" phase.
 * Color: cyan (#00eeff)
 */

import React, { useEffect, useRef, useState } from 'react';
import './ExecuteProgress.css';

interface ExecuteProgressProps {
  label?: string;
}

interface Beam {
  id: number;
  y: number;       // vertical position within cylinder (top=22, bot=78)
  x: number;       // horizontal progress: 0=left edge → 1=right edge
  speed: number;
  color: string;
  opacity: number;
}

const COLOR: string = '#00eeff';
const COLOR2: string = '#00ffcc';

// Cylinder geometry
const CYL_LEFT: number = 20;
const CYL_RIGHT: number = 80;
const CYL_TOP_Y: number = 30;
const CYL_BOT_Y: number = 75;
const CYL_RX: number = 30;   // ellipse x-radius
const CYL_RY: number = 7;    // ellipse y-radius
const CYL_MID_Y: number = (CYL_TOP_Y + CYL_BOT_Y) / 2;

const BEAM_COLORS: readonly string[] = [COLOR, COLOR2, '#00ccff'];
const MAX_BEAMS: number = 14;

function makeBeam(id: number): Beam {
  return {
    id,
    y: CYL_TOP_Y + 3 + Math.random() * (CYL_BOT_Y - CYL_TOP_Y - 6),
    x: Math.random(),
    speed: 0.008 + Math.random() * 0.008,
    color: BEAM_COLORS[Math.floor(Math.random() * BEAM_COLORS.length)] ?? COLOR,
    opacity: 0.6 + Math.random() * 0.4,
  };
}

export const ExecuteProgress: React.FC<ExecuteProgressProps> = ({ label = 'Executing...' }) => {
  const beamsRef = useRef<Beam[]>(
    Array.from({ length: MAX_BEAMS }, (_: unknown, i: number): Beam => makeBeam(i))
  );
  const rafRef = useRef<number>(0);
  const [, tick] = useState<number>(0);

  useEffect(() => {
    const loop = (): void => {
      beamsRef.current = beamsRef.current.map((b: Beam): Beam => {
        const newX: number = b.x + b.speed;
        return newX > 1.1 ? makeBeam(b.id) : { ...b, x: newX };
      });
      tick((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const beams: Beam[] = beamsRef.current;

  // Cylinder clip path: rectangle body + top and bottom ellipses
  const cylW: number = CYL_RIGHT - CYL_LEFT;

  return (
    <div className="execute-progress-container">
      <svg viewBox="0 0 100 115" className="execute-svg" role="img" aria-label="Executing query">
        <defs>
          <filter id="exec-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Clip beams to the cylinder body */}
          <clipPath id="exec-cyl-clip">
            <rect x={CYL_LEFT} y={CYL_TOP_Y} width={cylW} height={CYL_BOT_Y - CYL_TOP_Y} />
          </clipPath>
        </defs>

        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* ── Cylinder body background ── */}
        <rect x={CYL_LEFT} y={CYL_TOP_Y} width={cylW} height={CYL_BOT_Y - CYL_TOP_Y} fill="#050505" />

        {/* ── Beam particles inside cylinder ── */}
        <g clipPath="url(#exec-cyl-clip)" filter="url(#exec-bloom)">
          {beams.map((b: Beam) => {
            const bx: number = CYL_LEFT + b.x * cylW;
            return (
              <g key={b.id}>
                {/* Trail */}
                <line
                  x1={Math.max(CYL_LEFT, bx - 8)} y1={b.y}
                  x2={bx} y2={b.y}
                  stroke={b.color} strokeWidth="1.2" opacity={b.opacity * 0.4}
                  strokeLinecap="round"
                />
                {/* Head dot */}
                <circle cx={bx} cy={b.y} r="1.6" fill={b.color} opacity={b.opacity} />
              </g>
            );
          })}
        </g>

        {/* ── Wireframe cylinder outline ── */}
        <g filter="url(#exec-bloom)">
          {/* Left wall */}
          <line x1={CYL_LEFT} y1={CYL_TOP_Y} x2={CYL_LEFT} y2={CYL_BOT_Y} stroke={COLOR} strokeWidth="1.6" />
          {/* Right wall */}
          <line x1={CYL_RIGHT} y1={CYL_TOP_Y} x2={CYL_RIGHT} y2={CYL_BOT_Y} stroke={COLOR} strokeWidth="1.6" />

          {/* Top ellipse */}
          <ellipse cx={CYL_MID_Y - 2.5} cy={CYL_TOP_Y} rx={CYL_RX} ry={CYL_RY}
            fill="#000" stroke={COLOR} strokeWidth="1.6" />
          {/* Mid divider ellipse (data layers) */}
          <ellipse cx={CYL_MID_Y - 2.5} cy={CYL_MID_Y} rx={CYL_RX} ry={CYL_RY}
            fill="none" stroke={COLOR} strokeWidth="0.7" opacity="0.35" />
          {/* Bottom ellipse */}
          <ellipse cx={CYL_MID_Y - 2.5} cy={CYL_BOT_Y} rx={CYL_RX} ry={CYL_RY}
            fill="#000" stroke={COLOR} strokeWidth="1.6" />
        </g>

        {/* ── Input arrow (left side) ── */}
        <g opacity="0.6">
          <line x1="4" y1={CYL_MID_Y} x2={CYL_LEFT - 1} y2={CYL_MID_Y}
            stroke={COLOR} strokeWidth="1" strokeDasharray="2 2" />
          <polygon
            points={`${CYL_LEFT - 1},${CYL_MID_Y - 2.5} ${CYL_LEFT + 4},${CYL_MID_Y} ${CYL_LEFT - 1},${CYL_MID_Y + 2.5}`}
            fill={COLOR}
          />
          <text x="2" y={CYL_MID_Y - 4}
            fontFamily="'Courier New', Courier, monospace" fontSize="3.5"
            fill={COLOR} opacity="0.5">SQL</text>
        </g>

        {/* ── Output arrow (right side) ── */}
        <g opacity="0.6">
          <line x1={CYL_RIGHT + 1} y1={CYL_MID_Y} x2="96" y2={CYL_MID_Y}
            stroke={COLOR} strokeWidth="1" strokeDasharray="2 2" />
          <polygon
            points={`${CYL_RIGHT + 5},${CYL_MID_Y - 2.5} ${CYL_RIGHT + 10},${CYL_MID_Y} ${CYL_RIGHT + 5},${CYL_MID_Y + 2.5}`}
            fill={COLOR}
          />
          <text x="82" y={CYL_MID_Y - 4}
            fontFamily="'Courier New', Courier, monospace" fontSize="3.5"
            fill={COLOR} opacity="0.5">ROWS</text>
        </g>

        {/* Label inside cylinder top (faint) */}
        <text x="50" y={CYL_TOP_Y - 2}
          fontFamily="'Courier New', Courier, monospace" fontSize="3.8"
          fill={COLOR} textAnchor="middle" opacity="0.3">DATABASE</text>
      </svg>
      <div className="execute-progress-label">{label}</div>
    </div>
  );
};
