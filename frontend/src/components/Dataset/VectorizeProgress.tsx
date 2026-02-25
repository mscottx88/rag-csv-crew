/**
 * Vectorize Progress Component
 * Animated SVG showing the embedding phase: random English words flow
 * left-to-right through a glowing neon gateway and emerge as vector numbers
 * that accelerate off the right edge — visualising text being encoded into
 * high-dimensional vectors.
 *
 * Colour language:
 *   Neon pink  (#ffff00) — raw words / text on the left
 *   White      (#ffffff) — the transformation flash at the gateway
 *   Neon cyan  (#00eeff) — output vector numbers on the right
 */

import React, { useEffect, useRef, useState } from 'react';
import { WORD_LIST } from './wordList';
import './VectorizeProgress.css';

interface VectorizeProgressProps {
  label?: string;
}

interface VToken {
  id: number;
  x: number;
  y: number;
  baseSpeed: number;  // speed before the gate; increases after
  word: string;       // input text word (shown on left)
  numStr: string;     // output vector number (shown on right)
  fontSize: number;
  opacity: number;
}

const GATE_X: number = 50;
const FLICKER_HALF: number = 4;    // morph zone GATE_X ± 4
const ACCEL_K: number = 0.09;      // acceleration coefficient after the gate
const NUM_TOKENS: number = 22;

const NUMS: readonly string[] = [
  '0.24731', '-0.83142', '0.05891', '-0.61204', '0.91837',
  '-0.07563', '0.44209', '-0.38817', '0.72654', '-0.19482',
  '0.547832', '-0.063741', '0.881290', '-0.412673', '0.234857',
  '-0.778341', '0.106294', '-0.953017', '0.671548', '-0.328904',
  '0.0293847', '-0.7841203', '0.4192736', '-0.1057394', '0.6638201',
  '-0.2914857', '0.8073621', '-0.4461038', '0.1729465', '-0.9234710',
  '0.3847291', '-0.6102948', '0.7293847', '-0.0482917', '0.5561029',
];

function randFromArray(arr: readonly string[]): string {
  return arr[Math.floor(Math.random() * arr.length)] ?? '0';
}

function makeVToken(id: number, staggered: boolean = false): VToken {
  return {
    id,
    x: staggered ? Math.random() * 115 - 20 : -(8 + Math.random() * 20),
    y: 10 + Math.random() * 95,
    baseSpeed: 0.22 + Math.random() * 0.30,
    word: randFromArray(WORD_LIST),
    numStr: randFromArray(NUMS),
    // Smaller font — words on the left and long decimals on the right both need room
    fontSize: 3.8 + Math.random() * 1.2,
    opacity: 0.7 + Math.random() * 0.3,
  };
}

function stepVTokens(tokens: VToken[]): VToken[] {
  return tokens.map((t: VToken): VToken => {
    const pastGate: boolean = t.x > GATE_X + FLICKER_HALF;
    let speed: number = t.baseSpeed;

    if (pastGate) {
      // Accelerate proportionally to distance past the gate
      const distPast: number = t.x - (GATE_X + FLICKER_HALF);
      speed = t.baseSpeed * (1 + distPast * ACCEL_K);
    }

    const newX: number = t.x + speed;
    // Assign a fresh word when a token exits right — keeps the pool varied
    return newX > 120 ? makeVToken(t.id) : { ...t, x: newX };
  });
}

/** Small right-pointing chevron polygon */
function chevronPoints(cx: number, cy: number, r: number): string {
  return `${cx - r},${cy - r} ${cx + r},${cy} ${cx - r},${cy + r}`;
}

export const VectorizeProgress: React.FC<VectorizeProgressProps> = ({
  label = 'Embedding...',
}) => {
  const tokensRef = useRef<VToken[]>(
    Array.from({ length: NUM_TOKENS }, (_: unknown, i: number): VToken =>
      makeVToken(i, true)
    )
  );
  const rafRef = useRef<number>(0);
  const frameRef = useRef<number>(0);
  const [, forceUpdate] = useState<number>(0);

  useEffect(() => {
    const tick = (): void => {
      tokensRef.current = stepVTokens(tokensRef.current);
      frameRef.current += 1;
      forceUpdate((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const tokens: VToken[] = tokensRef.current;
  const frame: number = frameRef.current;

  return (
    <div className="vectorize-progress-container">
      <svg
        viewBox="0 0 100 115"
        className="vectorize-svg"
        role="img"
        aria-label="Embedding data into vectors"
      >
        <defs>
          {/* Soft bloom for tokens */}
          <filter id="vec-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Heavy glow for the gateway beam */}
          <filter id="vec-gate-glow" x="-80%" y="-10%" width="260%" height="120%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Black background */}
        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* ── Gateway beam ── */}
        <g filter="url(#vec-gate-glow)">
          <line
            x1={GATE_X} y1="4" x2={GATE_X} y2="111"
            stroke="#ffff00" strokeWidth="1.2" opacity="0.85"
          />
        </g>

        {/* Chevron markers along the beam */}
        <g opacity="0.4">
          {[14, 26, 38, 50, 62, 74, 86, 98].map((y: number) => (
            <polygon
              key={y}
              points={chevronPoints(GATE_X, y, 2.8)}
              fill="#ffff00"
            />
          ))}
        </g>

        {/* ── Flowing word tokens ── */}
        <g filter="url(#vec-bloom)">
          {tokens.map((t: VToken) => {
            const inFlicker: boolean =
              t.x >= GATE_X - FLICKER_HALF && t.x <= GATE_X + FLICKER_HALF;
            const pastGate: boolean = t.x > GATE_X + FLICKER_HALF;

            let displayStr: string;
            let color: string;
            let opacity: number = t.opacity;
            let fontSize: number = t.fontSize;

            if (inFlicker) {
              // Flash white: alternate between the word and its vector number
              displayStr = frame % 2 === 0 ? t.word : t.numStr;
              color = '#ffffff';
              opacity = 1;
              fontSize = t.fontSize * 1.15; // brief pop as it passes through
            } else if (pastGate) {
              displayStr = t.numStr;
              color = '#00eeff';
              // Fade as they fly off — motion-trail feel
              const distPast: number = t.x - (GATE_X + FLICKER_HALF);
              opacity = t.opacity * Math.max(0.25, 1 - distPast * 0.012);
            } else {
              displayStr = t.word;
              color = '#ffff00';
            }

            return (
              <text
                key={t.id}
                x={t.x}
                y={t.y}
                fontFamily="'Courier New', Courier, monospace"
                fontSize={fontSize}
                fill={color}
                textAnchor="middle"
                dominantBaseline="middle"
                opacity={opacity}
              >
                {displayStr}
              </text>
            );
          })}
        </g>

        {/* Faint zone labels */}
        <text
          x="24" y="108"
          fontFamily="'Courier New', Courier, monospace"
          fontSize="4.5" fill="#ffff00" textAnchor="middle" opacity="0.3"
        >
          TEXT
        </text>
        <text
          x="76" y="108"
          fontFamily="'Courier New', Courier, monospace"
          fontSize="4.5" fill="#00eeff" textAnchor="middle" opacity="0.3"
        >
          VECTOR
        </text>
      </svg>

      <div className="vectorize-progress-label">{label}</div>
    </div>
  );
};
