/**
 * ProcessProgress — 3D accounting tabulator for "Processing rows..." phase.
 * Inspired by the IBM 407 Accounting Machine.
 *
 * Features: wide box chassis, 8 rotating counter drum wheels visible
 * through front-panel cutouts (each drum spins at a different rate to
 * simulate counting), paper feed rollers at the top, paper strip emerging
 * upward, operator panel with cycle counter display, and activity LEDs.
 *
 * Color: cyan (#00eeff)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './ProcessProgress.css';

interface ProcessProgressProps {
  label?: string;
}

const CYAN = '#00eeff';

/* ── Machine dimensions ── */
const MW = 2.4;
const MH = 1.6;
const MD = 1.0;

const DRUM_COUNT = 8;
const DRUM_R = 0.11;
const DRUM_H = 0.18;

/* ── IBM 407 Tabulator 3D object ── */
function Tabulator(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const drumsRef = useRef<THREE.Group>(null);
  const paperRef = useRef<THREE.Mesh>(null);
  const ledsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  /* Individual drum speed multipliers (prime-ish to avoid sync) */
  const drumSpeeds = useMemo(() => [1.0, 1.7, 2.3, 3.1, 1.4, 2.7, 1.9, 3.5], []);

  /* ── Precomputed geometries ── */

  const bodyEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(MW, MH, MD)),
    [],
  );

  /* Drum wheel geometry */
  const drumEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(DRUM_R, DRUM_R, DRUM_H, 12)),
    [],
  );

  /* Digit lines on each drum face (10 marks = 10 digits) */
  const drumFaceGeo = useMemo(() => {
    const verts: number[] = [];
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2;
      /* Short radial tick on top face */
      const r0 = DRUM_R * 0.55;
      const r1 = DRUM_R * 0.9;
      verts.push(r0 * Math.cos(a), DRUM_H / 2, r0 * Math.sin(a));
      verts.push(r1 * Math.cos(a), DRUM_H / 2, r1 * Math.sin(a));
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Drum cutout frames on front panel */
  const drumFramesGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = MD / 2 + 0.01;
    const drumSpacing = (MW - 0.4) / DRUM_COUNT;
    const cy = 0.15;

    for (let i = 0; i < DRUM_COUNT; i++) {
      const cx = -MW / 2 + 0.2 + i * drumSpacing + drumSpacing / 2;
      const hw = DRUM_R + 0.02;
      const hh = DRUM_R + 0.02;
      verts.push(cx - hw, cy - hh, fz, cx + hw, cy - hh, fz);
      verts.push(cx + hw, cy - hh, fz, cx + hw, cy + hh, fz);
      verts.push(cx + hw, cy + hh, fz, cx - hw, cy + hh, fz);
      verts.push(cx - hw, cy + hh, fz, cx - hw, cy - hh, fz);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Paper feed roller (horizontal cylinder at top of machine) */
  const rollerEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.06, 0.06, MW - 0.3, 12, 1, false, 0, Math.PI * 2)),
    [],
  );

  /* Operator panel display window (right side) */
  const displayGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = MD / 2 + 0.01;
    const cx = MW / 2 - 0.3;
    const cy = -0.3;
    const hw = 0.22;
    const hh = 0.12;
    verts.push(cx - hw, cy - hh, fz, cx + hw, cy - hh, fz);
    verts.push(cx + hw, cy - hh, fz, cx + hw, cy + hh, fz);
    verts.push(cx + hw, cy + hh, fz, cx - hw, cy + hh, fz);
    verts.push(cx - hw, cy + hh, fz, cx - hw, cy - hh, fz);
    /* Divider lines inside (4 digit slots) */
    for (let i = 1; i <= 3; i++) {
      const x = cx - hw + i * (hw * 2 / 4);
      verts.push(x, cy - hh, fz, x, cy + hh, fz);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Side panel detail lines */
  const sidePanelGeo = useMemo(() => {
    const verts: number[] = [];
    const sx = MW / 2 + 0.01;
    const halfD = MD / 2 - 0.1;
    for (let i = 0; i < 5; i++) {
      const y = -0.6 + i * 0.3;
      verts.push(sx, y, -halfD, sx, y, halfD);
      verts.push(-sx, y, -halfD, -sx, y, halfD);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Base plate */
  const baseEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(MW + 0.22, 0.09, MD + 0.1)),
    [],
  );

  /* LED geometry */
  const ledGeo = useMemo(() => new THREE.SphereGeometry(0.024, 6, 6), []);

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Float + slow rotation */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.62) * 0.04;
      groupRef.current.rotation.y = Math.sin(t * 0.17) * 0.2;
    }

    /* Drums spin at individual rates */
    if (drumsRef.current) {
      drumsRef.current.children.forEach((drum, i) => {
        drum.rotation.y += delta * (drumSpeeds[i] ?? 1.0) * 2.2;
      });
    }

    /* Paper rises — oscillates upward then snaps back */
    if (paperRef.current) {
      const rise = ((t * 0.4) % 1.0);
      paperRef.current.position.y = MH / 2 + 0.25 + rise * 0.5;
      paperRef.current.scale.y = 0.5 + rise * 1.5;
    }

    /* Activity LEDs */
    if (ledsRef.current) {
      ledsRef.current.children.forEach((child, i) => {
        const phase = t * 3.0 + i * 0.55;
        const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        mat.opacity = 0.4 + Math.abs(Math.sin(phase)) * 0.55;
      });
    }
  });

  const fz = MD / 2 + 0.01;
  const drumSpacing = (MW - 0.4) / DRUM_COUNT;
  const drumCY = 0.15;

  return (
    <group ref={groupRef}>

      {/* ── Base plate ── */}
      <group position={[0, -MH / 2 - 0.045, 0]}>
        <mesh>
          <boxGeometry args={[MW + 0.22, 0.09, MD + 0.1]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Main body ── */}
      <mesh>
        <boxGeometry args={[MW, MH, MD]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.07} toneMapped={false} />
      </mesh>
      <lineSegments geometry={bodyEdges}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Counter drum cutout frames ── */}
      <lineSegments geometry={drumFramesGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.45} />
      </lineSegments>

      {/* ── Counter drums (individual groups, each spins) ── */}
      <group ref={drumsRef}>
        {Array.from({ length: DRUM_COUNT }, (_, i) => {
          const cx = -MW / 2 + 0.2 + i * drumSpacing + drumSpacing / 2;
          return (
            <group key={i} position={[cx, drumCY, fz + 0.01]} rotation={[Math.PI / 2, 0, 0]}>
              <mesh>
                <cylinderGeometry args={[DRUM_R, DRUM_R, DRUM_H, 12]} />
                <meshBasicMaterial color={CYAN} transparent opacity={0.14} toneMapped={false} />
              </mesh>
              <lineSegments geometry={drumEdges}>
                <lineBasicMaterial color={CYAN} transparent opacity={0.6} />
              </lineSegments>
              <lineSegments geometry={drumFaceGeo}>
                <lineBasicMaterial color={CYAN} transparent opacity={0.35} />
              </lineSegments>
            </group>
          );
        })}
      </group>

      {/* ── Paper feed roller (at top) ── */}
      <group position={[0, MH / 2 - 0.12, fz + 0.06]} rotation={[0, 0, Math.PI / 2]}>
        <mesh>
          <cylinderGeometry args={[0.06, 0.06, MW - 0.3, 12]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.2} toneMapped={false} />
        </mesh>
        <lineSegments geometry={rollerEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
        </lineSegments>
      </group>

      {/* ── Paper strip emerging from top ── */}
      <mesh ref={paperRef} position={[0, MH / 2 + 0.25, fz + 0.015]}>
        <boxGeometry args={[MW * 0.7, 0.5, 0.01]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.12} toneMapped={false} side={THREE.DoubleSide} />
      </mesh>

      {/* ── Operator display window ── */}
      <lineSegments geometry={displayGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.45} />
      </lineSegments>

      {/* ── Side panel detail ── */}
      <lineSegments geometry={sidePanelGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.2} />
      </lineSegments>

      {/* ── Activity LEDs ── */}
      <group ref={ledsRef}>
        {Array.from({ length: 5 }, (_, i) => (
          <mesh
            key={i}
            geometry={ledGeo}
            position={[-MW / 2 + 0.2 + i * 0.22, -MH / 2 + 0.18, fz + 0.01]}
          >
            <meshBasicMaterial color={CYAN} transparent opacity={0.6} toneMapped={false} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

export const ProcessProgress: React.FC<ProcessProgressProps> = ({ label = 'Processing rows...' }) => (
  <div className="process-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={5.0} fov={50}>
        <Tabulator />
      </QueryScene>
    </div>
    <div className="process-progress-label">{label}</div>
  </div>
);
