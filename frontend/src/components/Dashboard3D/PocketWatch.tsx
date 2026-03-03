/**
 * PocketWatch — Realistic 3D antique pocket watch for the History card.
 * Semi-transparent solid neon gold (#ffd700) with Bloom glow.
 *
 * Features: thick watch case ring, semi-transparent dial face with hour
 * markers and minute ticks, moving hour/minute/second hands, crown with
 * bail ring, decorative chain with catenary droop, visible gear outlines
 * rotating behind the face, seconds sub-dial.
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const GOLD = '#ffd700';

/* ── Watch dimensions ── */
const CASE_R = 1.2;       // outer case radius
const CASE_TUBE = 0.15;   // case ring tube thickness
const FACE_R = 1.05;      // dial face radius
const MARKER_INNER = 0.88; // hour marker inner radius
const MARKER_OUTER = 1.0;  // hour marker outer radius
const TICK_INNER = 0.95;   // minute tick inner radius
const TICK_OUTER = 1.0;    // minute tick outer radius

/* ── Hand lengths ── */
const HOUR_LEN = 0.5;
const MINUTE_LEN = 0.75;
const SECOND_LEN = 0.85;

/* ── Gear specs ── */
const GEARS = [
  { cx: 0.35, cy: -0.25, r: 0.18, teeth: 12, speed: 1.0 },
  { cx: -0.3, cy: 0.2, r: 0.25, teeth: 16, speed: -0.6 },
  { cx: 0.15, cy: 0.35, r: 0.12, teeth: 8, speed: 1.8 },
];

interface PocketWatchProps {
  hovered: boolean;
}

/** Circle outline in XY plane (paired line segments). */
function circleXY(cx: number, cy: number, r: number, segs = 32): number[] {
  const v: number[] = [];
  for (let i = 0; i < segs; i++) {
    const a0 = (i / segs) * Math.PI * 2;
    const a1 = ((i + 1) / segs) * Math.PI * 2;
    v.push(
      cx + Math.cos(a0) * r, cy + Math.sin(a0) * r, 0,
      cx + Math.cos(a1) * r, cy + Math.sin(a1) * r, 0,
    );
  }
  return v;
}

/** Gear outline: circle + triangular teeth at the perimeter. */
function gearOutline(cx: number, cy: number, r: number, teeth: number): number[] {
  const v: number[] = [];
  // Inner circle
  v.push(...circleXY(cx, cy, r * 0.6, 20));
  // Outer with teeth
  for (let i = 0; i < teeth; i++) {
    const a = (i / teeth) * Math.PI * 2;
    const aNext = ((i + 0.3) / teeth) * Math.PI * 2;
    const aMid = ((i + 0.15) / teeth) * Math.PI * 2;
    const aEnd = ((i + 0.5) / teeth) * Math.PI * 2;

    // Base of tooth
    v.push(
      cx + Math.cos(a) * r, cy + Math.sin(a) * r, 0,
      cx + Math.cos(aMid) * (r * 1.15), cy + Math.sin(aMid) * (r * 1.15), 0,
    );
    // Tip to end
    v.push(
      cx + Math.cos(aMid) * (r * 1.15), cy + Math.sin(aMid) * (r * 1.15), 0,
      cx + Math.cos(aNext) * r, cy + Math.sin(aNext) * r, 0,
    );
    // Valley between teeth
    v.push(
      cx + Math.cos(aNext) * r, cy + Math.sin(aNext) * r, 0,
      cx + Math.cos(aEnd) * r, cy + Math.sin(aEnd) * r, 0,
    );
  }
  return v;
}

export const PocketWatch: React.FC<PocketWatchProps> = ({ hovered }) => {
  const groupRef = useRef<THREE.Group>(null);
  const secondRef = useRef<THREE.Group>(null);
  const minuteRef = useRef<THREE.Group>(null);
  const hourRef = useRef<THREE.Group>(null);
  const gearsRef = useRef<THREE.Group>(null);
  const chainRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  /* ── Hour markers (12 radial lines, longer at 12/3/6/9) ── */
  const hourMarkersGeo = useMemo(() => {
    const v: number[] = [];
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2 - Math.PI / 2; // 12 o'clock at top
      const isCardinal = i % 3 === 0;
      const inner = isCardinal ? MARKER_INNER - 0.08 : MARKER_INNER;
      v.push(
        Math.cos(a) * inner, Math.sin(a) * inner, 0,
        Math.cos(a) * MARKER_OUTER, Math.sin(a) * MARKER_OUTER, 0,
      );
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Minute tick marks (60 tiny radial lines) ── */
  const minuteTicksGeo = useMemo(() => {
    const v: number[] = [];
    for (let i = 0; i < 60; i++) {
      if (i % 5 === 0) continue; // skip hour marker positions
      const a = (i / 60) * Math.PI * 2 - Math.PI / 2;
      v.push(
        Math.cos(a) * TICK_INNER, Math.sin(a) * TICK_INNER, 0,
        Math.cos(a) * TICK_OUTER, Math.sin(a) * TICK_OUTER, 0,
      );
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Clock hand geometries (line segments from center) ── */
  const hourHandGeo = useMemo(() => {
    // Thick hand: two parallel lines + tip
    const v: number[] = [];
    const w = 0.025;
    v.push(-w, 0, 0, -w, HOUR_LEN, 0);
    v.push(w, 0, 0, w, HOUR_LEN, 0);
    v.push(-w, HOUR_LEN, 0, 0, HOUR_LEN + 0.04, 0);
    v.push(w, HOUR_LEN, 0, 0, HOUR_LEN + 0.04, 0);
    // Small tail
    v.push(-w, 0, 0, 0, -0.08, 0);
    v.push(w, 0, 0, 0, -0.08, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  const minuteHandGeo = useMemo(() => {
    const v: number[] = [];
    const w = 0.018;
    v.push(-w, 0, 0, -w, MINUTE_LEN, 0);
    v.push(w, 0, 0, w, MINUTE_LEN, 0);
    v.push(-w, MINUTE_LEN, 0, 0, MINUTE_LEN + 0.03, 0);
    v.push(w, MINUTE_LEN, 0, 0, MINUTE_LEN + 0.03, 0);
    v.push(-w, 0, 0, 0, -0.06, 0);
    v.push(w, 0, 0, 0, -0.06, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  const secondHandGeo = useMemo(() => {
    const v: number[] = [];
    v.push(0, -0.1, 0, 0, SECOND_LEN, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Sub-dial at 6 o'clock ── */
  const subDialGeo = useMemo(() => {
    const v = circleXY(0, -0.45, 0.2, 24);
    // Tiny tick marks around sub-dial
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * Math.PI * 2;
      v.push(
        Math.cos(a) * 0.17, -0.45 + Math.sin(a) * 0.17, 0,
        Math.cos(a) * 0.2, -0.45 + Math.sin(a) * 0.2, 0,
      );
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ── Gear outlines ── */
  const gearGeos = useMemo(() =>
    GEARS.map(g => {
      const v = gearOutline(0, 0, g.r, g.teeth);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
      return geo;
    }), []);

  /* ── Chain links (catenary curve from bail) ── */
  const chainGeo = useMemo(() => {
    const v: number[] = [];
    const links = 10;
    const startX = 0;
    const startY = CASE_R + 0.35; // just above crown

    for (let i = 0; i < links; i++) {
      const t = i / links;
      const x = startX + t * 0.8;
      // Catenary droop
      const y = startY - t * 0.15 - Math.sin(t * Math.PI) * 0.25;

      const tNext = (i + 1) / links;
      const xNext = startX + tNext * 0.8;
      const yNext = startY - tNext * 0.15 - Math.sin(tNext * Math.PI) * 0.25;

      // Oval link shape (simplified as a small diamond)
      const lw = 0.03;
      const lh = 0.025;
      const mx = (x + xNext) / 2;
      const my = (y + yNext) / 2;

      if (i % 2 === 0) {
        // Horizontal oval
        v.push(mx - lw, my, 0, mx + lw, my, 0);
        v.push(mx, my - lh, 0, mx, my + lh, 0);
      }
      // Link connections
      v.push(x, y, 0, xNext, yNext, 0);
    }
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

    const speedMul = hovered ? 8 : 1;

    // Second hand — discrete tick or smooth sweep
    if (secondRef.current) {
      const secAngle = -(timeRef.current * speedMul) * (Math.PI / 30);
      secondRef.current.rotation.z = secAngle;
    }

    // Minute hand
    if (minuteRef.current) {
      const minAngle = -(timeRef.current * speedMul) * (Math.PI / 1800);
      minuteRef.current.rotation.z = minAngle;
    }

    // Hour hand
    if (hourRef.current) {
      const hrAngle = -(timeRef.current * speedMul) * (Math.PI / 21600);
      hourRef.current.rotation.z = hrAngle;
    }

    // Gear rotation
    if (gearsRef.current) {
      gearsRef.current.children.forEach((gear, i) => {
        const g = GEARS[i];
        if (g) {
          gear.rotation.z += delta * g.speed * (hovered ? 3 : 1);
        }
      });
    }

    // Chain sway
    if (chainRef.current) {
      chainRef.current.rotation.z = Math.sin(timeRef.current * 0.6) * 0.03;
    }
  });

  return (
    <group ref={groupRef} rotation={[0.1, 0, 0.15]}>
      {/* ── Watch case ring ── */}
      <mesh>
        <torusGeometry args={[CASE_R, CASE_TUBE, 12, 48]} />
        <meshBasicMaterial
          color={GOLD}
          transparent
          opacity={hovered ? 0.4 : 0.25}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>

      {/* ── Case back plate ── */}
      <mesh position={[0, 0, -0.08]}>
        <circleGeometry args={[CASE_R, 48]} />
        <meshBasicMaterial
          color={GOLD}
          transparent
          opacity={hovered ? 0.08 : 0.04}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>

      {/* ── Visible gears (behind face, rotating) ── */}
      <group ref={gearsRef} position={[0, 0, -0.04]}>
        {GEARS.map((g, i) => {
          const geo = gearGeos[i];
          return geo ? (
            <group key={i} position={[g.cx, g.cy, 0]}>
              <lineSegments geometry={geo}>
                <lineBasicMaterial
                  color={GOLD}
                  transparent
                  opacity={hovered ? 0.25 : 0.12}
                />
              </lineSegments>
            </group>
          ) : null;
        })}
      </group>

      {/* ── Watch face (very faint fill) ── */}
      <mesh position={[0, 0, 0.01]}>
        <circleGeometry args={[FACE_R, 48]} />
        <meshBasicMaterial
          color={GOLD}
          transparent
          opacity={hovered ? 0.06 : 0.03}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>

      {/* ── Hour markers ── */}
      <lineSegments geometry={hourMarkersGeo} position={[0, 0, 0.02]}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.65} />
      </lineSegments>

      {/* ── Minute tick marks ── */}
      <lineSegments geometry={minuteTicksGeo} position={[0, 0, 0.02]}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.3} />
      </lineSegments>

      {/* ── Sub-dial at 6 o'clock ── */}
      <lineSegments geometry={subDialGeo} position={[0, 0, 0.02]}>
        <lineBasicMaterial color={GOLD} transparent opacity={0.3} />
      </lineSegments>

      {/* ── Clock hands ── */}
      <group position={[0, 0, 0.03]}>
        {/* Hour hand */}
        <group ref={hourRef}>
          <lineSegments geometry={hourHandGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={0.7} />
          </lineSegments>
        </group>

        {/* Minute hand */}
        <group ref={minuteRef}>
          <lineSegments geometry={minuteHandGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={0.6} />
          </lineSegments>
        </group>

        {/* Second hand */}
        <group ref={secondRef}>
          <lineSegments geometry={secondHandGeo}>
            <lineBasicMaterial color={GOLD} transparent opacity={0.5} />
          </lineSegments>
        </group>

        {/* Center pin */}
        <mesh>
          <sphereGeometry args={[0.04, 8, 8]} />
          <meshBasicMaterial
            color={GOLD}
            transparent
            opacity={hovered ? 0.6 : 0.4}
            toneMapped={false}
          />
        </mesh>
      </group>

      {/* ── Crown (winding knob) at 12 o'clock ── */}
      <group position={[0, CASE_R + 0.12, 0]}>
        <mesh>
          <cylinderGeometry args={[0.07, 0.06, 0.14, 10]} />
          <meshBasicMaterial
            color={GOLD}
            transparent
            opacity={hovered ? 0.4 : 0.25}
            toneMapped={false}
          />
        </mesh>
      </group>

      {/* ── Bail ring (connects crown to chain) ── */}
      <group position={[0, CASE_R + 0.25, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <mesh>
          <torusGeometry args={[0.06, 0.018, 8, 16]} />
          <meshBasicMaterial
            color={GOLD}
            transparent
            opacity={hovered ? 0.45 : 0.3}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>
      </group>

      {/* ── Chain ── */}
      <group ref={chainRef}>
        <lineSegments geometry={chainGeo}>
          <lineBasicMaterial color={GOLD} transparent opacity={hovered ? 0.35 : 0.2} />
        </lineSegments>
      </group>
    </group>
  );
};
