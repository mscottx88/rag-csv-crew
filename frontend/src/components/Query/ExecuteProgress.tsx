/**
 * ExecuteProgress — 3D disk pack drive for "Executing query..." phase.
 * Inspired by the IBM 2311/2314 Disk Storage Drive.
 *
 * Features: tall tower cabinet, glass viewing window showing 5 stacked
 * spinning disk platters, access arm that sweeps radially between platters,
 * operator panel with activity LED row, and ventilation slots on sides.
 * Data transfer indicator pulses with each platter revolution.
 *
 * Color: cyan (#00eeff)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './ExecuteProgress.css';

interface ExecuteProgressProps {
  label?: string;
}

const CYAN = '#00eeff';

/* ── Cabinet dimensions ── */
const CW = 1.4;
const CH = 2.3;
const CD = 0.95;

const PLATTER_COUNT = 5;
const PLATTER_R = 0.42;
const PLATTER_GAP = 0.22;

/* ── IBM 2311 Disk Pack Drive 3D object ── */
function DiskPackDrive(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const plattersRef = useRef<THREE.Group>(null);
  const armRef = useRef<THREE.Group>(null);
  const ledsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  /* ── Precomputed geometries ── */

  const cabinetEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(CW, CH, CD)),
    [],
  );

  /* Viewing window frame */
  const windowGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = CD / 2 + 0.01;
    const hw = PLATTER_R + 0.1;
    const totalH = PLATTER_COUNT * PLATTER_GAP;
    const cy = totalH / 2 - 0.22;
    const hh = totalH / 2 + 0.05;
    verts.push(-hw, cy - hh, fz, hw, cy - hh, fz);
    verts.push(hw, cy - hh, fz, hw, cy + hh, fz);
    verts.push(hw, cy + hh, fz, -hw, cy + hh, fz);
    verts.push(-hw, cy + hh, fz, -hw, cy - hh, fz);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Individual platter — thin cylinder */
  const platterEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(PLATTER_R, PLATTER_R, 0.04, 36)),
    [],
  );

  /* Platter track rings (surface detail) */
  const platterTrackGeo = useMemo(() => {
    const verts: number[] = [];
    [0.15, 0.25, 0.34].forEach(r => {
      const segs = 32;
      for (let i = 0; i < segs; i++) {
        const a0 = (i / segs) * Math.PI * 2;
        const a1 = ((i + 1) / segs) * Math.PI * 2;
        verts.push(r * Math.cos(a0), 0.022, r * Math.sin(a0));
        verts.push(r * Math.cos(a1), 0.022, r * Math.sin(a1));
      }
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Platter hub */
  const hubEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.07, 0.07, 0.12, 10)),
    [],
  );

  /* Access arm */
  const armEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.06, 0.06, PLATTER_R * 1.1)),
    [],
  );

  /* Arm read head tip */
  const headEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.12, 0.06, 0.04)),
    [],
  );

  /* Operator panel bottom section */
  const panelGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = CD / 2 + 0.01;
    const panelY = -CH / 2 + 0.25;
    const hw = CW / 2 - 0.1;
    const hh = 0.2;
    verts.push(-hw, panelY - hh, fz, hw, panelY - hh, fz);
    verts.push(hw, panelY - hh, fz, hw, panelY + hh, fz);
    verts.push(hw, panelY + hh, fz, -hw, panelY + hh, fz);
    verts.push(-hw, panelY + hh, fz, -hw, panelY - hh, fz);
    /* Horizontal divider */
    verts.push(-hw, panelY, fz, hw, panelY, fz);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Ventilation lines (side panels) */
  const ventGeo = useMemo(() => {
    const verts: number[] = [];
    const sx = CW / 2 + 0.01;
    const halfD = CD / 2 - 0.1;
    for (let i = 0; i < 7; i++) {
      const y = -0.5 + i * 0.28;
      verts.push(sx, y, -halfD, sx, y, halfD);
      verts.push(-sx, y, -halfD, -sx, y, halfD);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Base plate */
  const baseEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(CW + 0.18, 0.08, CD + 0.12)),
    [],
  );

  /* LED geometry (shared) */
  const ledGeo = useMemo(() => new THREE.SphereGeometry(0.022, 6, 6), []);

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Float */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.7) * 0.04;
      groupRef.current.rotation.y = Math.sin(t * 0.16) * 0.2;
    }

    /* Platters spin (all together) */
    if (plattersRef.current) {
      plattersRef.current.rotation.y += delta * 2.8;
    }

    /* Access arm sweeps radially — sinusoidal from inner to outer */
    if (armRef.current) {
      const sweep = Math.sin(t * 0.55) * 0.5;
      armRef.current.position.z = CD / 2 + 0.02 + sweep * 0.12;
      armRef.current.position.x = sweep * PLATTER_R * 0.4;
    }

    /* Activity LEDs — staggered blink */
    if (ledsRef.current) {
      ledsRef.current.children.forEach((child, i) => {
        const phase = t * 2.5 + i * 0.7;
        const active = Math.sin(phase) > 0.2;
        const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
        mat.opacity = active ? 0.92 : 0.08;
      });
    }
  });

  const fz = CD / 2 + 0.01;
  const platterBaseY = -((PLATTER_COUNT - 1) * PLATTER_GAP) / 2 + 0.15;

  return (
    <group ref={groupRef}>

      {/* ── Base plate ── */}
      <group position={[0, -CH / 2 - 0.04, 0]}>
        <mesh>
          <boxGeometry args={[CW + 0.18, 0.08, CD + 0.12]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.12} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Cabinet ── */}
      <mesh>
        <boxGeometry args={[CW, CH, CD]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.07} toneMapped={false} />
      </mesh>
      <lineSegments geometry={cabinetEdges}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Viewing window frame ── */}
      <lineSegments geometry={windowGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Disk platters (spin together) ── */}
      <group ref={plattersRef}>
        {Array.from({ length: PLATTER_COUNT }, (_, i) => {
          const y = platterBaseY + i * PLATTER_GAP;
          return (
            <group key={i} position={[0, y, 0]}>
              <mesh>
                <cylinderGeometry args={[PLATTER_R, PLATTER_R, 0.04, 36]} />
                <meshBasicMaterial color={CYAN} transparent opacity={0.1} toneMapped={false} />
              </mesh>
              <lineSegments geometry={platterEdges}>
                <lineBasicMaterial color={CYAN} transparent opacity={0.45} />
              </lineSegments>
              <lineSegments geometry={platterTrackGeo}>
                <lineBasicMaterial color={CYAN} transparent opacity={0.2} />
              </lineSegments>
              {/* Hub */}
              <mesh>
                <cylinderGeometry args={[0.07, 0.07, 0.12, 10]} />
                <meshBasicMaterial color={CYAN} transparent opacity={0.25} toneMapped={false} />
              </mesh>
              <lineSegments geometry={hubEdges}>
                <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
              </lineSegments>
            </group>
          );
        })}
      </group>

      {/* ── Access arm ── */}
      <group ref={armRef} position={[0, platterBaseY + PLATTER_GAP, fz + 0.02]}>
        <mesh>
          <boxGeometry args={[0.06, 0.06, PLATTER_R * 1.1]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.2} toneMapped={false} />
        </mesh>
        <lineSegments geometry={armEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.65} />
        </lineSegments>
        {/* Read head */}
        <group position={[0, 0, -PLATTER_R * 0.5]}>
          <mesh>
            <boxGeometry args={[0.12, 0.06, 0.04]} />
            <meshBasicMaterial color={CYAN} transparent opacity={0.35} toneMapped={false} />
          </mesh>
          <lineSegments geometry={headEdges}>
            <lineBasicMaterial color={CYAN} transparent opacity={0.8} />
          </lineSegments>
          {/* Read tip LED */}
          <mesh position={[0, 0, -0.03]}>
            <sphereGeometry args={[0.02, 6, 6]} />
            <meshBasicMaterial color={CYAN} transparent opacity={0.9} toneMapped={false} />
          </mesh>
        </group>
      </group>

      {/* ── Operator panel ── */}
      <lineSegments geometry={panelGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.4} />
      </lineSegments>

      {/* ── Activity LEDs ── */}
      <group ref={ledsRef}>
        {Array.from({ length: 6 }, (_, i) => (
          <mesh
            key={i}
            geometry={ledGeo}
            position={[-CW / 2 + 0.2 + i * 0.16, -CH / 2 + 0.18, fz + 0.01]}
          >
            <meshBasicMaterial color={CYAN} transparent opacity={0.5} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* ── Side ventilation ── */}
      <lineSegments geometry={ventGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.2} />
      </lineSegments>
    </group>
  );
}

export const ExecuteProgress: React.FC<ExecuteProgressProps> = ({ label = 'Executing...' }) => (
  <div className="execute-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={5.2} fov={46}>
        <DiskPackDrive />
      </QueryScene>
    </div>
    <div className="execute-progress-label">{label}</div>
  </div>
);
