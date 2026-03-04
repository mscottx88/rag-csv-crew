/**
 * SearchProgress — 3D sonar/radar console for "Searching columns..." phase.
 * Inspired by AN/SQS naval sonar array displays.
 *
 * Features: flat parabolic dish on pedestal viewed from above at 45°,
 * continuously rotating sweep arm with glow trail, fading blip particles
 * that appear near the sweep as "hits" are detected.
 *
 * Color: cyan (#00eeff)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './SearchProgress.css';

interface SearchProgressProps {
  label?: string;
}

const CYAN = '#00eeff';
const DISK_R = 1.1;
const BLIP_SLOTS = 10;

/* ── Sonar Console 3D object ── */
function SonarConsole(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const sweepGroupRef = useRef<THREE.Group>(null);
  const blipsGroupRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);
  const sweepAngleRef = useRef(0);

  /* Blip state — fixed-size pool so mesh count is stable */
  const blipPool = useRef<{ x: number; z: number; life: number }[]>(
    Array.from({ length: BLIP_SLOTS }, () => ({ x: 0, z: 0, life: 0 })),
  );

  /* ── Precomputed geometries ── */

  /* Disk platter */
  const diskEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(DISK_R, DISK_R, 0.16, 48)),
    [],
  );

  /* Concentric range rings + radial sectors on top face */
  const diskSurfaceGeo = useMemo(() => {
    const verts: number[] = [];
    const Y = 0.09;

    /* 4 range rings */
    [0.27, 0.50, 0.73, 0.96].forEach(frac => {
      const r = frac * DISK_R;
      for (let i = 0; i < 48; i++) {
        const a0 = (i / 48) * Math.PI * 2;
        const a1 = ((i + 1) / 48) * Math.PI * 2;
        verts.push(r * Math.cos(a0), Y, r * Math.sin(a0));
        verts.push(r * Math.cos(a1), Y, r * Math.sin(a1));
      }
    });

    /* 12 radial sectors */
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      verts.push(0.23 * Math.cos(a), Y, 0.23 * Math.sin(a));
      verts.push(DISK_R * 0.97 * Math.cos(a), Y, DISK_R * 0.97 * Math.sin(a));
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Sweep arm — single line from origin to disk edge */
  const sweepLineGeo = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute(
      'position',
      new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, DISK_R], 3),
    );
    return geo;
  }, []);

  /* Sweep trail — 24 fanning lines behind the sweep arm */
  const sweepTrailGeo = useMemo(() => {
    const verts: number[] = [];
    const TRAIL_ARC = Math.PI * 0.45;
    const COUNT = 24;
    for (let i = 1; i <= COUNT; i++) {
      const a = -(i / COUNT) * TRAIL_ARC;
      verts.push(0, 0, 0);
      verts.push(DISK_R * Math.sin(a), 0, DISK_R * Math.cos(a));
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Pedestal */
  const pedestalEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.11, 0.17, 0.52, 8)),
    [],
  );

  /* Base plate */
  const baseEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.78, 0.11, 0.78)),
    [],
  );

  /* Shared blip geometry */
  const blipGeo = useMemo(() => new THREE.SphereGeometry(0.045, 6, 6), []);

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Float */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.65) * 0.04;
    }

    /* Sweep rotation (1.4 rad/s) */
    sweepAngleRef.current += delta * 1.4;
    if (sweepGroupRef.current) {
      sweepGroupRef.current.rotation.y = sweepAngleRef.current;
    }

    /* Spawn blips */
    if (Math.random() < 0.045) {
      const slot = blipPool.current.findIndex(b => b.life <= 0);
      if (slot >= 0) {
        const a = sweepAngleRef.current + (Math.random() - 0.5) * 0.35;
        const r = (0.28 + Math.random() * 0.62) * DISK_R;
        blipPool.current[slot] = { x: r * Math.sin(a), z: r * Math.cos(a), life: 1.0 };
      }
    }

    /* Age blips */
    blipPool.current.forEach(b => { if (b.life > 0) b.life -= delta * 0.7; });

    /* Sync blip meshes */
    if (blipsGroupRef.current) {
      blipsGroupRef.current.children.forEach((child, i) => {
        const b = blipPool.current[i];
        const mesh = child as THREE.Mesh;
        const mat = mesh.material as THREE.MeshBasicMaterial;
        if (b !== undefined && b.life > 0) {
          mesh.position.set(b.x, 0.09, b.z);
          mat.opacity = b.life * 0.92;
        } else {
          mat.opacity = 0;
        }
      });
    }
  });

  return (
    /* Tilt to show dish face — 50° toward viewer */
    <group ref={groupRef} rotation={[-0.88, 0.25, 0]}>

      {/* ── Base plate ── */}
      <group position={[0, -0.98, 0]}>
        <mesh>
          <boxGeometry args={[0.78, 0.11, 0.78]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Pedestal ── */}
      <group position={[0, -0.7, 0]}>
        <mesh>
          <cylinderGeometry args={[0.11, 0.17, 0.52, 8]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.12} toneMapped={false} />
        </mesh>
        <lineSegments geometry={pedestalEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Disk platter ── */}
      <group position={[0, -0.38, 0]}>
        <mesh>
          <cylinderGeometry args={[DISK_R, DISK_R, 0.16, 48]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={diskEdges}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
        </lineSegments>

        {/* Surface rings + sectors */}
        <lineSegments geometry={diskSurfaceGeo}>
          <lineBasicMaterial color={CYAN} transparent opacity={0.22} />
        </lineSegments>

        {/* Center hub */}
        <mesh position={[0, 0.09, 0]}>
          <sphereGeometry args={[0.07, 8, 8]} />
          <meshBasicMaterial color={CYAN} transparent opacity={0.9} toneMapped={false} />
        </mesh>

        {/* Sweep group — rotates around Y */}
        <group ref={sweepGroupRef} position={[0, 0.09, 0]}>
          <lineSegments geometry={sweepLineGeo}>
            <lineBasicMaterial color={CYAN} transparent opacity={0.95} />
          </lineSegments>
          <lineSegments geometry={sweepTrailGeo}>
            <lineBasicMaterial color={CYAN} transparent opacity={0.28} />
          </lineSegments>
        </group>

        {/* Blip pool */}
        <group ref={blipsGroupRef}>
          {Array.from({ length: BLIP_SLOTS }, (_, i) => (
            <mesh key={i} geometry={blipGeo} position={[0, 0.09, 0]}>
              <meshBasicMaterial color={CYAN} transparent opacity={0} toneMapped={false} />
            </mesh>
          ))}
        </group>
      </group>
    </group>
  );
}

export const SearchProgress: React.FC<SearchProgressProps> = ({ label = 'Searching...' }) => (
  <div className="search-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={4.8} cameraY={1.2} fov={48}>
        <SonarConsole />
      </QueryScene>
    </div>
    <div className="search-progress-label">{label}</div>
  </div>
);
