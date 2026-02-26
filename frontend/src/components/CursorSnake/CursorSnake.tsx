/**
 * CursorSnake — Geometric neon hexagon chain that follows the cursor.
 *
 * Uses a spring/lerp chain: each node continuously interpolates toward the
 * node ahead of it (node[0] interpolates toward the mouse). When the mouse
 * is idle the entire chain catches up and converges to a single glowing
 * hexagon at the cursor — no stagnant trail.
 */

import React, { useEffect, useRef } from 'react';
import './CursorSnake.css';

interface Point {
  x: number;
  y: number;
}

const CHAIN_LENGTH: number = 14;
const HEAD_RADIUS: number = 9;
const TAIL_RADIUS: number = 1;
const HEAD_LERP: number = 0.18;   // how fast node[0] chases the mouse
const NODE_LERP: number = 0.30;   // how fast each node chases the one ahead
const MIN_SEG_DIST: number = 1.5; // skip drawing segments shorter than this (px)
const SHADOW_BLUR: number = 14;

const NEON_COLORS: readonly string[] = [
  '#ff10f0', // pink
  '#00eeff', // cyan
  '#ff6600', // orange
  '#39ff14', // green
  '#ffd700', // gold
];

const OFF_SCREEN: number = -2000;

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

function drawCrosshair(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r: number,
  rotation: number,
  color: string,
): void {
  const armLength: number = r * 1.6;
  const gapRadius: number = r * 0.3;

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(rotation);

  // Draw 4 crosshair arms with gap in center
  ctx.beginPath();
  for (let i: number = 0; i < 4; i++) {
    const angle: number = (Math.PI / 2) * i;
    const cos: number = Math.cos(angle);
    const sin: number = Math.sin(angle);
    ctx.moveTo(cos * gapRadius, sin * gapRadius);
    ctx.lineTo(cos * armLength, sin * armLength);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.shadowBlur = SHADOW_BLUR * 2;
  ctx.shadowColor = color;
  ctx.stroke();

  // Inner glow layer for extra neon intensity
  ctx.shadowBlur = SHADOW_BLUR * 3;
  ctx.shadowColor = color;
  ctx.globalAlpha = 0.5;
  ctx.stroke();

  // Small center dot
  ctx.globalAlpha = 1;
  ctx.beginPath();
  ctx.arc(0, 0, 1.5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.shadowBlur = SHADOW_BLUR * 2;
  ctx.shadowColor = color;
  ctx.fill();

  ctx.restore();
}

export const CursorSnake: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mousePosRef = useRef<Point>({ x: OFF_SCREEN, y: OFF_SCREEN });
  const nodesRef = useRef<Point[]>(
    Array.from({ length: CHAIN_LENGTH }, (): Point => ({ x: OFF_SCREEN, y: OFF_SCREEN }))
  );
  const rafRef = useRef<number>(0);
  const frameRef = useRef<number>(0);
  const colorIdxRef = useRef<number>(0);
  const prevHeadRef = useRef<Point>({ x: OFF_SCREEN, y: OFF_SCREEN });
  const mouseSeenRef = useRef<boolean>(false);

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
      mousePosRef.current = { x: e.clientX, y: e.clientY };
      if (!mouseSeenRef.current) {
        // Snap all nodes to cursor on first sighting to avoid fly-in from off-screen
        for (const node of nodesRef.current) {
          node.x = e.clientX;
          node.y = e.clientY;
        }
        prevHeadRef.current = { x: e.clientX, y: e.clientY };
        mouseSeenRef.current = true;
      }
    };

    window.addEventListener('mousemove', onMove);

    const draw = (): void => {
      const ctx: CanvasRenderingContext2D | null = canvas.getContext('2d');
      if (!ctx) { rafRef.current = requestAnimationFrame(draw); return; }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!mouseSeenRef.current) { rafRef.current = requestAnimationFrame(draw); return; }

      // ── 1. Update node positions via lerp ──
      const mouse: Point = mousePosRef.current;
      const nodes: Point[] = nodesRef.current;

      nodes[0]!.x += (mouse.x - nodes[0]!.x) * HEAD_LERP;
      nodes[0]!.y += (mouse.y - nodes[0]!.y) * HEAD_LERP;

      for (let i: number = 1; i < CHAIN_LENGTH; i++) {
        nodes[i]!.x += (nodes[i - 1]!.x - nodes[i]!.x) * NODE_LERP;
        nodes[i]!.y += (nodes[i - 1]!.y - nodes[i]!.y) * NODE_LERP;
      }

      // ── 2. Advance color based on how much the head moved this frame ──
      const hdx: number = nodes[0]!.x - prevHeadRef.current.x;
      const hdy: number = nodes[0]!.y - prevHeadRef.current.y;
      const headDist: number = Math.sqrt(hdx * hdx + hdy * hdy);
      colorIdxRef.current = (colorIdxRef.current + headDist * 0.004) % NEON_COLORS.length;
      prevHeadRef.current = { x: nodes[0]!.x, y: nodes[0]!.y };

      frameRef.current += 1;

      // ── 3. Build visible node list (skip nodes that haven't separated enough) ──
      const visible: number[] = [0];
      for (let i: number = 1; i < CHAIN_LENGTH; i++) {
        const prev: number = visible[visible.length - 1]!;
        const dx: number = nodes[i]!.x - nodes[prev]!.x;
        const dy: number = nodes[i]!.y - nodes[prev]!.y;
        if (Math.sqrt(dx * dx + dy * dy) >= MIN_SEG_DIST) {
          visible.push(i);
        }
      }

      const count: number = visible.length;
      const baseColorIdx: number = Math.floor(colorIdxRef.current) % NEON_COLORS.length;
      const headColor: string = NEON_COLORS[baseColorIdx] ?? '#ff10f0';

      // ── 4. Draw connecting lines ──
      for (let vi: number = 0; vi < count - 1; vi++) {
        const i: number = visible[vi]!;
        const j: number = visible[vi + 1]!;
        const t: number = vi / Math.max(count - 1, 1);
        const segColorIdx: number = (baseColorIdx + Math.floor(vi / 5)) % NEON_COLORS.length;
        const segColor: string = NEON_COLORS[segColorIdx] ?? headColor;

        ctx.save();
        ctx.globalAlpha = (1 - t) * 0.55;
        ctx.strokeStyle = segColor;
        ctx.lineWidth = Math.max(0.4, (1 - t) * 1.5);
        ctx.shadowBlur = SHADOW_BLUR * (1 - t);
        ctx.shadowColor = segColor;
        ctx.beginPath();
        ctx.moveTo(nodes[i]!.x, nodes[i]!.y);
        ctx.lineTo(nodes[j]!.x, nodes[j]!.y);
        ctx.stroke();
        ctx.restore();
      }

      // ── 5. Draw head crosshair ──
      if (count > 0) {
        const headNodeIdx: number = visible[0]!;
        const headRotation: number = frameRef.current * 0.03;
        drawCrosshair(
          ctx,
          nodes[headNodeIdx]!.x,
          nodes[headNodeIdx]!.y,
          HEAD_RADIUS,
          headRotation,
          headColor,
        );
      }

      // ── 6. Draw tail hexagons (skip head) ──
      for (let vi: number = 1; vi < count; vi++) {
        const i: number = visible[vi]!;
        const t: number = vi / Math.max(count - 1, 1);
        const alpha: number = 1 - t;
        const r: number = TAIL_RADIUS + (HEAD_RADIUS - TAIL_RADIUS) * (1 - t);
        const segColorIdx: number = (baseColorIdx + Math.floor(vi / 5)) % NEON_COLORS.length;
        const segColor: string = NEON_COLORS[segColorIdx] ?? headColor;
        const rotation: number = frameRef.current * 0.015 * (1 - t * 0.7);

        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = segColor;
        ctx.lineWidth = Math.max(0.4, (1 - t) * 1.5);
        ctx.shadowBlur = SHADOW_BLUR * (1 - t * 0.8);
        ctx.shadowColor = segColor;
        hexagonPath(ctx, nodes[i]!.x, nodes[i]!.y, r, rotation);
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
