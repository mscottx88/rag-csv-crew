/**
 * SQLProgress — 3D card punch machine for "Generating SQL..." phase.
 * Inspired by the IBM 029 Card Punch.
 *
 * Features: desk-height box chassis, angled card hopper on the left,
 * card output stacker on the right, visible punch station in the center
 * with an animated punch head that descends rhythmically, a card that
 * slides left-to-right through the machine, keyboard panel with key grid
 * on the lower front, operator display window above the keyboard, and
 * a column counter LED row.
 *
 * Color: gold (#ffd700)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './SQLProgress.css';

interface SQLProgressProps {
  label?: string;
}

const GOLD = '#ffd700';

/* ── Machine dimensions ── */
const MW = 2.0;   // machine body width
const MH = 1.3;   // machine body height
const MD = 0.95;  // machine body depth

/* ── IBM 029 Card Punch 3D object ── */
function CardPunch(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const cardRef = useRef<THREE.Group>(null);
  const punchHeadRef = useRef<THREE.Mesh>(null);
  const timeRef = useRef(0);
  const cardPhaseRef = useRef(0); // 0 = in hopper, 1 = traversing, wraps

  /* ── Precomputed geometries ── */

  const bodyEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(MW, MH, MD)),
    [],
  );

  /* Card hopper (angled slot, left side of machine) */
  const hopperEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.38, 0.85, 0.6)),
    [],
  );

  /* Output stacker (angled slot, right side of machine) */
  const stackerEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.38, 0.72, 0.6)),
    [],
  );

  /* Punch station window frame */
  const stationGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = MD / 2 + 0.01;
    const cx = 0.0;
    const cy = 0.2;
    const hw = 0.22;
    const hh = 0.3;
    verts.push(cx - hw, cy - hh, fz, cx + hw, cy - hh, fz);
    verts.push(cx + hw, cy - hh, fz, cx + hw, cy + hh, fz);
    verts.push(cx + hw, cy + hh, fz, cx - hw, cy + hh, fz);
    verts.push(cx - hw, cy + hh, fz, cx - hw, cy - hh, fz);
    /* Cross guides inside station */
    verts.push(cx, cy - hh, fz, cx, cy + hh, fz);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Card geometry (IBM 80-column card proportions) */
  const cardEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(1.0, 0.44, 0.015)),
    [],
  );

  /* Keyboard panel — grid of keys */
  const keyboardGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = MD / 2 + 0.01;
    const kbTop = -MH / 2 + 0.38;
    const kbBot = -MH / 2 + 0.06;
    const cols = 10;
    const rows = 3;
    const kw = (MW - 0.3) / cols;
    const kh = (kbTop - kbBot) / rows;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = -MW / 2 + 0.15 + c * kw + kw * 0.1;
        const y = kbBot + r * kh + kh * 0.1;
        const w = kw * 0.8;
        const h = kh * 0.8;
        verts.push(x, y, fz, x + w, y, fz);
        verts.push(x + w, y, fz, x + w, y + h, fz);
        verts.push(x + w, y + h, fz, x, y + h, fz);
        verts.push(x, y + h, fz, x, y, fz);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Operator display window (small rectangular readout above keyboard) */
  const displayWindowGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = MD / 2 + 0.01;
    const cx = 0.5;
    const cy = -MH / 2 + 0.46;
    const hw = 0.28;
    const hh = 0.06;
    verts.push(cx - hw, cy - hh, fz, cx + hw, cy - hh, fz);
    verts.push(cx + hw, cy - hh, fz, cx + hw, cy + hh, fz);
    verts.push(cx + hw, cy + hh, fz, cx - hw, cy + hh, fz);
    verts.push(cx - hw, cy + hh, fz, cx - hw, cy - hh, fz);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Column counter LEDs (row of 8 dots across the top of punch station) */
  const ledGeo = useMemo(() => new THREE.SphereGeometry(0.022, 6, 6), []);

  /* Punch head */
  const punchHeadEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.12, 0.24, 0.08)),
    [],
  );

  /* Base plate */
  const baseEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(MW + 0.3, 0.09, MD + 0.12)),
    [],
  );

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Float */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.65) * 0.04;
      groupRef.current.rotation.y = Math.sin(t * 0.2) * 0.18;
    }

    /* Card traversal — cycles every 3 seconds */
    cardPhaseRef.current = (cardPhaseRef.current + delta / 3.0) % 1.0;
    const phase = cardPhaseRef.current;

    if (cardRef.current) {
      /* Card travels from hopper (x = -MW/2 + 0.35) to stacker (x = MW/2 - 0.35) */
      const startX = -MW / 2 + 0.05;
      const endX = MW / 2 - 0.05;
      cardRef.current.position.x = startX + phase * (endX - startX);
      /* Card visibility — fade in at start, fade out at end */
      const vis = phase < 0.1
        ? phase / 0.1
        : phase > 0.9
          ? (1 - phase) / 0.1
          : 1;
      cardRef.current.children.forEach(child => {
        const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (mat?.opacity !== undefined) mat.opacity = vis * 0.65;
      });
    }

    /* Punch head — bobs up/down rapidly */
    if (punchHeadRef.current) {
      const punchY = 0.2 + 0.18 - Math.abs(Math.sin(t * 4.5)) * 0.18;
      punchHeadRef.current.position.y = punchY;
    }
  });

  const fz = MD / 2 + 0.01;

  return (
    <group ref={groupRef}>

      {/* ── Base plate ── */}
      <group position={[0, -MH / 2 - 0.045, 0]}>
        <mesh>
          <boxGeometry args={[MW + 0.3, 0.09, MD + 0.12]} />
          <meshBasicMaterial color={GOLD} transparent opacity={0.15} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Main body ── */}
      <mesh>
        <boxGeometry args={[MW, MH, MD]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.08} toneMapped={false} />
      </mesh>
      <lineSegments geometry={bodyEdges}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Card hopper (left, tilted slightly) ── */}
      <group position={[-MW / 2 - 0.19, 0.15, 0]} rotation={[0, 0, -0.15]}>
        <mesh>
          <boxGeometry args={[0.38, 0.85, 0.6]} />
          <meshBasicMaterial color={GOLD} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={hopperEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.5} />
        </lineSegments>
        {/* Stacked cards in hopper (4 thin layers) */}
        {[0, 0.02, 0.04, 0.06].map((dz, i) => (
          <mesh key={i} position={[0, 0, -0.25 + dz]}>
            <boxGeometry args={[0.3, 0.78, 0.012]} />
            <meshBasicMaterial color={GOLD} transparent opacity={0.18} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* ── Output stacker (right, tilted) ── */}
      <group position={[MW / 2 + 0.19, 0.08, 0]} rotation={[0, 0, 0.15]}>
        <mesh>
          <boxGeometry args={[0.38, 0.72, 0.6]} />
          <meshBasicMaterial color={GOLD} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={stackerEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Punch station window ── */}
      <lineSegments geometry={stationGeo}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.5} />
      </lineSegments>

      {/* ── Punch head (moves up/down) ── */}
      <mesh ref={punchHeadRef} position={[0, 0.36, fz + 0.01]}>
        <boxGeometry args={[0.12, 0.24, 0.08]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.25} toneMapped={false} />
      </mesh>
      <lineSegments geometry={punchHeadEdges} position={[0, 0.36, fz + 0.01]}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.6} />
      </lineSegments>

      {/* ── Animated card (travels left → right) ── */}
      <group ref={cardRef} position={[0, 0.05, fz + 0.01]}>
        <mesh>
          <boxGeometry args={[1.0, 0.44, 0.015]} />
          <meshBasicMaterial color={GOLD} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={cardEdges}>
          <lineBasicMaterial color={GOLD} transparent opacity={0.65} />
        </lineSegments>
        {/* Punch hole rows (decorative lines) */}
        {[-0.15, -0.05, 0.05, 0.15].map((dy, i) => (
          <mesh key={i} position={[0, dy, 0.009]}>
            <boxGeometry args={[0.9, 0.025, 0.001]} />
            <meshBasicMaterial color={GOLD} transparent opacity={0.3} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* ── Keyboard panel ── */}
      <lineSegments geometry={keyboardGeo}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.35} />
      </lineSegments>

      {/* ── Operator display ── */}
      <lineSegments geometry={displayWindowGeo}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.45} />
      </lineSegments>

      {/* ── Column counter LEDs ── */}
      {Array.from({ length: 8 }, (_, i) => (
        <mesh key={i} geometry={ledGeo} position={[-0.35 + i * 0.1, MH / 2 - 0.14, fz + 0.01]}>
          <meshBasicMaterial color={GOLD} transparent opacity={0.6} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

export const SQLProgress: React.FC<SQLProgressProps> = ({ label = 'Generating SQL...' }) => (
  <div className="sql-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={4.8} fov={48}>
        <CardPunch />
      </QueryScene>
    </div>
    <div className="sql-progress-label">{label}</div>
  </div>
);
