/**
 * Funnel Progress Component
 * Animated SVG funnel — neon pink particles stream down and accelerate
 * through the narrowing funnel on a black background.
 */

import React, { useEffect, useRef, useState } from 'react';
import './FunnelProgress.css';

interface FunnelProgressProps {
  label?: string;
}

interface Particle {
  xFrac: number;  // 0–1 relative horizontal position within funnel width at current y
  progress: number;  // 0–1 down the funnel
  speed: number;  // base speed (progress units per frame)
  size: number;
  color: string;
  opacity: number;
}

// Funnel geometry (SVG viewBox 0 0 100 115)
const TOP_LEFT_X: number = 10;
const TOP_RIGHT_X: number = 90;
const BOT_LEFT_X: number = 45;
const BOT_RIGHT_X: number = 55;
const FUNNEL_TOP_Y: number = 18;
const FUNNEL_BOT_Y: number = 90;

const PARTICLE_COLORS: readonly string[] = [
  '#ff6600', '#ff4500', '#ff8c00', '#ffa500', '#ff7700',
];

const MAX_PARTICLES: number = 28;

function makeParticle(): Particle {
  return {
    xFrac: Math.random(),
    progress: Math.random() * 0.3, // stagger initial positions
    speed: 0.004 + Math.random() * 0.004,
    size: 1.8 + Math.random() * 2.4,
    color: PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)] ?? '#ff6600',
    opacity: 0.7 + Math.random() * 0.3,
  };
}

/** Interpolate funnel x-bounds at a given progress (0=top, 1=bottom) */
function funnelBoundsAtProgress(progress: number): { leftX: number; rightX: number } {
  const leftX: number = TOP_LEFT_X + (BOT_LEFT_X - TOP_LEFT_X) * progress;
  const rightX: number = TOP_RIGHT_X + (BOT_RIGHT_X - TOP_RIGHT_X) * progress;
  return { leftX, rightX };
}

/** Convert particle state to SVG coordinates */
function particleToSVG(p: Particle): { cx: number; cy: number } {
  const { leftX, rightX } = funnelBoundsAtProgress(p.progress);
  const cx: number = leftX + (rightX - leftX) * p.xFrac;
  const cy: number = FUNNEL_TOP_Y + (FUNNEL_BOT_Y - FUNNEL_TOP_Y) * p.progress;
  return { cx, cy };
}

function stepParticles(particles: Particle[]): Particle[] {
  return particles.map((p: Particle): Particle => {
    // Accelerate as funnel narrows (narrower = faster)
    const accel: number = 1 + p.progress * 3.5;
    const newProgress: number = p.progress + p.speed * accel;

    if (newProgress >= 1.05) {
      // Respawn at top
      return makeParticle();
    }

    // Nudge xFrac toward center as funnel narrows (particles get squeezed)
    const squeeze: number = 0.012;
    const newXFrac: number = p.xFrac + (0.5 - p.xFrac) * squeeze;

    return { ...p, progress: newProgress, xFrac: newXFrac };
  });
}

export const FunnelProgress: React.FC<FunnelProgressProps> = ({ label = 'Processing...' }) => {
  const particlesRef = useRef<Particle[]>(
    Array.from({ length: MAX_PARTICLES }, (): Particle => makeParticle())
  );
  const frameRef = useRef<number>(0);
  const [, forceUpdate] = useState<number>(0);

  useEffect(() => {
    const tick = (): void => {
      particlesRef.current = stepParticles(particlesRef.current);
      forceUpdate((n: number) => n + 1);
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return (): void => { cancelAnimationFrame(frameRef.current); };
  }, []);

  const particles: Particle[] = particlesRef.current;

  // Funnel polygon points (trapezoid outline)
  const funnelPoints: string =
    `${TOP_LEFT_X},${FUNNEL_TOP_Y} ${TOP_RIGHT_X},${FUNNEL_TOP_Y} ` +
    `${BOT_RIGHT_X},${FUNNEL_BOT_Y} ${BOT_LEFT_X},${FUNNEL_BOT_Y}`;

  // Spout rectangle below funnel
  const spoutX: number = BOT_LEFT_X;
  const spoutW: number = BOT_RIGHT_X - BOT_LEFT_X;
  const spoutTopY: number = FUNNEL_BOT_Y;
  const spoutBotY: number = 106;

  const clipId: string = 'funnel-clip';

  return (
    <div className="funnel-progress-container">
      <svg
        viewBox="0 0 100 115"
        className="funnel-svg"
        role="img"
        aria-label="Processing data"
      >
        <defs>
          {/* Clip to funnel + spout area */}
          <clipPath id={clipId}>
            <polygon points={funnelPoints} />
            <rect x={spoutX} y={spoutTopY} width={spoutW} height={spoutBotY - spoutTopY} />
          </clipPath>

          {/* Neon bloom filter */}
          <filter id="funnel-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Black background inside funnel */}
        <polygon points={funnelPoints} fill="#000" />
        <rect x={spoutX} y={spoutTopY} width={spoutW} height={spoutBotY - spoutTopY} fill="#000" />

        {/* Particles */}
        <g clipPath={`url(#${clipId})`} filter="url(#funnel-bloom)">
          {particles.map((p: Particle, i: number) => {
            const { cx, cy } = particleToSVG(p);
            return (
              <circle
                key={i}
                cx={cx}
                cy={cy}
                r={p.size * (0.5 + p.progress * 0.7)}
                fill={p.color}
                opacity={p.opacity * (1 - p.progress * 0.3)}
              />
            );
          })}
        </g>

        {/* Funnel glass outline — neon pink */}
        <polygon
          points={funnelPoints}
          fill="none"
          stroke="#ff6600"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {/* Spout sides */}
        <line
          x1={BOT_LEFT_X} y1={FUNNEL_BOT_Y}
          x2={BOT_LEFT_X} y2={spoutBotY}
          stroke="#ff6600" strokeWidth="2" strokeLinecap="round"
        />
        <line
          x1={BOT_RIGHT_X} y1={FUNNEL_BOT_Y}
          x2={BOT_RIGHT_X} y2={spoutBotY}
          stroke="#ff6600" strokeWidth="2" strokeLinecap="round"
        />
        {/* Spout bottom opening */}
        <line
          x1={BOT_LEFT_X} y1={spoutBotY}
          x2={BOT_RIGHT_X} y2={spoutBotY}
          stroke="#ff6600" strokeWidth="2" strokeLinecap="round"
        />

        {/* Funnel rim (top horizontal bar) */}
        <line
          x1={TOP_LEFT_X - 4} y1={FUNNEL_TOP_Y}
          x2={TOP_RIGHT_X + 4} y2={FUNNEL_TOP_Y}
          stroke="#ff6600" strokeWidth="2.2" strokeLinecap="round"
        />

        {/* Glass shine */}
        <line
          x1={TOP_LEFT_X + 5} y1={FUNNEL_TOP_Y + 2}
          x2={BOT_LEFT_X + 2} y2={FUNNEL_BOT_Y - 4}
          stroke="white" strokeWidth="1.5" opacity="0.08" strokeLinecap="round"
        />
      </svg>
      <div className="funnel-progress-label">{label}</div>
    </div>
  );
};
