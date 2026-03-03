/**
 * CRTTerminal — Realistic 3D CRT computer terminal for the Query card.
 * Inspired by the IBM 3278 / VT100 terminal. Semi-transparent solid
 * neon cyan (#00eeff) with Bloom glow.
 *
 * Features: chunky CRT monitor housing with tapered rear, convex screen
 * with split-pane display (SQL editor, bar chart, data table), scan-line
 * sweep, front bezel with brand badge and adjustment knobs, keyboard with
 * visible key grid, tilt-bracket stand with swivel base, power LED.
 *
 * SQL "words" are rendered as filled rectangle meshes (not thin line
 * segments) for legibility.  Screen content is positioned in front of
 * the CRT glass bulge so nothing draws over the text.
 *
 * When hovered: SQL words appear one-by-one in the left pane,
 * bar chart bars grow upward in the top-right pane, and data table rows
 * fill in the bottom-right pane. When idle: all content faintly visible.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const CYAN = '#00eeff';

/* ── Monitor dimensions ── */
const BZL_W = 2.0;   // bezel width
const BZL_H = 1.6;   // bezel height
const SCR_W = 1.6;    // screen width
const SCR_H = 1.2;    // screen height
const HSG_D = 1.2;    // housing depth

/* ── Keyboard ── */
const KB_W = 2.4;
const KB_H = 0.12;
const KB_D = 0.8;

/* ── Screen pane layout (in screen-local coords, origin = screen center) ── */
const SPLIT_X = -0.05;            // vertical divider x position (slightly left of center)
const SPLIT_Y = 0.05;             // horizontal divider y on right pane
const PANE_PAD = 0.04;            // padding inside panes

/* ── SQL content ── */
const SQL_LINES = [
  [0.52, 0.18, 0.22],                 // SELECT col1, col2
  [0.28, 0.35],                        // FROM datasets
  [0.32, 0.22, 0.1, 0.24],            // WHERE status = 'active'
  [0.32, 0.12, 0.18],                  // GROUP BY col1
  [0.32, 0.12, 0.18, 0.28],           // ORDER BY col2 DESC
  [0.3, 0.2],                          // LIMIT 100;
];
const SQL_TOTAL_SEGS = SQL_LINES.reduce((a, l) => a + l.length, 0);
const SQL_WORD_H = 0.05;              // height of each filled word rectangle

/* ── Chart bars ── */
const BAR_COUNT = 5;
const BAR_HEIGHTS = [0.7, 0.45, 0.85, 0.3, 0.6]; // normalised target heights

/* ── Table grid ── */
const TABLE_ROWS = 4;
const TABLE_COLS = 3;

interface CRTTerminalProps {
  hovered: boolean;
}

/** Circle outline in XZ plane at height y. */
function circleXZ(radius: number, y: number, segs = 24): number[] {
  const v: number[] = [];
  for (let i = 0; i < segs; i++) {
    const a0 = (i / segs) * Math.PI * 2;
    const a1 = ((i + 1) / segs) * Math.PI * 2;
    v.push(
      Math.cos(a0) * radius, y, Math.sin(a0) * radius,
      Math.cos(a1) * radius, y, Math.sin(a1) * radius,
    );
  }
  return v;
}

export const CRTTerminal: React.FC<CRTTerminalProps> = ({ hovered }) => {
  const groupRef = useRef<THREE.Group>(null);
  const sqlWordsRef = useRef<THREE.Group>(null);
  const cursorRef = useRef<THREE.Mesh>(null);
  const scanRef = useRef<THREE.LineSegments>(null);
  const ledRef = useRef<THREE.Mesh>(null);
  const barsRef = useRef<THREE.Group>(null);
  const tableRowsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);
  const hoverTimeRef = useRef(0);

  /* ── Edge outlines ── */
  const housingEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(BZL_W, BZL_H, HSG_D);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const baseEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(2.2, 0.06, 1.0);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const kbEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(KB_W, KB_H, KB_D);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── CRT taper lines (front-wide → rear-narrow) ── */
  const taperGeo = useMemo(() => {
    const v: number[] = [];
    const fw = BZL_W / 2;
    const fh = BZL_H / 2;
    const rw = 0.7;
    const rh = 0.55;
    const fz = HSG_D / 2;
    const rz = -HSG_D / 2;

    v.push(fw, fh, fz, rw, rh, rz);
    v.push(-fw, fh, fz, -rw, rh, rz);
    v.push(fw, -fh, fz, rw, -rh, rz);
    v.push(-fw, -fh, fz, -rw, -rh, rz);

    v.push(-rw, -rh, rz, rw, -rh, rz);
    v.push(-rw, rh, rz, rw, rh, rz);
    v.push(-rw, -rh, rz, -rw, rh, rz);
    v.push(rw, -rh, rz, rw, rh, rz);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Front bezel panel lines ── */
  const panelGeo = useMemo(() => {
    const v: number[] = [];
    const fz = HSG_D / 2 + 0.01;
    const bx = BZL_W / 2;
    const by = BZL_H / 2;
    const sx = SCR_W / 2;
    const sy = SCR_H / 2;

    // Outer bezel frame
    v.push(-bx, -by, fz, bx, -by, fz);
    v.push(-bx, by, fz, bx, by, fz);
    v.push(-bx, -by, fz, -bx, by, fz);
    v.push(bx, -by, fz, bx, by, fz);

    // Inner screen frame
    v.push(-sx, -sy, fz, sx, -sy, fz);
    v.push(-sx, sy, fz, sx, sy, fz);
    v.push(-sx, -sy, fz, -sx, sy, fz);
    v.push(sx, -sy, fz, sx, sy, fz);

    // Below-screen control strip
    const stripY = -by + 0.08;
    v.push(-bx + 0.06, stripY, fz, bx - 0.06, stripY, fz);

    // Brand badge rectangle
    const badgeCy = (-by + stripY) / 2;
    const badgeHW = 0.18;
    const badgeHH = 0.04;
    v.push(-badgeHW, badgeCy - badgeHH, fz, badgeHW, badgeCy - badgeHH, fz);
    v.push(-badgeHW, badgeCy + badgeHH, fz, badgeHW, badgeCy + badgeHH, fz);
    v.push(-badgeHW, badgeCy - badgeHH, fz, -badgeHW, badgeCy + badgeHH, fz);
    v.push(badgeHW, badgeCy - badgeHH, fz, badgeHW, badgeCy + badgeHH, fz);

    // Adjustment knob circles
    for (const kx of [0.55, 0.75]) {
      const kr = 0.04;
      const ky = badgeCy;
      for (let i = 0; i < 10; i++) {
        const a0 = (i / 10) * Math.PI * 2;
        const a1 = ((i + 1) / 10) * Math.PI * 2;
        v.push(
          kx + Math.cos(a0) * kr, ky + Math.sin(a0) * kr, fz,
          kx + Math.cos(a1) * kr, ky + Math.sin(a1) * kr, fz,
        );
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Rear ventilation lines ── */
  const rearVentsGeo = useMemo(() => {
    const v: number[] = [];
    const rz = -HSG_D / 2 - 0.01;
    const hw = 0.6;
    for (let i = 0; i < 6; i++) {
      const y = -0.3 + i * 0.16;
      v.push(-hw, y, rz, hw, y, rz);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Keyboard key grid ── */
  const keyGridGeo = useMemo(() => {
    const v: number[] = [];
    const ky = KB_H / 2 + 0.005;
    const gw = KB_W - 0.4;
    const gd = KB_D - 0.2;
    const rows = 5;
    const cols = 15;
    const x0 = -gw / 2;
    const z0 = -gd / 2;

    for (let r = 0; r <= rows; r++) {
      const z = z0 + (r / rows) * gd;
      v.push(x0, ky, z, x0 + gw, ky, z);
    }
    for (let c = 0; c <= cols; c++) {
      const x = x0 + (c / cols) * gw;
      v.push(x, ky, z0, x, ky, z0 + gd);
    }

    const spL = x0 + (4 / cols) * gw;
    const spR = x0 + (11 / cols) * gw;
    const spT = z0 + (4 / rows) * gd;
    const spB = z0 + gd;
    v.push(spL, ky + 0.003, spT, spR, ky + 0.003, spT);
    v.push(spL, ky + 0.003, spB, spR, ky + 0.003, spB);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Swivel base circle ── */
  const swivelGeo = useMemo(() => {
    const v = circleXZ(0.4, 0, 20);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Screen pane divider lines ── */
  const paneDividerGeo = useMemo(() => {
    const v: number[] = [];
    const hw = SCR_W / 2;
    const hh = SCR_H / 2;
    // Vertical divider
    v.push(SPLIT_X, -hh, 0, SPLIT_X, hh, 0);
    // Horizontal divider on right side
    v.push(SPLIT_X, SPLIT_Y, 0, hw, SPLIT_Y, 0);
    // Pane title underlines
    // SQL pane title line
    v.push(-hw + PANE_PAD, hh - 0.08, 0, SPLIT_X - PANE_PAD, hh - 0.08, 0);
    // Chart pane title line
    v.push(SPLIT_X + PANE_PAD, hh - 0.08, 0, hw - PANE_PAD, hh - 0.08, 0);
    // Table pane title line
    v.push(SPLIT_X + PANE_PAD, SPLIT_Y - 0.08, 0, hw - PANE_PAD, SPLIT_Y - 0.08, 0);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── SQL word layout — filled rectangles for each "word" ── */
  const sqlWordLayout = useMemo(() => {
    const words: { cx: number; cy: number; w: number }[] = [];
    const hw = SCR_W / 2;
    const hh = SCR_H / 2;
    const paneLeft = -hw + PANE_PAD;
    const lineH = 0.1;
    const startY = hh - 0.14;

    for (let line = 0; line < SQL_LINES.length; line++) {
      const segs = SQL_LINES[line];
      if (!segs) continue;
      const y = startY - line * lineH;
      let x = paneLeft;
      for (let s = 0; s < segs.length; s++) {
        const w = segs[s] ?? 0.2;
        words.push({ cx: x + w / 2, cy: y, w });
        x += w + 0.03;
      }
    }
    return words;
  }, []);

  /* ── Chart bar positions/sizes ── */
  const chartLayout = useMemo(() => {
    const hw = SCR_W / 2;
    const hh = SCR_H / 2;
    const paneLeft = SPLIT_X + PANE_PAD;
    const paneRight = hw - PANE_PAD;
    const paneTop = hh - 0.12;
    const paneBot = SPLIT_Y + PANE_PAD + 0.04;
    const paneW = paneRight - paneLeft;
    const maxH = paneTop - paneBot;
    const barW = paneW / (BAR_COUNT * 2);
    const bars: { x: number; maxH: number; y0: number }[] = [];

    for (let i = 0; i < BAR_COUNT; i++) {
      const bh = BAR_HEIGHTS[i] ?? 0.5;
      bars.push({
        x: paneLeft + (i * 2 + 1) * barW,
        maxH: bh * maxH,
        y0: paneBot,
      });
    }
    return bars;
  }, []);

  /* ── Table grid geometry ── */
  const tableGridGeo = useMemo(() => {
    const v: number[] = [];
    const hw = SCR_W / 2;
    const paneLeft = SPLIT_X + PANE_PAD;
    const paneRight = hw - PANE_PAD;
    const paneTop = SPLIT_Y - 0.12;
    const hh = SCR_H / 2;
    const paneBot = -hh + PANE_PAD;
    const cellW = (paneRight - paneLeft) / TABLE_COLS;
    const cellH = (paneTop - paneBot) / TABLE_ROWS;

    // Horizontal lines
    for (let r = 0; r <= TABLE_ROWS; r++) {
      const y = paneTop - r * cellH;
      v.push(paneLeft, y, 0, paneRight, y, 0);
    }
    // Vertical lines
    for (let c = 0; c <= TABLE_COLS; c++) {
      const x = paneLeft + c * cellW;
      v.push(x, paneTop, 0, x, paneBot, 0);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Table row fill positions ── */
  const tableRowLayout = useMemo(() => {
    const hw = SCR_W / 2;
    const paneLeft = SPLIT_X + PANE_PAD;
    const paneRight = hw - PANE_PAD;
    const paneTop = SPLIT_Y - 0.12;
    const hh = SCR_H / 2;
    const paneBot = -hh + PANE_PAD;
    const cellH = (paneTop - paneBot) / TABLE_ROWS;
    const w = paneRight - paneLeft;
    const rows: { cx: number; cy: number; w: number; h: number }[] = [];

    for (let r = 0; r < TABLE_ROWS; r++) {
      rows.push({
        cx: paneLeft + w / 2,
        cy: paneTop - (r + 0.5) * cellH,
        w,
        h: cellH - 0.01,
      });
    }
    return rows;
  }, []);

  /* ── Scan line (single horizontal line) ── */
  const scanGeo = useMemo(() => {
    const pos = new Float32Array([
      -SCR_W / 2, 0, 0,
      SCR_W / 2, 0, 0,
    ]);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    return geo;
  }, []);

  /* ── Animation ── */
  useFrame((_, delta) => {
    if (!groupRef.current) return;
    timeRef.current += delta;

    // Track hover time (resets when not hovered)
    if (hovered) {
      hoverTimeRef.current += delta;
    } else {
      hoverTimeRef.current = 0;
    }

    // Subtle float
    groupRef.current.position.y = Math.sin(timeRef.current * 0.8) * 0.04;

    // Power LED breathing
    if (ledRef.current) {
      const mat = ledRef.current.material as THREE.MeshBasicMaterial;
      const brightness = 0.7 + Math.sin(timeRef.current * 2) * 0.3;
      mat.opacity = brightness * (hovered ? 1.0 : 0.7);
    }

    // Cursor blink
    if (cursorRef.current) {
      const mat = cursorRef.current.material as THREE.MeshBasicMaterial;
      const rate = hovered ? 6 : 4;
      mat.opacity = Math.sin(timeRef.current * rate) > 0 ? (hovered ? 0.9 : 0.5) : 0.0;
    }

    // SQL word reveal animation
    if (sqlWordsRef.current) {
      const charsPerSec = 12;
      const cycleDuration = SQL_TOTAL_SEGS / charsPerSec + 1.5;
      const cycleT = hoverTimeRef.current % cycleDuration;
      const revealCount = Math.min(SQL_TOTAL_SEGS, Math.floor(cycleT * charsPerSec));

      sqlWordsRef.current.children.forEach((child, i) => {
        const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (hovered) {
          mat.opacity = i < revealCount ? 0.6 : 0;
        } else {
          mat.opacity = 0.2;
        }
      });

      // Position cursor at end of last revealed word
      if (cursorRef.current && hovered && revealCount > 0) {
        const lastWord = sqlWordLayout[revealCount - 1];
        if (lastWord) {
          cursorRef.current.position.x = lastWord.cx + lastWord.w / 2 + 0.03;
          cursorRef.current.position.y = lastWord.cy;
        }
      }
    }

    // Chart bar animation
    if (barsRef.current) {
      barsRef.current.children.forEach((bar, i) => {
        const layout = chartLayout[i];
        if (!layout) return;

        if (hovered) {
          // Bars grow one by one with stagger
          const delay = i * 0.3;
          const growT = Math.max(0, hoverTimeRef.current - delay);
          const progress = Math.min(1, growT * 2);
          const eased = 1 - Math.pow(1 - progress, 3);
          const h = layout.maxH * eased;
          bar.scale.y = Math.max(0.001, h);
          bar.position.y = layout.y0 + h / 2;
        } else {
          // Idle: bars at partial height, gently pulsing
          const pulse = 0.4 + Math.sin(timeRef.current * 0.5 + i) * 0.15;
          const h = layout.maxH * pulse;
          bar.scale.y = Math.max(0.001, h);
          bar.position.y = layout.y0 + h / 2;
        }
      });
    }

    // Table row fill animation
    if (tableRowsRef.current) {
      tableRowsRef.current.children.forEach((row, i) => {
        const mat = (row as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (hovered) {
          const delay = 0.8 + i * 0.25;
          const fillT = Math.max(0, hoverTimeRef.current - delay);
          const progress = Math.min(1, fillT * 3);
          mat.opacity = progress * 0.15;
        } else {
          mat.opacity = 0.02;
        }
      });
    }

    // Scan line sweep
    if (scanRef.current) {
      const posAttr = scanRef.current.geometry.attributes.position as THREE.BufferAttribute;
      const arr = posAttr.array as Float32Array;
      const sweepY = SCR_H / 2 - ((timeRef.current * 0.5) % 1) * SCR_H;
      arr[1] = sweepY;
      arr[4] = sweepY;
      posAttr.needsUpdate = true;
    }
  });

  const fz = HSG_D / 2 + 0.01;
  const monY = 0.3;
  const baseY = -0.65;
  const kbY = -0.55;
  const kbZ = 0.9;

  return (
    <group ref={groupRef} rotation={[0.15, 0, 0]}>
      {/* ── Monitor housing ── */}
      <group position={[0, monY, 0]}>
        <mesh>
          <boxGeometry args={[BZL_W, BZL_H, HSG_D]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.15 : 0.08}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={housingEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.65} />
        </lineSegments>

        {/* CRT taper (rear narrowing) */}
        <lineSegments geometry={taperGeo}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.3} />
        </lineSegments>

        {/* Front bezel & panel detail lines */}
        <lineSegments geometry={panelGeo}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.4} />
        </lineSegments>

        {/* CRT glass bulge — rendered BEHIND screen content */}
        <mesh position={[0, 0, fz]} scale={[0.67, 0.5, 0.08]}>
          <sphereGeometry args={[1.2, 32, 16]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.06 : 0.03}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>

        {/* Screen area fill */}
        <mesh position={[0, 0, fz]}>
          <boxGeometry args={[SCR_W, SCR_H, 0.01]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.05 : 0.02}
            toneMapped={false}
          />
        </mesh>

        {/* Scan line — sweeps behind content so it doesn't obscure text */}
        <group position={[0, 0, fz + 0.105]}>
          <lineSegments ref={scanRef} geometry={scanGeo}>
            <lineBasicMaterial
              color={CYAN}
              transparent
              opacity={hovered ? 0.1 : 0.05}
            />
          </lineSegments>
        </group>

        {/* ── Screen content — positioned well in front of glass bulge ── */}
        <group position={[0, 0, fz + 0.12]}>

          {/* Pane divider lines */}
          <lineSegments geometry={paneDividerGeo}>
            <lineBasicMaterial
              color={CYAN}
              transparent
              opacity={hovered ? 0.4 : 0.15}
            />
          </lineSegments>

          {/* SQL text — filled rectangle "word" blocks */}
          <group ref={sqlWordsRef}>
            {sqlWordLayout.map((word, i) => (
              <mesh key={i} position={[word.cx, word.cy, 0]}>
                <boxGeometry args={[word.w, SQL_WORD_H, 0.001]} />
                <meshBasicMaterial
                  color={CYAN}
                  transparent
                  opacity={0.2}
                  toneMapped={false}
                />
              </mesh>
            ))}
          </group>

          {/* Blinking cursor */}
          <mesh ref={cursorRef} position={[-SCR_W / 2 + 0.15, SCR_H / 2 - 0.14, 0]}>
            <boxGeometry args={[0.03, 0.06, 0.001]} />
            <meshBasicMaterial
              color={CYAN}
              transparent
              opacity={0.8}
              toneMapped={false}
            />
          </mesh>

          {/* ── Bar chart (top-right pane) ── */}
          <group ref={barsRef}>
            {chartLayout.map((bar, i) => (
              <mesh key={i} position={[bar.x, bar.y0, 0]}>
                <boxGeometry args={[0.06, 1, 0.001]} />
                <meshBasicMaterial
                  color={CYAN}
                  transparent
                  opacity={hovered ? 0.45 : 0.15}
                  toneMapped={false}
                />
              </mesh>
            ))}
          </group>

          {/* ── Data table (bottom-right pane) ── */}
          {/* Grid lines */}
          <lineSegments geometry={tableGridGeo}>
            <lineBasicMaterial
              color={CYAN}
              transparent
              opacity={hovered ? 0.3 : 0.1}
            />
          </lineSegments>

          {/* Row fills (animated) */}
          <group ref={tableRowsRef}>
            {tableRowLayout.map((row, i) => (
              <mesh key={i} position={[row.cx, row.cy, 0]}>
                <boxGeometry args={[row.w, row.h, 0.001]} />
                <meshBasicMaterial
                  color={CYAN}
                  transparent
                  opacity={0.02}
                  toneMapped={false}
                />
              </mesh>
            ))}
          </group>
        </group>

        {/* Power LED */}
        <mesh
          ref={ledRef}
          position={[-BZL_W / 2 + 0.15, -BZL_H / 2 + 0.04, fz + 0.01]}
        >
          <sphereGeometry args={[0.025, 8, 8]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={0.7}
            toneMapped={false}
          />
        </mesh>

        {/* Rear ventilation lines */}
        <lineSegments geometry={rearVentsGeo}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.2} />
        </lineSegments>
      </group>

      {/* ── Stand — tilt brackets ── */}
      {[-0.55, 0.55].map((x, i) => (
        <group key={i} position={[x, monY - BZL_H / 2 - 0.1, 0]}>
          <mesh>
            <boxGeometry args={[0.08, 0.25, 0.35]} />
            <meshBasicMaterial
              color={CYAN}
              transparent
              opacity={hovered ? 0.2 : 0.12}
              toneMapped={false}
            />
          </mesh>
        </group>
      ))}

      {/* ── Base plate ── */}
      <group position={[0, baseY, 0]}>
        <mesh>
          <boxGeometry args={[2.2, 0.06, 1.0]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.3 : 0.2}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.5} />
        </lineSegments>

        <lineSegments geometry={swivelGeo}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.25} />
        </lineSegments>
      </group>

      {/* ── Keyboard ── */}
      <group position={[0, kbY, kbZ]}>
        <mesh>
          <boxGeometry args={[KB_W, KB_H, KB_D]} />
          <meshBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.12 : 0.06}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={kbEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.45} />
        </lineSegments>

        <lineSegments geometry={keyGridGeo}>
          <lineBasicMaterial
            color={CYAN}
            transparent
            opacity={hovered ? 0.35 : 0.2}
          />
        </lineSegments>
      </group>
    </group>
  );
};
