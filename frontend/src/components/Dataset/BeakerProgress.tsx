/**
 * Beaker Progress Component
 * Animated SVG lab beaker — black background with classic screensaver-style
 * neon-pink geometric shapes bouncing around with gradient trails.
 */

import React, { useEffect, useRef, useState } from 'react';
import './BeakerProgress.css';

interface BeakerProgressProps {
  progress: number; // 0–100
}

interface TrailPoint {
  x: number;
  y: number;
  rotation: number;
}

interface Shape {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  type: number; // 0=square 1=triangle 2=diamond 3=hexagon
  rotation: number;
  rotationSpeed: number;
  color: string;
  trail: TrailPoint[];
}

// Beaker interior bounds in SVG user units
const MIN_X: number = 27;
const MAX_X: number = 73;
const MIN_Y: number = 23;
const MAX_Y: number = 102;
const TRAIL_LEN: number = 14;
const COLORS: readonly string[] = ['#ff10f0', '#ff69b4', '#ff00ff', '#ff1493'];

function makePoints(type: number, size: number): string {
  switch (type) {
    case 0: { // square
      const s: number = size * 0.85;
      return `${-s},${-s} ${s},${-s} ${s},${s} ${-s},${s}`;
    }
    case 1: { // triangle
      const h: number = size * 1.15;
      return `0,${-h} ${h * 0.95},${h * 0.65} ${-h * 0.95},${h * 0.65}`;
    }
    case 2: { // diamond
      return `0,${-size * 1.4} ${size * 0.8},0 0,${size * 1.4} ${-size * 0.8},0`;
    }
    case 3: { // hexagon
      return Array.from({ length: 6 }, (_: unknown, i: number) => {
        const a: number = (i * Math.PI) / 3;
        return `${(size * Math.cos(a)).toFixed(2)},${(size * Math.sin(a)).toFixed(2)}`;
      }).join(' ');
    }
    default:
      return '';
  }
}

function initShapes(): Shape[] {
  const w: number = MAX_X - MIN_X;
  const h: number = MAX_Y - MIN_Y;
  return COLORS.map(
    (color: string, i: number): Shape => ({
      x: MIN_X + (w * (i + 1)) / (COLORS.length + 1),
      y: MIN_Y + h * 0.25 + Math.random() * h * 0.5,
      vx: (0.5 + Math.random() * 0.7) * (i % 2 === 0 ? 1 : -1),
      vy: (0.5 + Math.random() * 0.7) * (i < 2 ? 1 : -1),
      size: 6 + Math.random() * 5,
      type: i,
      rotation: Math.random() * 360,
      rotationSpeed: (1.2 + Math.random() * 2) * (i % 2 === 0 ? 1 : -1),
      color,
      trail: [],
    })
  );
}

function stepShapes(shapes: Shape[]): Shape[] {
  return shapes.map((shape: Shape): Shape => {
    const trail: TrailPoint[] = [
      ...shape.trail.slice(-(TRAIL_LEN - 1)),
      { x: shape.x, y: shape.y, rotation: shape.rotation },
    ];

    const pad: number = shape.size * 1.4;
    let { x, y, vx, vy } = shape;
    x += vx;
    y += vy;

    if (x - pad < MIN_X) { x = MIN_X + pad; vx = Math.abs(vx); }
    if (x + pad > MAX_X) { x = MAX_X - pad; vx = -Math.abs(vx); }
    if (y - pad < MIN_Y) { y = MIN_Y + pad; vy = Math.abs(vy); }
    if (y + pad > MAX_Y) { y = MAX_Y - pad; vy = -Math.abs(vy); }

    return { ...shape, x, y, vx, vy, rotation: shape.rotation + shape.rotationSpeed, trail };
  });
}

export const BeakerProgress: React.FC<BeakerProgressProps> = ({ progress }) => {
  const clampedProgress: number = Math.min(100, Math.max(0, progress));
  const shapesRef = useRef<Shape[]>(initShapes());
  const frameRef = useRef<number>(0);
  const [, forceUpdate] = useState<number>(0);

  useEffect(() => {
    const tick = (): void => {
      shapesRef.current = stepShapes(shapesRef.current);
      forceUpdate((n: number) => n + 1);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return (): void => { cancelAnimationFrame(frameRef.current); };
  }, []);

  const shapes: Shape[] = shapesRef.current;

  return (
    <div className="beaker-progress-container">
      <svg
        viewBox="0 0 100 120"
        className="beaker-svg"
        role="img"
        aria-label={`Upload progress: ${clampedProgress}%`}
      >
        <defs>
          <clipPath id="beaker-clip">
            <path d="M 25 21 L 25 104 Q 25 113 50 113 Q 75 113 75 104 L 75 21 Z" />
          </clipPath>

          {/* Neon bloom filter */}
          <filter id="neon-bloom" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* ── Black interior ── */}
        <rect x="0" y="0" width="100" height="120" fill="#000" clipPath="url(#beaker-clip)" />

        {/* ── Bouncing shapes + gradient trails ── */}
        <g clipPath="url(#beaker-clip)" filter="url(#neon-bloom)">
          {shapes.map((shape: Shape, si: number) => (
            <g key={si}>
              {/* Trail: oldest=faintest, newest=brightest */}
              {shape.trail.map((pt: TrailPoint, ti: number) => {
                const frac: number = (ti + 1) / TRAIL_LEN;
                return (
                  <polygon
                    key={ti}
                    points={makePoints(shape.type, shape.size * (0.4 + frac * 0.6))}
                    transform={`translate(${pt.x},${pt.y}) rotate(${pt.rotation})`}
                    fill="none"
                    stroke={shape.color}
                    strokeWidth={0.6 + frac * 0.7}
                    opacity={frac * 0.6}
                  />
                );
              })}
              {/* Current shape — full brightness */}
              <polygon
                points={makePoints(shape.type, shape.size)}
                transform={`translate(${shape.x},${shape.y}) rotate(${shape.rotation})`}
                fill="none"
                stroke={shape.color}
                strokeWidth="1.5"
                opacity="1"
              />
            </g>
          ))}
        </g>

        {/* ── Glass outline — neon pink ── */}
        <rect x="14" y="13" width="72" height="7" rx="1.5"
          fill="none" stroke="#ff10f0" strokeWidth="2.2" />
        <line x1="22" y1="20" x2="22" y2="106"
          stroke="#ff10f0" strokeWidth="2.2" strokeLinecap="round" />
        <line x1="78" y1="20" x2="78" y2="106"
          stroke="#ff10f0" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M 22 106 Q 22 116 50 116 Q 78 116 78 106"
          fill="none" stroke="#ff10f0" strokeWidth="2.2" strokeLinecap="round" />

        {/* Graduation marks */}
        <line x1="69" y1="38" x2="75" y2="38" stroke="#ff10f0" strokeWidth="1.2" opacity="0.5" />
        <line x1="69" y1="54" x2="75" y2="54" stroke="#ff10f0" strokeWidth="1.2" opacity="0.5" />
        <line x1="69" y1="70" x2="75" y2="70" stroke="#ff10f0" strokeWidth="1.2" opacity="0.5" />
        <line x1="69" y1="86" x2="75" y2="86" stroke="#ff10f0" strokeWidth="1.2" opacity="0.5" />

        {/* Glass shine */}
        <line x1="31" y1="23" x2="29" y2="99"
          stroke="white" strokeWidth="2" opacity="0.1" strokeLinecap="round" />
      </svg>

      <div className="beaker-progress-label">{clampedProgress}%</div>
    </div>
  );
};
