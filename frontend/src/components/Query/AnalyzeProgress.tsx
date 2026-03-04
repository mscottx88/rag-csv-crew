/**
 * AnalyzeProgress — 3D oscilloscope for "Analyzing results..." phase.
 * Inspired by the Tektronix 547 / HP 1740 bench oscilloscope.
 *
 * Features: landscape box chassis, large circular CRT screen with animated
 * waveform, four control knobs below the screen, BNC ports on right panel,
 * a channel selector row of buttons, and a blinking status LED.
 *
 * Color: cyan (#00eeff)
 */

import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { QueryScene } from './QueryScene';
import './AnalyzeProgress.css';

interface AnalyzeProgressProps {
  label?: string;
}

const CYAN = '#00eeff';

/* ── Body dimensions ── */
const BW = 2.2;   // body width
const BH = 1.5;   // body height
const BD = 0.9;   // body depth
const SCR_R = 0.54; // screen radius

/* ── Oscilloscope 3D object ── */
function Oscilloscope(): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const waveformRef = useRef<THREE.LineSegments>(null);
  const ledRef = useRef<THREE.Mesh>(null);
  const timeRef = useRef(0);

  /* ── Precomputed geometries ── */

  const bodyEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(BW, BH, BD)),
    [],
  );

  /* Screen bezel — slightly inset rectangular frame */
  const screenBezelGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = BD / 2 + 0.01;
    const hw = SCR_R + 0.06;
    const hh = SCR_R + 0.06;
    const cy = 0.1;
    verts.push(-hw, cy - hh, fz, hw, cy - hh, fz);
    verts.push(hw, cy - hh, fz, hw, cy + hh, fz);
    verts.push(hw, cy + hh, fz, -hw, cy + hh, fz);
    verts.push(-hw, cy + hh, fz, -hw, cy - hh, fz);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Screen circle edge */
  const screenCircleGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = BD / 2 + 0.02;
    const cy = 0.1;
    const segs = 40;
    for (let i = 0; i < segs; i++) {
      const a0 = (i / segs) * Math.PI * 2;
      const a1 = ((i + 1) / segs) * Math.PI * 2;
      verts.push(
        SCR_R * Math.cos(a0), cy + SCR_R * Math.sin(a0), fz,
        SCR_R * Math.cos(a1), cy + SCR_R * Math.sin(a1), fz,
      );
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Graticule grid (crosshatch on screen face) */
  const graticuleGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = BD / 2 + 0.025;
    const cy = 0.1;
    /* Horizontal lines */
    [-0.36, -0.18, 0, 0.18, 0.36].forEach(dy => {
      const y = cy + dy;
      const half = Math.sqrt(Math.max(0, SCR_R * SCR_R - dy * dy)) * 0.95;
      verts.push(-half, y, fz, half, y, fz);
    });
    /* Vertical lines */
    [-0.36, -0.18, 0, 0.18, 0.36].forEach(dx => {
      const half = Math.sqrt(Math.max(0, SCR_R * SCR_R - dx * dx)) * 0.95;
      verts.push(dx, cy - half, fz, dx, cy + half, fz);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Waveform line — 120 segments, updated each frame */
  const waveformGeo = useMemo(() => {
    const count = 119; // number of segments = points - 1
    const pos = new Float32Array((count) * 6);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return geo;
  }, []);

  /* Knob edges (shared) */
  const knobEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.CylinderGeometry(0.075, 0.075, 0.06, 10)),
    [],
  );

  /* BNC port circles */
  const bncGeo = useMemo(() => {
    const verts: number[] = [];
    const sx = BW / 2 + 0.01;
    [-0.3, 0, 0.3].forEach(y => {
      const segs = 12;
      const r = 0.055;
      for (let i = 0; i < segs; i++) {
        const a0 = (i / segs) * Math.PI * 2;
        const a1 = ((i + 1) / segs) * Math.PI * 2;
        verts.push(sx, y + r * Math.sin(a0), r * Math.cos(a0));
        verts.push(sx, y + r * Math.sin(a1), r * Math.cos(a1));
      }
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Channel selector buttons */
  const buttonRowGeo = useMemo(() => {
    const verts: number[] = [];
    const fz = BD / 2 + 0.01;
    const y = -BH / 2 + 0.14;
    [-0.6, -0.2, 0.2, 0.6].forEach(cx => {
      const hw = 0.1;
      const hh = 0.05;
      verts.push(cx - hw, y - hh, fz, cx + hw, y - hh, fz);
      verts.push(cx + hw, y - hh, fz, cx + hw, y + hh, fz);
      verts.push(cx + hw, y + hh, fz, cx - hw, y + hh, fz);
      verts.push(cx - hw, y + hh, fz, cx - hw, y - hh, fz);
    });
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    return geo;
  }, []);

  /* Leg edges (shared) */
  const legEdges = useMemo(
    () => new THREE.EdgesGeometry(new THREE.BoxGeometry(0.12, 0.18, 0.12)),
    [],
  );

  /* ── Animation loop ── */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;

    /* Subtle float + slow Y rotation */
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.6) * 0.04;
      groupRef.current.rotation.y = Math.sin(t * 0.18) * 0.22;
    }

    /* Composite waveform */
    if (waveformRef.current) {
      const pos = waveformRef.current.geometry.attributes.position as THREE.BufferAttribute;
      const arr = pos.array as Float32Array;
      const segCount = 119;
      const totalPoints = segCount + 1;
      const fz = BD / 2 + 0.03;
      const cy = 0.1;
      const freq1 = 2.5 + Math.sin(t * 0.4) * 1.2;
      const freq2 = 5.8 + Math.sin(t * 0.25) * 2.0;
      const amp1 = 0.22 + Math.sin(t * 0.35) * 0.08;
      const amp2 = 0.06 + Math.sin(t * 0.55) * 0.04;

      const xs: number[] = [];
      const ys: number[] = [];
      for (let i = 0; i < totalPoints; i++) {
        const xn = (i / (totalPoints - 1)) * 2 - 1;
        xs.push(xn * SCR_R * 0.94);
        ys.push(
          cy
          + amp1 * Math.sin(freq1 * Math.PI * xn + t * 3.2)
          + amp2 * Math.sin(freq2 * Math.PI * xn + t * 1.8),
        );
      }

      for (let i = 0; i < segCount; i++) {
        const base = i * 6;
        arr[base]     = xs[i] ?? 0;
        arr[base + 1] = ys[i] ?? 0;
        arr[base + 2] = fz;
        arr[base + 3] = xs[i + 1] ?? 0;
        arr[base + 4] = ys[i + 1] ?? 0;
        arr[base + 5] = fz;
      }
      pos.needsUpdate = true;
    }

    /* LED blink */
    if (ledRef.current) {
      const mat = ledRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.5 + Math.abs(Math.sin(t * 1.8)) * 0.5;
    }
  });

  const fz = BD / 2 + 0.01;
  const knobY = -BH / 2 + 0.28;
  const legPositions: [number, number][] = [
    [-BW / 2 + 0.1, -BD / 2 + 0.08],
    [-BW / 2 + 0.1,  BD / 2 - 0.08],
    [ BW / 2 - 0.1, -BD / 2 + 0.08],
    [ BW / 2 - 0.1,  BD / 2 - 0.08],
  ];

  return (
    <group ref={groupRef}>

      {/* ── Main chassis ── */}
      <mesh>
        <boxGeometry args={[BW, BH, BD]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.08} toneMapped={false} />
      </mesh>
      <lineSegments geometry={bodyEdges}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
      </lineSegments>

      {/* ── Screen backing ── */}
      <mesh position={[0, 0.1, BD / 2 + 0.015]}>
        <circleGeometry args={[SCR_R, 40]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.06} toneMapped={false} />
      </mesh>

      {/* ── Screen bezel ── */}
      <lineSegments geometry={screenBezelGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.35} />
      </lineSegments>

      {/* ── Screen circle ── */}
      <lineSegments geometry={screenCircleGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.65} />
      </lineSegments>

      {/* ── Graticule ── */}
      <lineSegments geometry={graticuleGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.18} />
      </lineSegments>

      {/* ── Animated waveform ── */}
      <lineSegments ref={waveformRef} geometry={waveformGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.92} />
      </lineSegments>

      {/* ── 4 control knobs ── */}
      {[-0.66, -0.22, 0.22, 0.66].map((cx, i) => (
        <group key={i} position={[cx, knobY, fz + 0.03]}>
          <mesh>
            <cylinderGeometry args={[0.075, 0.075, 0.06, 10]} />
            <meshBasicMaterial color={CYAN} transparent opacity={0.2} toneMapped={false} />
          </mesh>
          <lineSegments geometry={knobEdges}>
            <lineBasicMaterial color={CYAN} transparent opacity={0.55} />
          </lineSegments>
        </group>
      ))}

      {/* ── Channel selector buttons ── */}
      <lineSegments geometry={buttonRowGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.35} />
      </lineSegments>

      {/* ── BNC ports ── */}
      <lineSegments geometry={bncGeo}>
        <lineBasicMaterial color={CYAN} transparent opacity={0.4} />
      </lineSegments>

      {/* ── Status LED ── */}
      <mesh ref={ledRef} position={[BW / 2 - 0.16, BH / 2 - 0.15, fz + 0.01]}>
        <sphereGeometry args={[0.03, 8, 8]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.8} toneMapped={false} />
      </mesh>

      {/* ── Corner legs ── */}
      {legPositions.map(([lx, lz]) => (
        <group key={`${lx}-${lz}`} position={[lx, -BH / 2 - 0.09, lz]}>
          <mesh>
            <boxGeometry args={[0.12, 0.18, 0.12]} />
            <meshBasicMaterial color={CYAN} transparent opacity={0.15} toneMapped={false} />
          </mesh>
          <lineSegments geometry={legEdges}>
            <lineBasicMaterial color={CYAN} transparent opacity={0.45} />
          </lineSegments>
        </group>
      ))}
    </group>
  );
}

export const AnalyzeProgress: React.FC<AnalyzeProgressProps> = ({ label = 'Analyzing...' }) => (
  <div className="analyze-progress-container">
    <div className="qprog-canvas">
      <QueryScene cameraZ={4.5} fov={50}>
        <Oscilloscope />
      </QueryScene>
    </div>
    <div className="analyze-progress-label">{label}</div>
  </div>
);
