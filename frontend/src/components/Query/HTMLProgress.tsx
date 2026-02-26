/**
 * HTMLProgress Component
 * Data values / SQL results stream in from the left (cyan), pass through a
 * central transformation gate, and emerge as HTML elements on the right (green).
 * Represents the "Result Analyst Agent formatting results as HTML" phase.
 * Color: cyan (#00eeff) → white → green (#39ff14)
 */

import React, { useEffect, useRef, useState } from 'react';
import './HTMLProgress.css';

interface HTMLProgressProps {
  label?: string;
}

interface Token {
  id: number;
  x: number;
  y: number;
  speed: number;
  dataStr: string;  // left side: data / SQL result values
  htmlStr: string;  // right side: HTML element tags
  fontSize: number;
  opacity: number;
}

const GATE_X: number = 50;
const FLICKER_HALF: number = 4;
const ACCEL_K: number = 0.07;
const NUM_TOKENS: number = 18;

const DATA_VALUES: readonly string[] = [
  '42', 'Alice', '3.14', 'TRUE', 'NULL', '2024',
  '99.5', 'Bob', '1000', 'XYZ', '0.0', 'Smith',
  '8080', 'RED', '12.7', 'YES', '404', 'Jones',
  '250', 'NYC', '7.2', 'ABC', '100%', 'Max',
];

const HTML_TAGS: readonly string[] = [
  '<table>', '<tr>', '<td>', '<th>', '<div>',
  '</table>', '</tr>', '</td>', '<body>',
  '<span>', '</div>', '<p>', '<head>',
  'class=', 'style=', '<h2>', '</body>',
  '<ul>', '<li>', '<section>', '</p>',
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
    dataStr: rand(DATA_VALUES),
    htmlStr: rand(HTML_TAGS),
    fontSize: 3.6 + Math.random() * 1.4,
    opacity: 0.65 + Math.random() * 0.35,
  };
}

export const HTMLProgress: React.FC<HTMLProgressProps> = ({ label = 'Rendering HTML...' }) => {
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
    <div className="html-progress-container">
      <svg viewBox="0 0 100 115" className="html-svg" role="img" aria-label="Rendering HTML response">
        <defs>
          <filter id="html-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="html-gate-glow" x="-80%" y="-10%" width="260%" height="120%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <clipPath id="html-clip">
            <rect x="0" y="0" width="100" height="115" />
          </clipPath>
        </defs>

        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* Gate beam */}
        <g filter="url(#html-gate-glow)">
          <line x1={GATE_X} y1="4" x2={GATE_X} y2="108" stroke="#ffffff" strokeWidth="1" opacity="0.7" />
        </g>

        {/* Gate angle-brackets — matching HTML theme */}
        {[12, 55].map((y: number) => (
          <g key={y} opacity="0.5">
            {/* Left < bracket */}
            <polyline
              points={`${GATE_X - 6},${y} ${GATE_X - 2},${y + 4} ${GATE_X - 6},${y + 8}`}
              fill="none" stroke="#fff" strokeWidth="0.9" strokeLinejoin="round"
            />
            {/* Right > bracket */}
            <polyline
              points={`${GATE_X + 6},${y} ${GATE_X + 2},${y + 4} ${GATE_X + 6},${y + 8}`}
              fill="none" stroke="#fff" strokeWidth="0.9" strokeLinejoin="round"
            />
          </g>
        ))}

        {/* Tokens */}
        <g filter="url(#html-bloom)" clipPath="url(#html-clip)">
          {tokens.map((t: Token) => {
            const inGate: boolean = t.x >= GATE_X - FLICKER_HALF && t.x <= GATE_X + FLICKER_HALF;
            const pastGate: boolean = t.x > GATE_X + FLICKER_HALF;
            const distPast: number = pastGate ? t.x - (GATE_X + FLICKER_HALF) : 0;

            let text: string;
            let color: string;
            let opacity: number = t.opacity;

            if (inGate) {
              text = frame % 2 === 0 ? t.dataStr : t.htmlStr;
              color = '#ffffff';
              opacity = 1;
            } else if (pastGate) {
              text = t.htmlStr;
              color = '#39ff14';
              opacity = t.opacity * Math.max(0.2, 1 - distPast * 0.013);
            } else {
              text = t.dataStr;
              color = '#00eeff';
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
          fontSize="4" fill="#00eeff" textAnchor="middle" opacity="0.3">DATA</text>
        <text x="77" y="109" fontFamily="'Courier New', Courier, monospace"
          fontSize="4" fill="#39ff14" textAnchor="middle" opacity="0.3">HTML</text>
      </svg>
      <div className="html-progress-label">{label}</div>
    </div>
  );
};
