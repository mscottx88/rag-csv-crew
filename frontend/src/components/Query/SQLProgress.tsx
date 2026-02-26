/**
 * SQLProgress Component
 * Natural language words stream in from the left (gold), pass through a central
 * transformation gate, and emerge as SQL tokens on the right (cyan).
 * Represents the "text-to-SQL generation" phase.
 * Color: gold (#ffd700) → white → cyan (#00eeff)
 */

import React, { useEffect, useRef, useState } from 'react';
import './SQLProgress.css';

interface SQLProgressProps {
  label?: string;
}

interface Token {
  id: number;
  x: number;
  y: number;
  speed: number;
  word: string;
  sqlStr: string;
  fontSize: number;
  opacity: number;
}

const GATE_X: number = 50;
const FLICKER_HALF: number = 4;
const ACCEL_K: number = 0.07;
const NUM_TOKENS: number = 18;

const NL_WORDS: readonly string[] = [
  'show', 'find', 'count', 'total', 'list', 'average', 'top', 'where',
  'maximum', 'minimum', 'group', 'filter', 'between', 'all', 'unique',
  'sum', 'first', 'last', 'compare', 'rank',
];

const SQL_TOKENS: readonly string[] = [
  'SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY',
  'COUNT(*)', 'AVG(x)', 'SUM(x)', 'LIMIT', 'HAVING', 'INNER',
  'ON id', 'ASC', 'DESC', 'DISTINCT', 'MAX(x)', 'MIN(x)',
];

function rand<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)] as T;
}

function makeToken(id: number, staggered: boolean = false): Token {
  return {
    id,
    x: staggered ? Math.random() * 110 - 15 : -(6 + Math.random() * 18),
    y: 10 + Math.random() * 95,
    speed: 0.20 + Math.random() * 0.28,
    word: rand(NL_WORDS),
    sqlStr: rand(SQL_TOKENS),
    fontSize: 3.6 + Math.random() * 1.4,
    opacity: 0.65 + Math.random() * 0.35,
  };
}

export const SQLProgress: React.FC<SQLProgressProps> = ({ label = 'Generating SQL...' }) => {
  const tokensRef = useRef<Token[]>(
    Array.from({ length: NUM_TOKENS }, (_: unknown, i: number): Token => makeToken(i, true))
  );
  const rafRef = useRef<number>(0);
  const frameRef = useRef<number>(0);
  const [, tick] = useState<number>(0);

  useEffect(() => {
    const loop = (): void => {
      tokensRef.current = tokensRef.current.map((t: Token): Token => {
        const pastGate: boolean = t.x > GATE_X + FLICKER_HALF;
        const distPast: number = pastGate ? t.x - (GATE_X + FLICKER_HALF) : 0;
        const speed: number = pastGate ? t.speed * (1 + distPast * ACCEL_K) : t.speed;
        const newX: number = t.x + speed;
        return newX > 120 ? makeToken(t.id) : { ...t, x: newX };
      });
      frameRef.current += 1;
      tick((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const tokens: Token[] = tokensRef.current;
  const frame: number = frameRef.current;

  return (
    <div className="sql-progress-container">
      <svg viewBox="0 0 100 115" className="sql-svg" role="img" aria-label="Generating SQL query">
        <defs>
          <filter id="sql-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="sql-gate-glow" x="-80%" y="-10%" width="260%" height="120%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Clip tokens to viewport */}
          <clipPath id="sql-clip">
            <rect x="0" y="0" width="100" height="115" />
          </clipPath>
        </defs>

        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* Gate beam */}
        <g filter="url(#sql-gate-glow)">
          <line x1={GATE_X} y1="4" x2={GATE_X} y2="108" stroke="#ffffff" strokeWidth="1" opacity="0.7" />
        </g>

        {/* Gate brackets */}
        {[10, 55].map((y: number) => (
          <g key={y} opacity="0.5">
            <line x1={GATE_X - 5} y1={y} x2={GATE_X - 5} y2={y + 4} stroke="#fff" strokeWidth="0.8" />
            <line x1={GATE_X - 5} y1={y} x2={GATE_X - 2} y2={y} stroke="#fff" strokeWidth="0.8" />
            <line x1={GATE_X + 2} y1={y} x2={GATE_X + 5} y2={y} stroke="#fff" strokeWidth="0.8" />
            <line x1={GATE_X + 5} y1={y} x2={GATE_X + 5} y2={y + 4} stroke="#fff" strokeWidth="0.8" />
          </g>
        ))}

        {/* Tokens */}
        <g filter="url(#sql-bloom)" clipPath="url(#sql-clip)">
          {tokens.map((t: Token) => {
            const inGate: boolean = t.x >= GATE_X - FLICKER_HALF && t.x <= GATE_X + FLICKER_HALF;
            const pastGate: boolean = t.x > GATE_X + FLICKER_HALF;
            const distPast: number = pastGate ? t.x - (GATE_X + FLICKER_HALF) : 0;

            let text: string;
            let color: string;
            let opacity: number = t.opacity;

            if (inGate) {
              text = frame % 2 === 0 ? t.word : t.sqlStr;
              color = '#ffffff';
              opacity = 1;
            } else if (pastGate) {
              text = t.sqlStr;
              color = '#00eeff';
              opacity = t.opacity * Math.max(0.2, 1 - distPast * 0.013);
            } else {
              text = t.word;
              color = '#ffd700';
            }

            return (
              <text
                key={t.id}
                x={t.x}
                y={t.y}
                fontFamily="'Courier New', Courier, monospace"
                fontSize={t.fontSize}
                fill={color}
                textAnchor="middle"
                dominantBaseline="middle"
                opacity={opacity}
              >
                {text}
              </text>
            );
          })}
        </g>

        {/* Zone labels */}
        <text x="22" y="109" fontFamily="'Courier New', Courier, monospace"
          fontSize="4" fill="#ffd700" textAnchor="middle" opacity="0.3">QUERY</text>
        <text x="77" y="109" fontFamily="'Courier New', Courier, monospace"
          fontSize="4" fill="#00eeff" textAnchor="middle" opacity="0.3">SQL</text>
      </svg>
      <div className="sql-progress-label">{label}</div>
    </div>
  );
};
