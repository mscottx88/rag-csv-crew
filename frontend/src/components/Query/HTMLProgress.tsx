/**
 * HTMLProgress — 3D Selectric typewriter terminal for "Formatting output..." phase.
 * Inspired by the IBM 2741 Selectric Communications Terminal.
 *
 * Features: low-profile landscape chassis, horizontal platen roller at the
 * top with paper emerging upward, a type-ball sphere on a carriage that
 * travels left to right (then snaps back), carriage motion driving paper
 * advance on each return, keyboard key grid on the lower front face,
 * and a status LED that pulses with each keystroke.
 *
 * Color: green (#39ff14)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './HTMLProgress.css';

interface HTMLProgressProps {
  label?: string;
}

const GREEN = '#39ff14';

/* ── Machine dimensions ── */
const BW = 2.2;   // body width
const BH = 0.72;  // body height (low profile)
const BD = 1.3;   // body depth

/* ── IBM 2741 Selectric Terminal 3D object ── */
function Selectric(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const carriageRef = useRef<THREE.Group>(null);
  const typeBallRef = useRef<THREE.Mesh>(null);
  const paperRef = useRef<THREE.Mesh>(null);
  const ledRef = useRef<THREE.Mesh>(null);
  const timeRef = useRef(0);
  const carriagePosRef = useRef(0); // 0 = left, 1 = right

  /* ── Precomputed geometries ── */

  const bodyEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(BW, BH, BD)),
    [],
  );

  /* Platen roller (horizontal cylinder spanning machine width) */
  const rollerEdges = useMemo(
    () => new THREE.EdgesGeometry(
      new THREE.CylinderGeometry(0.07, 0.07, BW * 0.9, 16),
    ),
    [],
  );

  /* Carriage rail (thin rod above the body) */
  const railEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(BW * 0.85, 0.03, 0.03)),
    [],
  );

  /* Carriage body */
  const carriageEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.28, 0.18, 0.15)),
    [],
  );

  /* Paper geometry */
  const paperEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(BW * 0.72, 0.7, 0.008)),
    [],
  );

  /* Keyboard grid */
  const keyboardGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = -BD / 2 + 0.01; // front face (negative Z since deep chassis)
    const kbW = BW - 0.3;
    const kbH = BH * 0.6;
    const kbBottom = -BH / 2 + 0.04;
    const cols = 12;
    const rows = 4;
    const kw = kbW / cols;
    const kh = kbH / rows;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = -kbW / 2 + c * kw + kw * 0.1;
        const y = kbBottom + r * kh + kh * 0.12;
        const w = kw * 0.78;
        const h = kh * 0.72;
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

  /* Control panel (right side of body top) */
  const controlPanelGeo = useMemo(() => {
    const verts: number[] = [];
    const topY = BH / 2 + 0.01;
    const sx = BW / 2 - 0.35;
    const ex = BW / 2 - 0.04;
    const z0 = -BD / 2 + 0.1;
    const z1 = BD / 2 - 0.1;
    verts.push(sx, topY, z0, ex, topY, z0);
    verts.push(ex, topY, z0, ex, topY, z1);
    verts.push(ex, topY, z1, sx, topY, z1);
    verts.push(sx, topY, z1, sx, topY, z0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Base plate */
  const baseEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(BW + 0.18, 0.07, BD + 0.1)),
    [],
  );

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Float + very slow Y oscillation */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.58) * 0.04;
      groupRef.current.rotation.y = Math.sin(t * 0.19) * 0.2;
    }

    /* Carriage: travels left → right over 2s, snaps back in 0.3s */
    const period = 2.3;
    const phase = (t % period) / period;
    const travelFrac = Math.min(1, phase / 0.87); // 0→1 during travel
    const isReturning = phase > 0.87;

    carriagePosRef.current = isReturning
      ? 1 - (phase - 0.87) / 0.13 // fast snap back
      : travelFrac;

    const railHalf = BW * 0.85 / 2 - 0.14;
    const carriageX = -railHalf + carriagePosRef.current * railHalf * 2;

    if (carriageRef.current) {
      carriageRef.current.position.x = carriageX;
    }

    /* Type ball spins when moving (not during snap-back) */
    if (typeBallRef.current && !isReturning) {
      typeBallRef.current.rotation.y += delta * 8.0;
      typeBallRef.current.rotation.x += delta * 5.5;
    }

    /* Paper advances on each return */
    if (paperRef.current) {
      const paperRise = ((t * 0.35) % 1.0) * 0.4;
      paperRef.current.position.y = BH / 2 + 0.35 + paperRise;
    }

    /* LED pulses with each character */
    if (ledRef.current) {
      const mat = ledRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = !isReturning ? 0.5 + Math.abs(Math.sin(t * 12.0)) * 0.5 : 0.15;
    }
  });

  const topY = BH / 2;
  const railY = topY + 0.22;
  const rollerY = topY + 0.12;
  const paperZ = -BD / 2 + 0.05;

  return (
    <group ref={groupRef}>

      {/* ── Base plate ── */}
      <group position={[0, -BH / 2 - 0.035, 0]}>
        <mesh>
          <boxGeometry args={[BW + 0.18, 0.07, BD + 0.1]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Main body ── */}
      <mesh>
        <boxGeometry args={[BW, BH, BD]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.08} toneMapped={false} />
      </mesh>
      <lineSegments geometry={bodyEdges}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Keyboard grid ── */}
      <lineSegments geometry={keyboardGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.38} />
      </lineSegments>

      {/* ── Control panel (top-right) ── */}
      <lineSegments geometry={controlPanelGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.4} />
      </lineSegments>

      {/* ── Platen roller ── */}
      <group position={[0, rollerY, paperZ + 0.07]} rotation={[0, 0, Math.PI / 2]}>
        <mesh>
          <cylinderGeometry args={[0.07, 0.07, BW * 0.9, 16]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.2} toneMapped={false} />
        </mesh>
        <lineSegments geometry={rollerEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
        </lineSegments>
      </group>

      {/* ── Carriage rail ── */}
      <group position={[0, railY, paperZ + 0.04]}>
        <mesh>
          <boxGeometry args={[BW * 0.85, 0.03, 0.03]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.25} toneMapped={false} />
        </mesh>
        <lineSegments geometry={railEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.6} />
        </lineSegments>
      </group>

      {/* ── Carriage (slides along rail) ── */}
      <group ref={carriageRef} position={[0, railY + 0.02, paperZ + 0.04]}>
        <mesh>
          <boxGeometry args={[0.28, 0.18, 0.15]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.18} toneMapped={false} />
        </mesh>
        <lineSegments geometry={carriageEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.65} />
        </lineSegments>

        {/* Type ball (Selectric golf ball) */}
        <mesh ref={typeBallRef} position={[0, -0.05, 0.09]}>
          <sphereGeometry args={[0.085, 10, 10]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.35} toneMapped={false} />
        </mesh>
        {/* Type ball equator ring (makes it look like a Selectric element) */}
        <mesh position={[0, -0.05, 0.09]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.085, 0.012, 6, 20]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.65} toneMapped={false} />
        </mesh>
      </group>

      {/* ── Paper strip (rises upward) ── */}
      <mesh ref={paperRef} position={[0, topY + 0.35, paperZ]}>
        <boxGeometry args={[BW * 0.72, 0.7, 0.008]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <lineSegments geometry={paperEdges} position={[0, topY + 0.35, paperZ]}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.35} />
      </lineSegments>

      {/* ── Horizontal print lines on paper ── */}
      {[0, 0.12, 0.24, 0.36].map((dy, i) => (
        <mesh key={i} position={[0, topY + 0.2 + dy, paperZ - 0.001]}>
          <boxGeometry args={[BW * 0.62, 0.018, 0.001]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.22} toneMapped={false} />
        </mesh>
      ))}

      {/* ── Status LED ── */}
      <mesh ref={ledRef} position={[BW / 2 - 0.12, topY + 0.01, -BD / 2 + 0.35]}>
        <sphereGeometry args={[0.028, 8, 8]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.8} toneMapped={false} />
      </mesh>
    </group>
  );
}

export const HTMLProgress: React.FC<HTMLProgressProps> = ({ label = 'Formatting output...' }) => (
  <div className="html-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={4.8} cameraY={0.3} fov={52}>
        <Selectric />
      </QueryScene>
    </div>
    <div className="html-progress-label">{label}</div>
  </div>
);
