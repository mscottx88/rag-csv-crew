/**
 * ProcessProgress Component
 * A wireframe data table with rows filling in one by one — each cell receives
 * a random value as a "cursor" moves across the grid. Completed rows flash cyan.
 * Represents the "processing result rows" phase.
 * Color: cyan (#00eeff)
 */

import React, { useEffect, useRef, useState } from 'react';
import './ProcessProgress.css';

interface ProcessProgressProps {
  label?: string;
}

const COLOR: string = '#00eeff';
const COLS: number = 4;
const ROWS: number = 5;

// Table layout
const TBL_LEFT: number = 8;
const TBL_TOP: number = 12;
const CELL_W: number = 21;
const CELL_H: number = 16;
const TBL_RIGHT: number = TBL_LEFT + COLS * CELL_W;
const TBL_BOT: number = TBL_TOP + ROWS * CELL_H;

// Column header labels
const HEADERS: readonly string[] = ['ID', 'NAME', 'VAL', 'SUM'];

// Pool of random cell values
const VALUES: readonly string[] = [
  '147', 'ABC', '3.14', '988', 'XYZ', '0.72', '521',
  'DEF', '12.5', '007', 'GHI', '8.01', '404', 'JKL',
];

function randVal(): string {
  return VALUES[Math.floor(Math.random() * VALUES.length)] ?? '?';
}

interface CellData {
  value: string;
  filled: boolean;
  flash: number; // 1=just filled, fades to 0
}

export const ProcessProgress: React.FC<ProcessProgressProps> = ({ label = 'Processing...' }) => {
  // Current cursor position (advances through cells row by row)
  const cursorRef = useRef<number>(0); // 0 to COLS*ROWS-1
  const cellsRef = useRef<CellData[]>(
    Array.from({ length: COLS * ROWS }, (): CellData => ({ value: '', filled: false, flash: 0 }))
  );
  const tickCountRef = useRef<number>(0);
  const rafRef = useRef<number>(0);
  const [, tick] = useState<number>(0);

  useEffect(() => {
    const loop = (): void => {
      tickCountRef.current += 1;

      // Decay flash values
      cellsRef.current = cellsRef.current.map((c: CellData): CellData =>
        c.flash > 0 ? { ...c, flash: c.flash - 0.035 } : c
      );

      // Advance cursor every ~18 frames
      if (tickCountRef.current % 18 === 0) {
        const idx: number = cursorRef.current;
        const updated: CellData[] = [...cellsRef.current];
        updated[idx] = { value: randVal(), filled: true, flash: 1 };
        cellsRef.current = updated;
        cursorRef.current = (idx + 1) % (COLS * ROWS);

        // When we wrap around, reset all cells for a fresh pass
        if (cursorRef.current === 0) {
          cellsRef.current = Array.from(
            { length: COLS * ROWS },
            (): CellData => ({ value: '', filled: false, flash: 0 })
          );
        }
      }

      tick((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const cells: CellData[] = cellsRef.current;
  const cursor: number = cursorRef.current;

  return (
    <div className="process-progress-container">
      <svg viewBox="0 0 100 115" className="process-svg" role="img" aria-label="Processing result rows">
        <defs>
          <filter id="proc-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="0" y="0" width="100" height="115" fill="#000" />

        <g filter="url(#proc-bloom)">
          {/* Column headers */}
          {HEADERS.map((h: string, ci: number) => {
            const cx: number = TBL_LEFT + ci * CELL_W + CELL_W / 2;
            return (
              <g key={ci}>
                <rect
                  x={TBL_LEFT + ci * CELL_W} y={TBL_TOP - CELL_H}
                  width={CELL_W} height={CELL_H}
                  fill="rgba(0,238,255,0.12)" stroke={COLOR} strokeWidth="0.7"
                />
                <text x={cx} y={TBL_TOP - CELL_H / 2}
                  fontFamily="'Courier New', Courier, monospace"
                  fontSize="4" fill={COLOR} textAnchor="middle" dominantBaseline="middle"
                  fontWeight="bold"
                >
                  {h}
                </text>
              </g>
            );
          })}

          {/* Data cells */}
          {Array.from({ length: ROWS }, (_: unknown, ri: number) =>
            Array.from({ length: COLS }, (_2: unknown, ci: number) => {
              const idx: number = ri * COLS + ci;
              const cell: CellData = cells[idx]!;
              const isCursor: boolean = idx === cursor;
              const cx: number = TBL_LEFT + ci * CELL_W + CELL_W / 2;
              const cy: number = TBL_TOP + ri * CELL_H + CELL_H / 2;
              const flashAlpha: number = Math.max(0, cell.flash);

              return (
                <g key={idx}>
                  {/* Cell background */}
                  <rect
                    x={TBL_LEFT + ci * CELL_W} y={TBL_TOP + ri * CELL_H}
                    width={CELL_W} height={CELL_H}
                    fill={
                      isCursor
                        ? `rgba(0,238,255,0.18)`
                        : flashAlpha > 0
                          ? `rgba(0,238,255,${flashAlpha * 0.15})`
                          : 'rgba(0,0,0,0)'
                    }
                    stroke={COLOR}
                    strokeWidth={isCursor ? 1 : 0.5}
                    opacity={isCursor ? 1 : 0.3}
                  />
                  {/* Cell value */}
                  {cell.filled && (
                    <text
                      x={cx} y={cy}
                      fontFamily="'Courier New', Courier, monospace"
                      fontSize="3.6"
                      fill={COLOR}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      opacity={0.5 + flashAlpha * 0.5}
                    >
                      {cell.value}
                    </text>
                  )}
                  {/* Cursor blink */}
                  {isCursor && (
                    <rect
                      x={cx - 0.6} y={cy - 4}
                      width="1.2" height="7"
                      fill={COLOR}
                      opacity="0.9"
                    />
                  )}
                </g>
              );
            })
          )}

          {/* Row count label below table */}
          <text
            x={TBL_LEFT + (TBL_RIGHT - TBL_LEFT) / 2} y={TBL_BOT + 9}
            fontFamily="'Courier New', Courier, monospace"
            fontSize="3.8" fill={COLOR} textAnchor="middle" opacity="0.4"
          >
            {cursor} rows processed
          </text>
        </g>
      </svg>
      <div className="process-progress-label">{label}</div>
    </div>
  );
};
