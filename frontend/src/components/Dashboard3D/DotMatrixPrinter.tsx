/**
 * DotMatrixPrinter — Realistic 3D IBM dot matrix printer for the History card.
 * Inspired by the IBM Proprinter / 5152. Semi-transparent solid
 * neon gold (#ffd700) with Bloom glow.
 *
 * Paper feeds from a fan-fold stack below, through the tractor mechanism,
 * and exits UPWARD out the back of the printer. The output paper rises to
 * a page-break height then FOLDS OVER at the perforation, dropping down
 * in the classic fan-fold cascade. Folded pages accumulate in a pile.
 *
 * When hovered: faster feed, faster head shuttle, more rapid folding.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const GOLD = '#ffd700';

/* ── Printer body ── */
const BODY_W = 2.6;
const BODY_H = 0.55;
const BODY_D = 1.4;

/* ── Paper ── */
const PAPER_W = 1.8;
const PAPER_LEN = 1.3;     // visible paper length on top of printer
const TRACTOR_X = 1.08;
const STRIP_W = 0.1;

/* ── Platen roller ── */
const PLATEN_R = 0.08;

/* ── Print head ── */
const RAIL_W = 2.0;
const HEAD_W = 0.2;
const HEAD_H = 0.15;
const HEAD_D = 0.12;

/* ── Tractor wheels ── */
const WHEEL_R = 0.15;
const WHEEL_PINS = 10;

const PRINT_LINE_H = 0.035;
const PRINT_ZONE_Z = -0.05;

/* ── Output paper (rises from back of printer) ── */
const PAGE_HEIGHT = 0.75;  // how tall one page rises before folding
const OUTPUT_Z = -PAPER_LEN / 2 - 0.02; // z of output paper (back of printer top)
const MAX_PILE_PAGES = 5;  // max pre-rendered pile pages

interface DotMatrixPrinterProps {
  hovered: boolean;
}

/** Circle outline in YZ plane. */
function circleYZ(cy: number, cz: number, radius: number, segs = 16): number[] {
  const v: number[] = [];
  for (let i = 0; i < segs; i++) {
    const a0 = (i / segs) * Math.PI * 2;
    const a1 = ((i + 1) / segs) * Math.PI * 2;
    v.push(
      0, cy + Math.cos(a0) * radius, cz + Math.sin(a0) * radius,
      0, cy + Math.cos(a1) * radius, cz + Math.sin(a1) * radius,
    );
  }
  return v;
}

/** Sprocket pin lines in YZ plane. */
function sprocketPins(cy: number, cz: number, radius: number, pinLen: number, count: number): number[] {
  const v: number[] = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    v.push(
      0, cy + Math.cos(a) * radius, cz + Math.sin(a) * radius,
      0, cy + Math.cos(a) * (radius + pinLen), cz + Math.sin(a) * (radius + pinLen),
    );
  }
  return v;
}

export const DotMatrixPrinter: React.FC<DotMatrixPrinterProps> = ({ hovered }) => {
  const groupRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Mesh>(null);
  const leftWheelsRef = useRef<THREE.Group>(null);
  const rightWheelsRef = useRef<THREE.Group>(null);
  const onlineLedRef = useRef<THREE.Mesh>(null);
  const activityLedRef = useRef<THREE.Mesh>(null);

  /* Output paper animation refs */
  const outputTextRef = useRef<THREE.Group>(null);
  const risingSheetRef = useRef<THREE.Mesh>(null);
  const risingEdgesRef = useRef<THREE.LineSegments>(null);
  const perfMarkRef = useRef<THREE.LineSegments>(null);
  const foldGroupRef = useRef<THREE.Group>(null);
  const foldSheetRef = useRef<THREE.Mesh>(null);
  const foldEdgesRef = useRef<THREE.LineSegments>(null);
  const pileRef = useRef<THREE.Group>(null);

  const timeRef = useRef(0);
  const paperFeedRef = useRef(0);

  /* ── Body edges ── */
  const bodyEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(BODY_W, BODY_H, BODY_D);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const coverEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(BODY_W - 0.2, 0.14, 0.45);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const baseEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(BODY_W + 0.2, 0.04, BODY_D + 0.2);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── Tractor wheel geometry ── */
  const tractorWheelGeo = useMemo(() => {
    const v: number[] = [];
    const pinLen = 0.05;
    for (const wz of [-0.1, 0.1]) {
      v.push(...circleYZ(0, wz, WHEEL_R, 18));
      v.push(...sprocketPins(0, wz, WHEEL_R, pinLen, WHEEL_PINS));
      v.push(...circleYZ(0, wz, WHEEL_R * 0.35, 10));
      for (let s = 0; s < 3; s++) {
        const a = (s / 3) * Math.PI;
        const dy = Math.cos(a) * WHEEL_R * 0.9;
        const dz = Math.sin(a) * WHEEL_R * 0.9;
        v.push(0, -dy, wz - dz, 0, dy, wz + dz);
      }
    }
    v.push(0, WHEEL_R + 0.03, -0.1, 0, WHEEL_R + 0.03, 0.1);
    v.push(0, -WHEEL_R - 0.03, -0.1, 0, -WHEEL_R - 0.03, 0.1);
    v.push(0, 0, -0.1, 0, 0, 0.1);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Output paper perforation mark (dashed line on the rising sheet) ── */
  const outputPerfGeo = useMemo(() => {
    const v: number[] = [];
    const hw = PAPER_W / 2 + STRIP_W;
    // Dashed horizontal line at y = 0 (will be positioned at perforation height)
    const dashW = hw * 0.3;
    for (let d = 0; d < 4; d++) {
      const x0 = -hw + 0.02 + d * dashW * 2 + dashW * 0.15;
      v.push(x0, 0, 0, x0 + dashW - 0.04, 0, 0);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Output text layout (individual meshes that animate as paper feeds) ── */
  const OUTPUT_TEXT_LINES = 14;
  const outputTextLayout = useMemo(() => {
    const hw = PAPER_W / 2;
    const maxW = hw * 0.85;
    const spacing = PAGE_HEIGHT / (OUTPUT_TEXT_LINES + 1);
    const widths = [0.8, 0.55, 0.95, 0.4, 0.7, 0.85, 0.5, 0.65, 0.75, 0.42, 0.9, 0.58, 0.82, 0.48];
    const lines: { lineY: number; w: number; cx: number }[] = [];
    for (let i = 0; i < OUTPUT_TEXT_LINES; i++) {
      const relW = widths[i % widths.length] ?? 0.5;
      const w = relW * maxW;
      const indent = i % 4 === 0 ? 0.06 : i % 3 === 0 ? 0.03 : 0;
      lines.push({
        lineY: (i + 1) * spacing,
        w,
        cx: -hw + 0.08 + indent + w / 2,
      });
    }
    return lines;
  }, []);

  /* ── Control panel ── */
  const controlPanelGeo = useMemo(() => {
    const v: number[] = [];
    const fz = BODY_D / 2 + 0.005;
    const panelTop = BODY_H / 2 - 0.06;
    const panelBot = -BODY_H / 2 + 0.04;
    const panelLeft = -BODY_W / 2 + 0.1;
    const panelW = 0.9;
    v.push(panelLeft, panelBot, fz, panelLeft + panelW, panelBot, fz);
    v.push(panelLeft, panelTop, fz, panelLeft + panelW, panelTop, fz);
    v.push(panelLeft, panelBot, fz, panelLeft, panelTop, fz);
    v.push(panelLeft + panelW, panelBot, fz, panelLeft + panelW, panelTop, fz);
    const divY = panelBot + 0.08;
    v.push(panelLeft + 0.03, divY, fz, panelLeft + panelW - 0.03, divY, fz);
    const btnW = 0.1;
    const btnH = 0.05;
    const btnY = (panelBot + divY) / 2;
    for (let b = 0; b < 4; b++) {
      const bx = panelLeft + 0.07 + b * 0.2;
      v.push(bx, btnY - btnH / 2, fz, bx + btnW, btnY - btnH / 2, fz);
      v.push(bx, btnY + btnH / 2, fz, bx + btnW, btnY + btnH / 2, fz);
      v.push(bx, btnY - btnH / 2, fz, bx, btnY + btnH / 2, fz);
      v.push(bx + btnW, btnY - btnH / 2, fz, bx + btnW, btnY + btnH / 2, fz);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Side vents ── */
  const sideVentsGeo = useMemo(() => {
    const v: number[] = [];
    for (const xSign of [-1, 1]) {
      const x = xSign * (BODY_W / 2 + 0.005);
      for (let i = 0; i < 4; i++) {
        v.push(x, -BODY_H / 2 + 0.1 + i * 0.1, -0.3, x, -BODY_H / 2 + 0.1 + i * 0.1, 0.3);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Ribbon cartridge ── */
  const ribbonEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(0.6, 0.06, 0.14);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── Rising output paper — edge outline (left + right + bottom edges) ── */
  const risingEdgesGeo = useMemo(() => {
    // Unit-height rectangle edges in XY plane at z=0
    // Will be scaled in Y by the animation
    const v: number[] = [];
    const hw = PAPER_W / 2 + STRIP_W;
    // Left edge (bottom to top)
    v.push(-hw, 0, 0, -hw, 1, 0);
    // Right edge
    v.push(hw, 0, 0, hw, 1, 0);
    // Bottom edge
    v.push(-hw, 0, 0, hw, 0, 0);
    // Top edge
    v.push(-hw, 1, 0, hw, 1, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Fold sheet edge outline ── */
  const foldEdgesGeo = useMemo(() => {
    const v: number[] = [];
    const hw = PAPER_W / 2 + STRIP_W;
    const h = PAGE_HEIGHT * 0.18; // fold portion is ~18% of page
    v.push(-hw, 0, 0, -hw, h, 0);
    v.push(hw, 0, 0, hw, h, 0);
    v.push(-hw, 0, 0, hw, 0, 0);
    v.push(-hw, h, 0, hw, h, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Animation ── */
  useFrame((_, delta) => {
    if (!groupRef.current) return;
    timeRef.current += delta;

    const feedSpeed = hovered ? 0.55 : 0.22;
    paperFeedRef.current += delta * feedSpeed;

    // Subtle float
    groupRef.current.position.y = Math.sin(timeRef.current * 0.8) * 0.04;

    // Print head oscillation
    if (headRef.current) {
      const speed = hovered ? 12 : 4;
      headRef.current.position.x = Math.sin(timeRef.current * speed) * (RAIL_W / 2 - HEAD_W / 2);
    }

    // Tractor wheel rotation
    const wheelRot = paperFeedRef.current * 3;
    if (leftWheelsRef.current) leftWheelsRef.current.rotation.x = wheelRot;
    if (rightWheelsRef.current) rightWheelsRef.current.rotation.x = wheelRot;

    /* ── Output paper: rise → perforation → fold → pile ── */
    const bodyTop = BODY_H / 2;
    const outputBaseY = bodyTop + 0.02;
    const pagePhase = (paperFeedRef.current / PAGE_HEIGHT) % 1; // 0→1 per page
    const pageCount = Math.floor(paperFeedRef.current / PAGE_HEIGHT);
    const foldStart = 0.82; // fold begins at 82% of page cycle
    const foldPortion = PAGE_HEIGHT * 0.18; // top 18% folds over

    // Rising sheet (the main output paper growing upward)
    if (risingSheetRef.current) {
      const riseProgress = Math.min(pagePhase / foldStart, 1);
      const sheetH = riseProgress * PAGE_HEIGHT;
      risingSheetRef.current.scale.set(PAPER_W + STRIP_W * 2, Math.max(0.001, sheetH), 0.003);
      risingSheetRef.current.position.y = outputBaseY + sheetH / 2;
    }

    // Rising sheet edge outline
    if (risingEdgesRef.current) {
      const riseProgress = Math.min(pagePhase / foldStart, 1);
      const sheetH = riseProgress * PAGE_HEIGHT;
      risingEdgesRef.current.scale.set(1, Math.max(0.001, sheetH), 1);
      risingEdgesRef.current.position.y = outputBaseY;
    }

    // Output text lines — printed at the ribbon head (bottom), scroll upward on paper
    if (outputTextRef.current) {
      const riseProgress = Math.min(pagePhase / foldStart, 1);
      const sheetH = riseProgress * PAGE_HEIGHT;
      outputTextRef.current.children.forEach((child, i) => {
        const mesh = child as THREE.Mesh;
        const mat = mesh.material as THREE.MeshBasicMaterial;
        const layout = outputTextLayout[i];
        if (!layout) return;
        // Text is fixed on the paper. lineY = how far into the page it was printed.
        // Scene Y = sheetH - lineY: first-printed lines are at the top, newest at bottom.
        const posY = sheetH - layout.lineY;
        if (layout.lineY <= sheetH && posY > 0.01) {
          mesh.position.y = posY;
          // Freshness: lines near the bottom (small posY) were just printed
          const freshness = Math.max(0, 1 - posY * 3);
          mat.opacity = hovered
            ? 0.3 + freshness * 0.35
            : 0.15 + freshness * 0.15;
          mesh.visible = true;
        } else {
          mesh.visible = false;
        }
      });
    }

    // Perforation mark — positioned near the top of the rising sheet
    if (perfMarkRef.current) {
      const riseProgress = Math.min(pagePhase / foldStart, 1);
      const sheetH = riseProgress * PAGE_HEIGHT;
      // Perf line sits at the fold crease point (where the page will fold)
      const perfY = outputBaseY + sheetH - foldPortion;
      perfMarkRef.current.position.y = Math.max(outputBaseY + 0.05, perfY);
      perfMarkRef.current.visible = sheetH > foldPortion + 0.05;
    }

    // Fold sheet — the top portion that rotates over at the perforation
    if (foldGroupRef.current && foldSheetRef.current) {
      if (pagePhase >= foldStart) {
        foldGroupRef.current.visible = true;
        const foldProgress = (pagePhase - foldStart) / (1 - foldStart); // 0→1
        // Ease-in-out for natural fold motion
        const eased = foldProgress < 0.5
          ? 2 * foldProgress * foldProgress
          : 1 - Math.pow(-2 * foldProgress + 2, 2) / 2;

        // Position at the perforation crease (top of the risen portion minus fold portion)
        const creaseY = outputBaseY + PAGE_HEIGHT - foldPortion;
        foldGroupRef.current.position.y = creaseY;

        // Rotate from vertical (0) to folded over backward (-PI, hanging down behind)
        foldGroupRef.current.rotation.x = -eased * Math.PI;

        // Size the fold sheet
        foldSheetRef.current.scale.set(
          PAPER_W + STRIP_W * 2, Math.max(0.001, foldPortion), 0.003,
        );
        foldSheetRef.current.position.y = foldPortion / 2;
      } else {
        foldGroupRef.current.visible = false;
      }
    }

    // Fold edges
    if (foldEdgesRef.current && foldGroupRef.current) {
      foldEdgesRef.current.visible = foldGroupRef.current.visible;
    }

    // Page pile — show accumulated folded pages
    if (pileRef.current) {
      const visiblePages = Math.min(pageCount, MAX_PILE_PAGES);
      pileRef.current.children.forEach((child, i) => {
        child.visible = i < visiblePages;
        if (i < visiblePages) {
          // Stack pages slightly offset for visual depth
          child.position.y = i * 0.015;
        }
      });
    }

    // LEDs
    if (onlineLedRef.current) {
      const mat = onlineLedRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.5 + Math.sin(timeRef.current * 1.5) * 0.3;
    }
    if (activityLedRef.current) {
      const mat = activityLedRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = hovered
        ? (Math.sin(timeRef.current * 18) > 0 ? 0.85 : 0.1)
        : 0.12 + Math.sin(timeRef.current * 0.8) * 0.08;
    }
  });

  const bodyTop = BODY_H / 2;
  const coverY = bodyTop + 0.07;
  const railY = bodyTop + 0.1;
  const baseY = -BODY_H / 2 - 0.02;
  const outputBaseY = bodyTop + 0.02;
  const pw = PAPER_W + STRIP_W * 2;

  return (
    <group ref={groupRef} rotation={[0.22, 0, 0]}>
      {/* ── Main body ── */}
      <mesh>
        <boxGeometry args={[BODY_W, BODY_H, BODY_D]} />
        <meshBasicMaterial
          color={GOLD} transparent opacity={hovered ? 0.12 : 0.06}
          side={THREE.DoubleSide} toneMapped={false}
        />
      </mesh>
      <lineSegments geometry={bodyEdges}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.6} />
      </lineSegments>

      {/* ── Top cover ── */}
      <group position={[0, coverY, -BODY_D / 2 + 0.28]}>
        <mesh>
          <boxGeometry args={[BODY_W - 0.2, 0.14, 0.45]} />
          <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.1 : 0.05} toneMapped={false} />
        </mesh>
        <lineSegments geometry={coverEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.45} />
        </lineSegments>
      </group>

      {/* ── Platen roller ── */}
      <mesh position={[0, bodyTop + PLATEN_R + 0.01, PRINT_ZONE_Z]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[PLATEN_R, PLATEN_R, pw + 0.1, 14]} />
        <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.2 : 0.12} toneMapped={false} />
      </mesh>

      {/* ── Tractor feed wheels ── */}
      <group position={[-TRACTOR_X, bodyTop + 0.04, PRINT_ZONE_Z]}>
        <group ref={leftWheelsRef}>
          <lineSegments geometry={tractorWheelGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.6 : 0.4} />
          </lineSegments>
        </group>
      </group>
      <group position={[TRACTOR_X, bodyTop + 0.04, PRINT_ZONE_Z]}>
        <group ref={rightWheelsRef}>
          <lineSegments geometry={tractorWheelGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.6 : 0.4} />
          </lineSegments>
        </group>
      </group>

      {/* ── Print head rail ── */}
      <mesh position={[0, railY, PRINT_ZONE_Z]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.02, 0.02, RAIL_W + 0.2, 8]} />
        <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.5 : 0.35} toneMapped={false} />
      </mesh>

      {/* ── Print head carriage ── */}
      <group position={[0, railY, PRINT_ZONE_Z]}>
        <mesh ref={headRef}>
          <boxGeometry args={[HEAD_W, HEAD_H, HEAD_D]} />
          <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.4 : 0.22} toneMapped={false} />
        </mesh>
      </group>

      {/* ── Ribbon cartridge ── */}
      <group position={[0, railY - 0.03, PRINT_ZONE_Z - 0.14]}>
        <mesh>
          <boxGeometry args={[0.6, 0.06, 0.14]} />
          <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.15 : 0.08} toneMapped={false} />
        </mesh>
        <lineSegments geometry={ribbonEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.3} />
        </lineSegments>
      </group>

      {/* ══════════════════════════════════════════════════════════
          OUTPUT PAPER — rises upward from back of printer
          ══════════════════════════════════════════════════════════ */}

      {/* Rising paper sheet (animated scale.y) */}
      <group position={[0, 0, OUTPUT_Z]}>
        <mesh ref={risingSheetRef} position={[0, outputBaseY, 0]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.14 : 0.08} toneMapped={false} />
        </mesh>

        {/* Rising sheet edge outline */}
        <lineSegments ref={risingEdgesRef} geometry={risingEdgesGeo} position={[0, outputBaseY, 0]}>
          <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.5 : 0.3} />
        </lineSegments>

        {/* Printed text on the rising output sheet — animated per-line */}
        <group ref={outputTextRef} position={[0, outputBaseY, 0]}>
          {outputTextLayout.map((line, i) => (
            <mesh key={i} position={[line.cx, line.lineY, 0.002]} visible={false}>
              <boxGeometry args={[line.w, PRINT_LINE_H, 0.001]} />
              <meshBasicMaterial color={GOLD} transparent opacity={0} toneMapped={false} />
            </mesh>
          ))}
        </group>

        {/* Perforation mark (positioned at crease point) */}
        <lineSegments ref={perfMarkRef} position={[0, outputBaseY + PAGE_HEIGHT * 0.7, 0]}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={outputPerfGeo.attributes.position?.count ?? 0}
              array={(outputPerfGeo.attributes.position as THREE.Float32BufferAttribute).array}
              itemSize={3}
            />
          </bufferGeometry>
          <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.55 : 0.3} />
        </lineSegments>

        {/* Fold group — top portion that rotates at the perforation crease */}
        <group ref={foldGroupRef} position={[0, outputBaseY + PAGE_HEIGHT * 0.82, 0]} visible={false}>
          <mesh ref={foldSheetRef} position={[0, PAGE_HEIGHT * 0.09, 0]}>
            <boxGeometry args={[1, 1, 1]} />
            <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.14 : 0.08} toneMapped={false} />
          </mesh>
          <lineSegments ref={foldEdgesRef} geometry={foldEdgesGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.5 : 0.3} />
          </lineSegments>
        </group>

        {/* Page pile — folded pages accumulating below the output */}
        <group ref={pileRef} position={[0, outputBaseY - 0.02, -0.04]}>
          {[...Array(MAX_PILE_PAGES)].map((_, i) => (
            <mesh key={`pile-${i}`} position={[0, 0, 0]} visible={false}>
              <boxGeometry args={[pw, 0.008, PAGE_HEIGHT * 0.18]} />
              <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.1 : 0.06} toneMapped={false} />
            </mesh>
          ))}
        </group>
      </group>

      {/* ── Control panel ── */}
      <lineSegments geometry={controlPanelGeo}>
        <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.4 : 0.25} />
      </lineSegments>

      {/* LEDs */}
      <mesh ref={onlineLedRef} position={[BODY_W / 2 - 0.18, BODY_H / 2 - 0.1, BODY_D / 2 + 0.01]}>
        <sphereGeometry args={[0.028, 8, 8]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.5} toneMapped={false} />
      </mesh>
      <mesh ref={activityLedRef} position={[BODY_W / 2 - 0.33, BODY_H / 2 - 0.1, BODY_D / 2 + 0.01]}>
        <sphereGeometry args={[0.028, 8, 8]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.12} toneMapped={false} />
      </mesh>

      {/* ── Side vents ── */}
      <lineSegments geometry={sideVentsGeo}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.2} />
      </lineSegments>

      {/* ── Base plate ── */}
      <group position={[0, baseY, 0]}>
        <mesh>
          <boxGeometry args={[BODY_W + 0.2, 0.04, BODY_D + 0.2]} />
          <meshBasicMaterial color={GOLD} transparent opacity={hovered ? 0.2 : 0.12} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.4} />
        </lineSegments>
      </group>
    </group>
  );
};
