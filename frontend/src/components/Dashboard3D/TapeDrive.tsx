/**
 * DASD — 3D Direct Access Storage Device for the Upload card.
 * Inspired by the IBM 3380 / 3390 disk storage units. Semi-transparent
 * solid neon green (#39ff14) with Bloom glow.
 *
 * Features: upright storage cabinet with cartridge bay slots, a cartridge
 * that animates being inserted and loaded by an internal arm mechanism,
 * spare cartridges resting on top, operator panel with flashing LEDs,
 * side vents, and base plate.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const GREEN = '#39ff14';
const LED_COUNT = 6;
const BAY_COUNT = 4;

/* ── Cabinet dimensions ── */
const CW = 1.6;   // cabinet width
const CH = 2.4;    // cabinet height
const CD = 0.7;    // cabinet depth

/* ── Cartridge dimensions ── */
const CART_W = 0.55;
const CART_H = 0.14;
const CART_D = 0.35;

/* ── Bay layout ── */
const BAY_TOP = 0.5;      // top of bay area
const BAY_H = 0.22;       // height per bay (including gap)
const BAY_HW = CW / 2 - 0.12; // bay half-width

interface TapeDriveProps {
  hovered: boolean;
}

export const TapeDrive: React.FC<TapeDriveProps> = ({ hovered }) => {
  const groupRef = useRef<THREE.Group>(null);
  const cartridgeRef = useRef<THREE.Group>(null);
  const armRef = useRef<THREE.Group>(null);
  const ledsRef = useRef<THREE.Group>(null);
  const bayLedsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  /* ── Edge outlines ── */
  const cabinetEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CW, CH, CD);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const baseEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CW + 0.15, 0.07, CD + 0.1);
    return new THREE.EdgesGeometry(geo);
  }, []);

  const cartEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CART_W, CART_H, CART_D);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── Spare cartridge edges (slightly different size for variety) ── */
  const spareEdges = useMemo(() => {
    const geo = new THREE.BoxGeometry(CART_W * 0.9, CART_H * 0.85, CART_D * 0.9);
    return new THREE.EdgesGeometry(geo);
  }, []);

  /* ── Front panel detail lines ── */
  const panelGeo = useMemo(() => {
    const v: number[] = [];
    const fz = CD / 2 + 0.01;

    // Cartridge bay outlines
    for (let i = 0; i < BAY_COUNT; i++) {
      const y = BAY_TOP - i * BAY_H;
      const yb = y - CART_H - 0.02;
      // Bay rectangle
      v.push(-BAY_HW, y, fz, BAY_HW, y, fz);
      v.push(-BAY_HW, yb, fz, BAY_HW, yb, fz);
      v.push(-BAY_HW, yb, fz, -BAY_HW, y, fz);
      v.push(BAY_HW, yb, fz, BAY_HW, y, fz);

      // Internal rail guides (two horizontal lines inside each bay)
      const railY1 = y - 0.03;
      const railY2 = yb + 0.03;
      v.push(-BAY_HW + 0.04, railY1, fz, BAY_HW - 0.04, railY1, fz);
      v.push(-BAY_HW + 0.04, railY2, fz, BAY_HW - 0.04, railY2, fz);
    }

    // Divider below bays
    const divY = BAY_TOP - BAY_COUNT * BAY_H - 0.05;
    v.push(-BAY_HW, divY, fz, BAY_HW, divY, fz);

    // Operator panel rectangle (below bays)
    const opTop = divY - 0.08;
    const opBot = opTop - 0.25;
    const opHW = 0.35;
    v.push(-opHW, opTop, fz, opHW, opTop, fz);
    v.push(-opHW, opBot, fz, opHW, opBot, fz);
    v.push(-opHW, opBot, fz, -opHW, opTop, fz);
    v.push(opHW, opBot, fz, opHW, opTop, fz);

    // Inner panel label area
    v.push(-opHW + 0.05, opTop - 0.06, fz, opHW - 0.05, opTop - 0.06, fz);

    // Loader arm track (vertical line on right side inside cabinet)
    const trackX = BAY_HW - 0.08;
    const trackTop = BAY_TOP + 0.05;
    const trackBot = BAY_TOP - BAY_COUNT * BAY_H;
    v.push(trackX, trackBot, fz, trackX, trackTop, fz);
    v.push(trackX + 0.04, trackBot, fz, trackX + 0.04, trackTop, fz);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Side vent lines ── */
  const ventGeo = useMemo(() => {
    const v: number[] = [];
    const sx = CW / 2 + 0.01;
    const halfD = CD / 2 - 0.1;
    for (let i = 0; i < 6; i++) {
      const y = -0.6 + i * 0.2;
      v.push(sx, y, -halfD, sx, y, halfD);
      v.push(-sx, y, -halfD, -sx, y, halfD);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Loader arm geometry (horizontal bar with gripper) ── */
  const armGeo = useMemo(() => {
    const v: number[] = [];
    // Horizontal arm bar
    v.push(-0.3, 0, 0, 0.1, 0, 0);
    v.push(-0.3, 0.04, 0, 0.1, 0.04, 0);
    v.push(-0.3, 0, 0, -0.3, 0.04, 0);
    v.push(0.1, 0, 0, 0.1, 0.04, 0);
    // Gripper fingers at left end
    v.push(-0.3, -0.03, 0, -0.3, 0.07, 0);
    v.push(-0.35, -0.02, 0, -0.35, 0.06, 0);
    v.push(-0.35, -0.02, 0, -0.3, -0.03, 0);
    v.push(-0.35, 0.06, 0, -0.3, 0.07, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Cartridge detail lines (label area + handle groove) ── */
  const cartDetailGeo = useMemo(() => {
    const v: number[] = [];
    const fz = CART_D / 2 + 0.005;
    // Label rectangle on front face
    v.push(-CART_W / 2 + 0.04, -CART_H / 2 + 0.02, fz,
      CART_W / 2 - 0.04, -CART_H / 2 + 0.02, fz);
    v.push(-CART_W / 2 + 0.04, CART_H / 2 - 0.02, fz,
      CART_W / 2 - 0.04, CART_H / 2 - 0.02, fz);
    v.push(-CART_W / 2 + 0.04, -CART_H / 2 + 0.02, fz,
      -CART_W / 2 + 0.04, CART_H / 2 - 0.02, fz);
    v.push(CART_W / 2 - 0.04, -CART_H / 2 + 0.02, fz,
      CART_W / 2 - 0.04, CART_H / 2 - 0.02, fz);
    // Handle groove on top
    v.push(-0.12, CART_H / 2 + 0.001, -CART_D / 2 + 0.05,
      0.12, CART_H / 2 + 0.001, -CART_D / 2 + 0.05);
    v.push(-0.12, CART_H / 2 + 0.001, CART_D / 2 - 0.05,
      0.12, CART_H / 2 + 0.001, CART_D / 2 - 0.05);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Animation ── */
  useFrame((_, delta) => {
    if (!groupRef.current) return;
    timeRef.current += delta;

    // Subtle float
    groupRef.current.position.y = Math.sin(timeRef.current * 0.8) * 0.04;

    const cycleDuration = hovered ? 3.0 : 6.0;
    const t = (timeRef.current % cycleDuration) / cycleDuration; // 0→1 cycle

    const fz = CD / 2 + 0.01;
    const targetBay = 1; // insert into bay index 1
    const bayY = BAY_TOP - targetBay * BAY_H - CART_H / 2 - 0.01;
    const armTrackX = BAY_HW - 0.06;

    // Cartridge animation: slide in from right → settle in bay
    if (cartridgeRef.current) {
      if (t < 0.25) {
        // Phase 1: Cartridge slides in from right
        const p = t / 0.25;
        const eased = 1 - Math.pow(1 - p, 3); // ease-out
        const startX = CW / 2 + CART_W;
        const endX = 0;
        cartridgeRef.current.position.set(
          startX + (endX - startX) * eased,
          bayY,
          fz + CART_D / 2,
        );
        cartridgeRef.current.visible = true;
      } else if (t < 0.45) {
        // Phase 2: Arm grabs and pushes cartridge deeper into cabinet
        const p = (t - 0.25) / 0.2;
        const eased = p * p; // ease-in
        cartridgeRef.current.position.set(
          0,
          bayY,
          fz + CART_D / 2 - eased * (CD * 0.5),
        );
      } else if (t < 0.85) {
        // Phase 3: Cartridge seated inside, LEDs flash (reading data)
        cartridgeRef.current.position.set(0, bayY, fz + CART_D / 2 - CD * 0.5);
      } else {
        // Phase 4: Cartridge ejected / hidden, reset
        cartridgeRef.current.visible = false;
      }
    }

    // Loader arm animation
    if (armRef.current) {
      if (t < 0.15) {
        // Arm at home (top position)
        armRef.current.position.set(armTrackX, BAY_TOP + 0.03, fz + 0.02);
      } else if (t < 0.25) {
        // Arm descends to target bay
        const p = (t - 0.15) / 0.1;
        const homeY = BAY_TOP + 0.03;
        armRef.current.position.set(
          armTrackX,
          homeY + (bayY - homeY) * p,
          fz + 0.02,
        );
      } else if (t < 0.45) {
        // Arm at bay, pushing cartridge
        armRef.current.position.set(armTrackX, bayY, fz + 0.02);
      } else if (t < 0.55) {
        // Arm returns to home
        const p = (t - 0.45) / 0.1;
        armRef.current.position.set(
          armTrackX,
          bayY + (BAY_TOP + 0.03 - bayY) * p,
          fz + 0.02,
        );
      } else {
        // Arm idle at home
        armRef.current.position.set(armTrackX, BAY_TOP + 0.03, fz + 0.02);
      }
    }

    // Operator panel LEDs (rapid activity during read phase)
    if (ledsRef.current) {
      const isReading = t >= 0.45 && t < 0.85;
      ledsRef.current.children.forEach((led, i) => {
        const mat = (led as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (isReading) {
          const phase = timeRef.current * (hovered ? 8 : 4) + i * 0.9;
          const active = Math.sin(phase) > 0.1;
          mat.opacity = active ? (hovered ? 0.95 : 0.7) : 0.08;
        } else {
          // Idle: gentle breathing on first LED only
          if (i === 0) {
            mat.opacity = 0.5 + Math.sin(timeRef.current * 1.5) * 0.3;
          } else {
            mat.opacity = 0.08;
          }
        }
      });
    }

    // Bay activity LEDs (one per bay, active bay lights up during load/read)
    if (bayLedsRef.current) {
      bayLedsRef.current.children.forEach((led, i) => {
        const mat = (led as THREE.Mesh).material as THREE.MeshBasicMaterial;
        if (i === targetBay && t >= 0.25 && t < 0.85) {
          const phase = timeRef.current * (hovered ? 6 : 2.5);
          mat.opacity = 0.5 + Math.sin(phase) * 0.45;
        } else {
          mat.opacity = 0.06;
        }
      });
    }
  });

  const fz = CD / 2 + 0.01;
  const opDivY = BAY_TOP - BAY_COUNT * BAY_H - 0.05;
  const opTop = opDivY - 0.08;

  return (
    <group ref={groupRef}>
      {/* ── Main cabinet ── */}
      <mesh>
        <boxGeometry args={[CW, CH, CD]} />
        <meshBasicMaterial
          color={GREEN}
          transparent
          opacity={hovered ? 0.15 : 0.08}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>
      <lineSegments geometry={cabinetEdges}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.65} />
      </lineSegments>

      {/* ── Base plate ── */}
      <group position={[0, -CH / 2 - 0.035, 0]}>
        <mesh>
          <boxGeometry args={[CW + 0.15, 0.07, CD + 0.1]} />
          <meshBasicMaterial
            color={GREEN}
            transparent
            opacity={hovered ? 0.3 : 0.2}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={baseEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* ── Front panel detail lines ── */}
      <lineSegments geometry={panelGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.4} />
      </lineSegments>

      {/* ── Bay solid fills ── */}
      {Array.from({ length: BAY_COUNT }, (_, i) => (
        <mesh
          key={i}
          position={[0, BAY_TOP - i * BAY_H - CART_H / 2 - 0.01, fz]}
        >
          <boxGeometry args={[CW - 0.24, CART_H + 0.01, 0.01]} />
          <meshBasicMaterial
            color={GREEN}
            transparent
            opacity={hovered ? 0.08 : 0.03}
            toneMapped={false}
          />
        </mesh>
      ))}

      {/* ── Bay activity LEDs (one per bay, right side) ── */}
      <group ref={bayLedsRef}>
        {Array.from({ length: BAY_COUNT }, (_, i) => (
          <mesh
            key={i}
            position={[
              BAY_HW - 0.04,
              BAY_TOP - i * BAY_H - CART_H / 2 - 0.01,
              fz + 0.01,
            ]}
          >
            <sphereGeometry args={[0.02, 6, 6]} />
            <meshBasicMaterial
              color={GREEN}
              transparent
              opacity={0.06}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>

      {/* ── Animating cartridge ── */}
      <group ref={cartridgeRef}>
        <mesh>
          <boxGeometry args={[CART_W, CART_H, CART_D]} />
          <meshBasicMaterial
            color={GREEN}
            transparent
            opacity={hovered ? 0.3 : 0.18}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>
        <lineSegments geometry={cartEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.6} />
        </lineSegments>
        <lineSegments geometry={cartDetailGeo}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.35} />
        </lineSegments>
      </group>

      {/* ── Loader arm ── */}
      <group ref={armRef}>
        <lineSegments geometry={armGeo}>
          <lineBasicMaterial color={GREEN} transparent opacity={hovered ? 0.6 : 0.4} />
        </lineSegments>
      </group>

      {/* ── Spare cartridges on top of cabinet ── */}
      {[
        { x: -0.25, z: 0, rot: 0.1 },
        { x: 0.2, z: -0.05, rot: -0.15 },
      ].map((spare, i) => (
        <group
          key={i}
          position={[spare.x, CH / 2 + CART_H * 0.85 / 2 + 0.01, spare.z]}
          rotation={[0, spare.rot, 0]}
        >
          <mesh>
            <boxGeometry args={[CART_W * 0.9, CART_H * 0.85, CART_D * 0.9]} />
            <meshBasicMaterial
              color={GREEN}
              transparent
              opacity={hovered ? 0.2 : 0.1}
              side={THREE.DoubleSide}
              toneMapped={false}
            />
          </mesh>
          <lineSegments geometry={spareEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.35} />
          </lineSegments>
        </group>
      ))}

      {/* ── Side vent lines ── */}
      <lineSegments geometry={ventGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.2} />
      </lineSegments>

      {/* ── Operator panel LEDs ── */}
      <group ref={ledsRef}>
        {Array.from({ length: LED_COUNT }, (_, i) => (
          <mesh
            key={i}
            position={[
              -0.25 + i * 0.1,
              opTop - 0.04,
              fz + 0.01,
            ]}
          >
            <sphereGeometry args={[0.02, 8, 8]} />
            <meshBasicMaterial
              color={GREEN}
              transparent
              opacity={0.08}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
};
