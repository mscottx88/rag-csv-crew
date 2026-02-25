/**
 * CursorSnake — Geometric neon hexagon chain that follows the cursor.
 *
 * A fixed full-viewport canvas overlay (pointer-events: none) renders a
 * connected chain of hexagons whose size, opacity, and colour fade from
 * head to tail, giving the illusion of a glowing wireframe snake.
 */

import React, { useEffect, useRef } from 'react';
import './CursorSnake.css';

interface Point {
  x: number;
  y: number;
}

const CHAIN_LENGTH: number = 32;
const HEAD_RADIUS: number = 7;
const TAIL_RADIUS: number = 1;
const NEON_COLORS: readonly string[] = [
  '#ff10f0', // pink
  '#00eeff', // cyan
  '#ff6600', // orange
  '#39ff14', // green
  '#ffd700', // gold
];
const SHADOW_BLUR: number = 14;
const FRAME_SKIP: number = 2; // sample cursor every N pixels of movement

function hexagonPath(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  rotation: number,
): void {
  ctx.beginPath();
  for (let i: number = 0; i < 6; i++) {
    const angle: number = (Math.PI / 3) * i + rotation;
    const x: number = cx + r * Math.cos(angle);
    const y: number = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

export const CursorSnake: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointsRef = useRef<Point[]>([]);
  const rafRef = useRef<number>(0);
  const lastRef = useRef<Point>({ x: -999, y: -999 });
  const frameRef = useRef<number>(0);
  const colorIdxRef = useRef<number>(0);

  useEffect(() => {
    const canvas: HTMLCanvasElement | null = canvasRef.current;
    if (!canvas) return;

    const resize = (): void => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const onMove = (e: MouseEvent): void => {
      const cur: Point = { x: e.clientX, y: e.clientY };
      const last: Point = lastRef.current;
      const dx: number = cur.x - last.x;
      const dy: number = cur.y - last.y;
      const dist: number = Math.sqrt(dx * dx + dy * dy);

      if (dist < FRAME_SKIP) return;

      // Advance color index slowly as the snake moves
      colorIdxRef.current = (colorIdxRef.current + 0.04) % NEON_COLORS.length;

      pointsRef.current = [cur, ...pointsRef.current].slice(0, CHAIN_LENGTH);
      lastRef.current = cur;
    };

    window.addEventListener('mousemove', onMove);

    const draw = (): void => {
      const ctx: CanvasRenderingContext2D | null = canvas.getContext('2d');
      if (!ctx) { rafRef.current = requestAnimationFrame(draw); return; }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const points: Point[] = pointsRef.current;
      const count: number = points.length;
      if (count < 2) { rafRef.current = requestAnimationFrame(draw); return; }

      frameRef.current += 1;

      const baseColorIdx: number = Math.floor(colorIdxRef.current) % NEON_COLORS.length;
      const headColor: string = NEON_COLORS[baseColorIdx] ?? '#ff10f0';

      // Draw connecting lines first (below hexagons)
      for (let i: number = 0; i < count - 1; i++) {
        const t: number = i / (count - 1);
        const alpha: number = (1 - t) * 0.6;
        const segColorIdx: number = (baseColorIdx + Math.floor(i / 6)) % NEON_COLORS.length;
        const segColor: string = NEON_COLORS[segColorIdx] ?? headColor;

        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = segColor;
        ctx.lineWidth = Math.max(0.5, (1 - t) * 1.5);
        ctx.shadowBlur = SHADOW_BLUR * (1 - t);
        ctx.shadowColor = segColor;
        ctx.beginPath();
        ctx.moveTo(points[i]!.x, points[i]!.y);
        ctx.lineTo(points[i + 1]!.x, points[i + 1]!.y);
        ctx.stroke();
        ctx.restore();
      }

      // Draw hexagons (head → tail)
      for (let i: number = 0; i < count; i++) {
        const t: number = i / (count - 1);
        const alpha: number = 1 - t;
        const r: number = TAIL_RADIUS + (HEAD_RADIUS - TAIL_RADIUS) * (1 - t);
        const segColorIdx: number = (baseColorIdx + Math.floor(i / 6)) % NEON_COLORS.length;
        const segColor: string = NEON_COLORS[segColorIdx] ?? headColor;
        // Rotate hexagons slowly over time, faster at head
        const rotation: number = (frameRef.current * 0.015) * (1 - t * 0.7);

        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = segColor;
        ctx.lineWidth = Math.max(0.5, (1 - t) * 1.5);
        ctx.shadowBlur = SHADOW_BLUR * (1 - t * 0.8);
        ctx.shadowColor = segColor;
        hexagonPath(ctx, points[i]!.x, points[i]!.y, r, rotation);
        ctx.stroke();
        ctx.restore();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return (): void => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="cursor-snake-canvas" />;
};
