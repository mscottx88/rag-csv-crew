/**
 * Database — 3D mainframe tower inspired by the IBM eServer i5 520.
 * Semi-transparent solid neon orange (#ff6600) with Bloom glow.
 *
 * Features: tall tower chassis, 8 hot-swap disk drive bays on the front,
 * media bay slots, operator panel with animated status LEDs, side vents,
 * and a base plate.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const ORANGE = '#ff6600';
const LED_COUNT = 4;
const DRIVE_COUNT = 8;

/* ── Tower dimensions ── */
const CW = 1.1;   // chassis width
const CH = 2.5;    // chassis height
const CD = 0.75;   // chassis depth

interface DatabaseProps {
  hovered: boolean;
}

export const Database: React.FC<DatabaseProps> = ({ hovered }) => {
  const groupRef = useRef<THREE.Group>(null);
  const ledsRef = useRef<THREE.Group>(null);
  const driveLightsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  /* ── Edge outlines ── */
  const chassisEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CW, CH, CD);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const baseEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CW + 0.2, 0.07, CD + 0.1);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── Front-panel detail lines ── */
  const panelLinesGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = CD / 2 + 0.01;         // just in front of chassis
    const hw = CW / 2 - 0.1;          // bay area half-width
    const bayH = 0.16;                 // individual bay height
    const bayGap = 0.03;              // gap between bays
    const bayStep = bayH + bayGap;
    const bayAreaTop = 0.35;           // top of drive bay area
    const bayAreaBot = bayAreaTop - DRIVE_COUNT * bayStep;

    // Horizontal drive bay separator lines (top and bottom of each bay)
    for (let i = 0; i <= DRIVE_COUNT; i++) {
      const y = bayAreaTop - i * bayStep;
      verts.push(-hw, y, fz, hw, y, fz);
    }

    // Vertical borders for drive bay area
    verts.push(-hw, bayAreaBot, fz, -hw, bayAreaTop, fz);
    verts.push(hw, bayAreaBot, fz, hw, bayAreaTop, fz);

    // Media bays — two wider slots above the drive area
    const mediaTop = bayAreaTop + 0.12;
    const mediaBot = mediaTop + 0.38;
    const mhw = hw * 0.9;
    // Slot divider
    verts.push(-mhw, mediaTop, fz, mhw, mediaTop, fz);
    verts.push(-mhw, mediaTop + 0.18, fz, mhw, mediaTop + 0.18, fz);
    verts.push(-mhw, mediaBot, fz, mhw, mediaBot, fz);
    // Vertical borders
    verts.push(-mhw, mediaTop, fz, -mhw, mediaBot, fz);
    verts.push(mhw, mediaTop, fz, mhw, mediaBot, fz);

    // Operator panel — small rectangle near the very top
    const opCy = CH / 2 - 0.18;
    const opHH = 0.1;
    const opHW = 0.25;
    verts.push(-opHW, opCy - opHH, fz, opHW, opCy - opHH, fz);
    verts.push(-opHW, opCy + opHH, fz, opHW, opCy + opHH, fz);
    verts.push(-opHW, opCy - opHH, fz, -opHW, opCy + opHH, fz);
    verts.push(opHW, opCy - opHH, fz, opHW, opCy + opHH, fz);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* ── Side vent lines ── */
  const ventLinesGeo = useMemo(() => {
    const verts: number[] = [];
    const sx = CW / 2 + 0.01;
    const ventCount = 8;
    const startY = -0.7;
    const spacing = 0.2;
    const halfD = CD / 2 - 0.12;

    for (let i = 0; i < ventCount; i++) {
      const y = startY + i * spacing;
      // Right side
      verts.push(sx, y, -halfD, sx, y, halfD);
      // Left side
      verts.push(-sx, y, -halfD, -sx, y, halfD);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* ── Drive bay solid fills (for semi-transparent body on each slot) ── */
  const bayStep = 0.16 + 0.03;
  const bayAreaTop = 0.35;

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    if (!groupRef.current) return;

    timeRef.current += delta;

    // Subtle float
    groupRef.current.position.y = Math.sin(timeRef.current * 0.8) * 0.04;

    // Operator panel LED animation
    if (ledsRef.current) {
      ledsRef.current.children.forEach((led, i) => {
        const phase = timeRef.current * (hovered ? 3 : 1.5) + i * 1.2;
        const brightness = 0.5 + Math.sin(phase) * 0.5;
        const mat = (led as THREE.Mesh).material as THREE.MeshBasicMaterial;
        mat.opacity = brightness * (hovered ? 1.0 : 0.7);
      });
    }

    // Drive bay activity light animation
    if (driveLightsRef.current) {
      driveLightsRef.current.children.forEach((light, i) => {
        const phase = timeRef.current * (hovered ? 5 : 1.2) + i * 0.8;
        const active = Math.sin(phase) > 0.3;
        const mat = (light as THREE.Mesh).material as THREE.MeshBasicMaterial;
        mat.opacity = active ? (hovered ? 0.95 : 0.5) : 0.05;
      });
    }
  });

  const fz = CD / 2 + 0.01;
  const opCy = CH / 2 - 0.18;

  return (
    <group ref={groupRef}>
      {/* ── Main chassis — solid semi-transparent ── */}
      <mesh>
        <boxGeometry args={[CW, CH, CD]} />
        <meshBasicMaterial
          color={ORANGE}
          transparent
          opacity={hovered ? 0.15 : 0.08}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>
      <lineSegments geometry={chassisEdges}>
        <lineBasicMaterial color={ORANGE} transparent opacity={0.65} />
      </lineSegments>

      {/* ── Base plate ── */}
      <group position={[0, -CH / 2 - 0.035, 0]}>
        <mesh>
          <boxGeometry args={[CW + 0.2, 0.07, CD + 0.1]} />
          <meshBasicMaterial
            color={ORANGE}
            transparent
            opacity={hovered ? 0.3 : 0.2}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={ORANGE} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Front panel detail lines ── */}
      <lineSegments geometry={panelLinesGeo}>
        <lineBasicMaterial color={ORANGE} transparent opacity={0.4} />
      </lineSegments>

      {/* ── Drive bay solid fills ── */}
      {Array.from({ length: DRIVE_COUNT }, (_, i) => (
        <mesh
          key={i}
          position={[0, bayAreaTop - i * bayStep - 0.08, fz]}
        >
          <boxGeometry args={[CW - 0.2, 0.14, 0.01]} />
          <meshBasicMaterial
            color={ORANGE}
            transparent
            opacity={hovered ? 0.1 : 0.04}
            toneMapped={false}
          />
        </mesh>
      ))}

      {/* ── Side vent lines ── */}
      <lineSegments geometry={ventLinesGeo}>
        <lineBasicMaterial color={ORANGE} transparent opacity={0.2} />
      </lineSegments>

      {/* ── Operator panel status LEDs ── */}
      <group ref={ledsRef}>
        {Array.from({ length: LED_COUNT }, (_, i) => (
          <mesh
            key={i}
            position={[-0.12 + i * 0.08, opCy, fz + 0.01]}
          >
            <sphereGeometry args={[0.022, 8, 8]} />
            <meshBasicMaterial
              color={ORANGE}
              transparent
              opacity={0.7}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      {/* ── Drive bay activity lights ── */}
      <group ref={driveLightsRef}>
        {Array.from({ length: DRIVE_COUNT }, (_, i) => (
          <mesh
            key={i}
            position={[
              CW / 2 - 0.14,
              bayAreaTop - i * bayStep - 0.08,
              fz + 0.01,
            ]}
          >
            <sphereGeometry args={[0.018, 6, 6]} />
            <meshBasicMaterial
              color={ORANGE}
              transparent
              opacity={0.5}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
};
