/**
 * LightningBorder — Animated lightning bolt that traces around hovered
 * interactive elements (buttons, links, inputs, etc.).
 *
 * Renders a full-screen canvas overlay. On hover of a qualifying element the
 * component generates a jagged bolt path that races around the element's
 * perimeter with a neon glow trail. The bolt colour is derived from the
 * element's `--hover-glow-color` CSS variable (set in index.css), falling back
 * to the default pink neon.
 */

import React, { useEffect, useRef, useCallback } from 'react';
import './LightningBorder.css';

/* ── Configurable knobs ── */
const BOLT_SPEED_PX: number = 300;       // pixels per second (constant regardless of element size)
const TRAIL_LENGTH_PX: number = 200;     // visible trail length in pixels
const SEGMENT_PX: number = 6;            // bolt sub-segment length in px
const JITTER_PX: number = 5;             // max perpendicular jitter for jagged bolt
const JITTER_REGEN_MS: number = 90;      // how often jitter offsets regenerate
const GLOW_BLUR: number = 14;            // canvas shadowBlur for neon
const BOLT_WIDTH: number = 2;            // base stroke width of the bolt
const PADDING: number = 3;               // px gap between element edge and bolt path
const FALLBACK_COLOR: string = '#ff10f0';

/* ── Selectors that qualify for the effect ── */
const HOVER_SELECTORS: string = [
  'button:not(:disabled)',
  'a',
  '.nav-link',
  '.dataset-checkbox',
  '.example-button:not(:disabled)',
  '.drop-zone',
  '.action-card',
  '.expand-indicator',
  '.dataset-expand-indicator',
  '.history-item-row',
  '.dataset-item',
  '.console-header',
  '.console-expand-indicator',
  'input:not(:disabled)',
  'textarea:not(:disabled)',
  'select:not(:disabled)',
].join(',');

/* ── Types ── */
interface BoltPoint {
  x: number;
  y: number;
}

interface HoverTarget {
  el: Element;
  rect: DOMRect;
  color: string;
  perimeter: number;
  jitterOffsets: number[];
  lastJitterTime: number;
}

/* ── Helpers ── */

/** Read the resolved --hover-glow-color from an element (or its ancestors). */
function resolveGlowColor(el: Element): string {
  const style: CSSStyleDeclaration = getComputedStyle(el);
  const raw: string = style.getPropertyValue('--hover-glow-color').trim();
  if (raw && raw !== '') return raw;
  return FALLBACK_COLOR;
}

/** Generate random jitter offsets for each segment around the perimeter. */
function generateJitter(segmentCount: number): number[] {
  const out: number[] = [];
  for (let i: number = 0; i < segmentCount; i++) {
    out.push((Math.random() - 0.5) * 2 * JITTER_PX);
  }
  return out;
}

/**
 * Given a progress value (0-1) around the perimeter return the (x, y) point
 * on the rect edge and the outward-facing normal.
 */
function perimeterPoint(
  rect: DOMRect,
  progress: number,
): { x: number; y: number; nx: number; ny: number } {
  const p: number = ((progress % 1) + 1) % 1;
  const w: number = rect.width + PADDING * 2;
  const h: number = rect.height + PADDING * 2;
  const perim: number = 2 * (w + h);
  const d: number = p * perim;

  const left: number = rect.left - PADDING;
  const top: number = rect.top - PADDING;

  if (d <= w) {
    // Top edge (left → right)
    return { x: left + d, y: top, nx: 0, ny: -1 };
  } else if (d <= w + h) {
    // Right edge (top → bottom)
    return { x: left + w, y: top + (d - w), nx: 1, ny: 0 };
  } else if (d <= 2 * w + h) {
    // Bottom edge (right → left)
    return { x: left + w - (d - w - h), y: top + h, nx: 0, ny: 1 };
  } else {
    // Left edge (bottom → top)
    return { x: left, y: top + h - (d - 2 * w - h), nx: -1, ny: 0 };
  }
}

/** Build the jagged bolt trail as an array of canvas points. */
function buildBoltPath(
  target: HoverTarget,
  headProgress: number,
): BoltPoint[] {
  const points: BoltPoint[] = [];
  const segCount: number = target.jitterOffsets.length;
  // Convert pixel trail length to a fraction of this element's perimeter
  const trailFraction: number = Math.min(TRAIL_LENGTH_PX / target.perimeter, 0.9);

  // Walk backwards from the head
  const steps: number = Math.max(4, Math.floor(trailFraction * segCount));
  for (let i: number = 0; i <= steps; i++) {
    const t: number = i / steps; // 0 = head, 1 = tail
    const prog: number = headProgress - t * trailFraction;
    const pt = perimeterPoint(target.rect, prog);

    // Apply jitter offset perpendicular to the edge
    const segIdx: number = Math.floor(((prog % 1 + 1) % 1) * segCount) % segCount;
    const jitter: number = target.jitterOffsets[segIdx] ?? 0;

    points.push({
      x: pt.x + pt.nx * jitter,
      y: pt.y + pt.ny * jitter,
    });
  }
  return points;
}

/* ── Component ── */

export const LightningBorder: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const targetRef = useRef<HoverTarget | null>(null);
  const rafRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  /** Determine if an element (or ancestor) matches our selectors. */
  const findQualifying = useCallback((el: Element | null): Element | null => {
    while (el) {
      if (el.matches && el.matches(HOVER_SELECTORS)) return el;
      el = el.parentElement;
    }
    return null;
  }, []);

  useEffect(() => {
    const canvas: HTMLCanvasElement | null = canvasRef.current;
    if (!canvas) return;

    const resize = (): void => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    /* ── Hover detection ── */
    const onEnter = (e: MouseEvent): void => {
      const el: Element | null = findQualifying(e.target as Element | null);
      if (!el) return;

      // If already tracking this element, don't restart the animation
      if (targetRef.current && targetRef.current.el === el) return;

      const rect: DOMRect = el.getBoundingClientRect();
      const w: number = rect.width + PADDING * 2;
      const h: number = rect.height + PADDING * 2;
      const perim: number = 2 * (w + h);
      const segCount: number = Math.max(4, Math.ceil(perim / SEGMENT_PX));
      const color: string = resolveGlowColor(el);

      targetRef.current = {
        el,
        rect,
        color,
        perimeter: perim,
        jitterOffsets: generateJitter(segCount),
        lastJitterTime: performance.now(),
      };
      // Start at a random perimeter offset so the bolt never always begins
      // at the top-left corner — it spawns at a different point each hover.
      startRef.current = performance.now() - Math.random() * (perim / BOLT_SPEED_PX) * 1000;
    };

    const onLeave = (e: MouseEvent): void => {
      const el: Element | null = findQualifying(e.target as Element | null);
      if (el && targetRef.current && targetRef.current.el === el) {
        // If the mouse is moving to a child (or another element) still inside
        // the same qualifying container, don't clear — the bolt stays.
        const dest: Element | null = findQualifying(e.relatedTarget as Element | null);
        if (dest === el) return;
        targetRef.current = null;
      }
    };

    // Use capture so we catch events before children swallow them
    document.addEventListener('mouseenter', onEnter, true);
    document.addEventListener('mouseleave', onLeave, true);
    // Also track mouseover/mouseout for more reliable detection
    document.addEventListener('mouseover', onEnter, true);
    document.addEventListener('mouseout', onLeave, true);

    /* ── Render loop ── */
    const draw = (): void => {
      const ctx: CanvasRenderingContext2D | null = canvas.getContext('2d');
      if (!ctx) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const target: HoverTarget | null = targetRef.current;
      if (target) {
        // Drop the target if it no longer qualifies (e.g. became disabled)
        if (!target.el.matches(HOVER_SELECTORS)) {
          targetRef.current = null;
          rafRef.current = requestAnimationFrame(draw);
          return;
        }

        const now: number = performance.now();

        // Refresh rect in case of scroll / layout shift
        target.rect = target.el.getBoundingClientRect();
        // Re-resolve color (it may change as CSS vars shift)
        target.color = resolveGlowColor(target.el);

        // Regenerate jitter for a live-wire look
        if (now - target.lastJitterTime > JITTER_REGEN_MS) {
          target.jitterOffsets = generateJitter(target.jitterOffsets.length);
          target.lastJitterTime = now;
        }

        // Head progress (0-1 wrapping) — constant px/sec regardless of element size
        const elapsed: number = (now - startRef.current) / 1000;
        const pxTravelled: number = elapsed * BOLT_SPEED_PX;
        const headProgress: number = (pxTravelled / target.perimeter) % 1;

        // Build the bolt path
        const path: BoltPoint[] = buildBoltPath(target, headProgress);

        // Draw the bolt segments with fading trail
        if (path.length >= 2) {
          for (let i: number = 0; i < path.length - 1; i++) {
            const t: number = i / (path.length - 1); // 0 = head, 1 = tail
            const alpha: number = 1 - t;

            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.strokeStyle = target.color;
            ctx.lineWidth = BOLT_WIDTH * (1 - t * 0.5);
            ctx.shadowBlur = GLOW_BLUR * (1 - t * 0.6);
            ctx.shadowColor = target.color;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.beginPath();
            ctx.moveTo(path[i]!.x, path[i]!.y);
            ctx.lineTo(path[i + 1]!.x, path[i + 1]!.y);
            ctx.stroke();
            ctx.restore();
          }

          // Extra bright head dot
          ctx.save();
          ctx.globalAlpha = 1;
          ctx.fillStyle = '#ffffff';
          ctx.shadowBlur = GLOW_BLUR * 2;
          ctx.shadowColor = target.color;
          ctx.beginPath();
          ctx.arc(path[0]!.x, path[0]!.y, 2.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();

          // Second glow pass for intensity
          ctx.save();
          ctx.globalAlpha = 0.4;
          ctx.strokeStyle = target.color;
          ctx.lineWidth = BOLT_WIDTH * 2.5;
          ctx.shadowBlur = GLOW_BLUR * 2.5;
          ctx.shadowColor = target.color;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';
          ctx.beginPath();
          ctx.moveTo(path[0]!.x, path[0]!.y);
          for (let i: number = 1; i < Math.min(path.length, Math.floor(path.length * 0.3)); i++) {
            ctx.lineTo(path[i]!.x, path[i]!.y);
          }
          ctx.stroke();
          ctx.restore();
        }
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return (): void => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
      document.removeEventListener('mouseenter', onEnter, true);
      document.removeEventListener('mouseleave', onLeave, true);
      document.removeEventListener('mouseover', onEnter, true);
      document.removeEventListener('mouseout', onLeave, true);
    };
  }, [findQualifying]);

  return <canvas ref={canvasRef} className="lightning-border-canvas" />;
};
