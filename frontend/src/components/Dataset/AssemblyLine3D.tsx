/**
 * AssemblyLine3D — Continuous 3D assembly-line animation for the Upload page.
 * A conveyor belt carries a paper-stack item through 4 processing stations:
 *   1. Upload (Hopper)   — paper drops from chute, progress bar fills
 *   2. Process (Shredder) — rollers shred the stack, shreds scatter
 *   3. Embed (Laser)      — robotic laser arms zap shreds into digital 1s and 0s
 *   4. Complete (Vacuum)   — vacuum descends and sucks up 1s and 0s from belt
 *
 * Solid-mesh + EdgesGeometry overlay aesthetic matching Dashboard3D components.
 * Each station is a proper 3D machine: solid fills, edge wireframes, detail
 * panel lines, base plates, vents, and animated LEDs.
 */

import React, { Suspense, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { HalfFloatType } from 'three';
import * as THREE from 'three';
import './AssemblyLine3D.css';

type AnimPhase = 'hidden' | 'uploading' | 'processing' | 'embedding' | 'complete';

interface AssemblyLine3DProps {
  phase: AnimPhase;
  progress: number; // 0–100
}

/* ── Layout constants ── */
const GREEN = '#39ff14';

const BELT_LEN = 9.5;
const BELT_W = 1.2;
const RAIL_OFFSET = BELT_W / 2 + 0.06;

const S1_X = -3.0;
const S2_X = -1.0;
const S3_X = 1.0;
const S4_X = 3.0;

const BELT_Y = 0;
const ITEM_Y = BELT_Y + 0.1;

const CHEVRON_COUNT = 10;
const CHEVRON_SPACING = BELT_LEN / CHEVRON_COUNT;

const SHEET_W = 0.6;
const SHEET_D = 0.8;
const SHEET_H = 0.02;
const SHEET_COUNT = 5;

/* ── Phase helpers ── */
function phaseIndex(phase: AnimPhase): number {
  switch (phase) {
    case 'uploading': return 0;
    case 'processing': return 1;
    case 'embedding': return 2;
    case 'complete': return 3;
    default: return -1;
  }
}

function phaseTargetX(phase: AnimPhase): number {
  switch (phase) {
    case 'uploading': return S1_X;
    case 'processing': return S2_X;
    case 'embedding': return S2_X; // item stays at S2 (shredded)
    case 'complete': return S2_X;
    default: return -6;
  }
}

/* ════════════════════════════════════════════════
   Inner scene component (must be inside Canvas)
   ════════════════════════════════════════════════ */
function AssemblyLineScene({ phase, progress }: { phase: AnimPhase; progress: number }): React.JSX.Element {
  const timeRef = useRef(0);
  const chevronOffsetRef = useRef(0);

  // Item animation refs
  const itemGroupRef = useRef<THREE.Group>(null);
  const itemXRef = useRef(-6);
  const itemYRef = useRef(2.5);
  const itemScaleYRef = useRef(1);
  const itemOpacityRef = useRef(0);
  const dropDoneRef = useRef(false);

  // Belt roller group ref (for animating conveyor rollers)
  const beltRollersGroupRef = useRef<THREE.Group>(null);

  // Station refs
  const roller1Ref = useRef<THREE.Group>(null);
  const roller2Ref = useRef<THREE.Group>(null);
  const progressBarRef = useRef<THREE.Mesh>(null);
  const laserArm1Ref = useRef<THREE.Group>(null);
  const laserArm2Ref = useRef<THREE.Group>(null);
  const laserBeam1Ref = useRef<THREE.LineSegments>(null);
  const laserBeam2Ref = useRef<THREE.LineSegments>(null);
  const vacuumNozzleRef = useRef<THREE.Group>(null);

  // LED refs
  const led1Ref = useRef<THREE.Mesh>(null);
  const led2Ref = useRef<THREE.Mesh>(null);
  const led3Ref = useRef<THREE.Mesh>(null);
  const led4Ref = useRef<THREE.Mesh>(null);

  // Particle refs
  const particlesS2Ref = useRef<THREE.Group>(null);     // shreds from shredder
  const particlesS3InRef = useRef<THREE.Group>(null);    // shreds entering gate
  const particlesS3OutRef = useRef<THREE.Group>(null);   // digital bits leaving gate
  const particlesS4Ref = useRef<THREE.Group>(null);      // bits vacuumed into silo

  /* ══════════════════════════════════════════
     Geometry memos — Belt
     ══════════════════════════════════════════ */
  const beltEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(BELT_LEN, 0.04, BELT_W),
  ), []);

  const railEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(BELT_LEN + 0.5, 0.08, 0.1),
  ), []);

  const beltRollerEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.08, 0.08, BELT_W + 0.2, 10),
  ), []);

  const legEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.06, 0.6, 0.06),
  ), []);

  const chevronGeo = useMemo(() => {
    const v: number[] = [];
    for (let i = 0; i < CHEVRON_COUNT; i++) {
      const x = -BELT_LEN / 2 + i * CHEVRON_SPACING + CHEVRON_SPACING / 2;
      v.push(x - 0.15, BELT_Y + 0.025, -0.25, x + 0.15, BELT_Y + 0.025, 0);
      v.push(x + 0.15, BELT_Y + 0.025, 0, x - 0.15, BELT_Y + 0.025, 0.25);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  const rollerPositions = useMemo((): number[] => {
    const positions: number[] = [];
    for (let i = 0; i < 5; i++) {
      positions.push(-BELT_LEN / 2 + 0.8 + i * (BELT_LEN - 1.6) / 4);
    }
    return positions;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Paper stack
     ══════════════════════════════════════════ */
  const sheetEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(SHEET_W, SHEET_H, SHEET_D),
  ), []);

  const csvLinesGeo = useMemo(() => {
    const v: number[] = [];
    const widths = [0.4, 0.25, 0.48, 0.3];
    const baseY = SHEET_COUNT * SHEET_H + 0.005;
    for (let i = 0; i < widths.length; i++) {
      const w = widths[i] ?? 0.3;
      const z = -SHEET_D / 2 + 0.1 + i * 0.18;
      v.push(-SHEET_W / 2 + 0.06, baseY, z, -SHEET_W / 2 + 0.06 + w, baseY, z);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Station 1: Hopper
     ══════════════════════════════════════════ */
  const hopperBodyEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.9, 1.0, 1.0),
  ), []);
  const hopperRimEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(1.2, 0.15, 1.3),
  ), []);
  const hopperBaseEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(1.1, 0.06, 1.2),
  ), []);

  // Hopper detail lines: front panel opening, internal guides, side vents
  const hopperDetailGeo = useMemo(() => {
    const v: number[] = [];
    const fz = 0.51; // just in front of hopper body
    const bx = 0;    // relative to hopper center
    const by = -0.5; // bottom of body (relative to body center at 0)

    // Front feed opening rectangle
    const openW = 0.5;
    const openH = 0.35;
    const oy = by + 0.08;
    v.push(bx - openW / 2, oy, fz, bx + openW / 2, oy, fz);
    v.push(bx - openW / 2, oy + openH, fz, bx + openW / 2, oy + openH, fz);
    v.push(bx - openW / 2, oy, fz, bx - openW / 2, oy + openH, fz);
    v.push(bx + openW / 2, oy, fz, bx + openW / 2, oy + openH, fz);

    // Internal guide rails inside opening
    v.push(bx - openW / 2 + 0.04, oy + 0.04, fz, bx + openW / 2 - 0.04, oy + 0.04, fz);
    v.push(bx - openW / 2 + 0.04, oy + openH - 0.04, fz, bx + openW / 2 - 0.04, oy + openH - 0.04, fz);

    // Operator panel rectangle below opening
    const panelW = 0.35;
    const panelH = 0.12;
    const panelY = oy - 0.16;
    v.push(bx - panelW / 2, panelY, fz, bx + panelW / 2, panelY, fz);
    v.push(bx - panelW / 2, panelY + panelH, fz, bx + panelW / 2, panelY + panelH, fz);
    v.push(bx - panelW / 2, panelY, fz, bx - panelW / 2, panelY + panelH, fz);
    v.push(bx + panelW / 2, panelY, fz, bx + panelW / 2, panelY + panelH, fz);

    // Side vents (right side of hopper)
    const sx = 0.46;
    for (let i = 0; i < 4; i++) {
      const vy = -0.25 + i * 0.15;
      v.push(sx, vy, -0.35, sx, vy, 0.35);
      v.push(-sx, vy, -0.35, -sx, vy, 0.35);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  const progressBarBgGeo = useMemo(() => {
    const v: number[] = [];
    const bx = S1_X;
    const barW = 0.8;
    const barY = BELT_Y - 0.15;
    v.push(bx - barW / 2, barY, 0, bx + barW / 2, barY, 0);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Station 2: Roller Press
     ══════════════════════════════════════════ */
  const pressSideEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.8, 1.2, 0.08),
  ), []);
  const pressBarEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.1, 0.1, BELT_W + 0.38),
  ), []);
  const pressRoller1Edges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.15, 0.15, BELT_W + 0.1, 12),
  ), []);
  const pressRoller2Edges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.12, 0.12, BELT_W + 0.1, 12),
  ), []);
  const pressControlEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.2, 0.3, 0.15),
  ), []);
  const pressBaseEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.9, 0.05, 0.15),
  ), []);

  // Press detail lines: vent slits on side panels
  const pressDetailGeo = useMemo(() => {
    const v: number[] = [];
    for (const zSign of [-1, 1]) {
      const sz = zSign * (BELT_W / 2 + 0.15) + zSign * 0.045;
      for (let i = 0; i < 5; i++) {
        const vy = -0.2 + i * 0.14;
        v.push(-0.3, vy, sz, 0.3, vy, sz);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Station 3: Laser Arms
     ══════════════════════════════════════════ */
  const laserPylonEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.1, 1.4, 0.1),
  ), []);
  const laserArmBarEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.06, 0.06, 0.6),
  ), []);
  const laserBaseEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.2, 0.05, 0.2),
  ), []);
  // Sci-fi ray gun parts (Planet 51 style)
  const gunBodyEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.SphereGeometry(0.065, 8, 6),
  ), []);
  const gunFinEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.13, 0.01, 0.045),
  ), []);
  const gunBarrelEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.01, 0.016, 0.32, 6),
  ), []);
  const gunEmitterEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.SphereGeometry(0.022, 6, 5),
  ), []);
  const gunAntennaEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.006, 0.006, 0.11, 4),
  ), []);

  // Laser beam geometry — vertical line from emitter tip down to belt
  const laserBeamGeo = useMemo(() => {
    const v: number[] = [0, 0, 0, 0, -0.88, 0];
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Digital "1" and "0" digits
     ══════════════════════════════════════════ */
  const digit1Geo = useMemo(() => {
    const v: number[] = [
      // Vertical stroke
      0, -0.03, 0, 0, 0.03, 0,
      // Top serif
      -0.01, 0.02, 0, 0, 0.03, 0,
      // Base line
      -0.014, -0.03, 0, 0.014, -0.03, 0,
    ];
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  const digit0Geo = useMemo(() => {
    const v: number[] = [
      // Top
      -0.014, 0.028, 0, 0.014, 0.028, 0,
      // Right
      0.014, 0.028, 0, 0.014, -0.028, 0,
      // Bottom
      0.014, -0.028, 0, -0.014, -0.028, 0,
      // Left
      -0.014, -0.028, 0, -0.014, 0.028, 0,
    ];
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);

  /* ══════════════════════════════════════════
     Geometry memos — Station 4: Vacuum
     ══════════════════════════════════════════ */
  const vacuumPostEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.1, 1.6, 0.1),
  ), []);
  const vacuumCrossbarEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.08, 0.08, BELT_W + 0.38),
  ), []);
  const vacuumMotorEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.3, 0.25, 0.3),
  ), []);
  // Long ribbed hose cylinder — extends from nozzle up into motor housing
  const vacuumHoseCylEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.048, 0.048, 0.75, 8),
  ), []);
  // Rib rings along the hose at even intervals
  const vacuumHoseRibsGeo = useMemo(() => {
    const v: number[] = [];
    const segs = 8;
    const r = 0.062;
    for (let ring = 0; ring < 6; ring++) {
      const ry = -0.3 + ring * 0.12;
      for (let s = 0; s < segs; s++) {
        const a0 = (s / segs) * Math.PI * 2;
        const a1 = ((s + 1) / segs) * Math.PI * 2;
        v.push(Math.cos(a0) * r, ry, Math.sin(a0) * r, Math.cos(a1) * r, ry, Math.sin(a1) * r);
      }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    return geo;
  }, []);
  // Dramatic flared nozzle cone — wide at bottom, narrow at top
  const vacuumNozzleEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.CylinderGeometry(0.04, 0.44, 0.4, 8),
  ), []);
  const vacuumBaseEdges = useMemo(() => new THREE.EdgesGeometry(
    new THREE.BoxGeometry(0.2, 0.05, 0.2),
  ), []);

  /* ══════════════════════════════════════════
     useFrame: master animation loop
     ══════════════════════════════════════════ */
  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;
    const pi = phaseIndex(phase);
    const active = pi >= 0;

    // Belt chevron scroll
    const beltSpeed = active ? 0.8 : 0.15;
    chevronOffsetRef.current += delta * beltSpeed;

    if (chevronGeo.attributes.position) {
      const posAttr = chevronGeo.attributes.position as THREE.BufferAttribute;
      const arr = posAttr.array as Float32Array;
      const offset = chevronOffsetRef.current % CHEVRON_SPACING;
      for (let c = 0; c < CHEVRON_COUNT; c++) {
        const baseX = -BELT_LEN / 2 + c * CHEVRON_SPACING + CHEVRON_SPACING / 2 + offset;
        const wrappedX = baseX > BELT_LEN / 2 ? baseX - BELT_LEN : baseX;
        const idx = c * 12;
        arr[idx] = wrappedX - 0.15;
        arr[idx + 3] = wrappedX + 0.15;
        arr[idx + 6] = wrappedX + 0.15;
        arr[idx + 9] = wrappedX - 0.15;
      }
      posAttr.needsUpdate = true;
    }

    // Item position
    const targetX = phaseTargetX(phase);
    const targetY = phase === 'hidden' ? 2.5 : ITEM_Y;

    if (phase === 'uploading' && !dropDoneRef.current) {
      itemYRef.current += (targetY - itemYRef.current) * Math.min(1, delta * 5);
      if (Math.abs(itemYRef.current - targetY) < 0.02) {
        dropDoneRef.current = true;
      }
    } else if (phase === 'hidden') {
      itemYRef.current = 2.5;
      dropDoneRef.current = false;
    } else {
      itemYRef.current = ITEM_Y;
    }

    itemXRef.current += (targetX - itemXRef.current) * Math.min(1, delta * 2.5);
    const itemTargetOpacity = phase === 'hidden' || phase === 'embedding' || phase === 'complete' ? 0 : 1;
    itemOpacityRef.current += (itemTargetOpacity - itemOpacityRef.current) * Math.min(1, delta * 4);

    // Item scale — shrinks to nothing at S2 (gets shredded)
    const scaleTarget = phase === 'processing' || phase === 'embedding' || phase === 'complete' ? 0.05 : 1.0;
    itemScaleYRef.current += (scaleTarget - itemScaleYRef.current) * Math.min(1, delta * 3);

    // Apply to item group
    if (itemGroupRef.current) {
      itemGroupRef.current.position.x = itemXRef.current;
      itemGroupRef.current.position.y = itemYRef.current;
      itemGroupRef.current.scale.y = itemScaleYRef.current;
      itemGroupRef.current.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          const mat = child.material as THREE.MeshBasicMaterial;
          mat.opacity = mat.userData.baseOpacity * itemOpacityRef.current;
        } else if (child instanceof THREE.LineSegments) {
          const mat = child.material as THREE.LineBasicMaterial;
          mat.opacity = (mat.userData.baseOpacity ?? 0.5) * itemOpacityRef.current;
        }
      });
    }

    // Progress bar
    if (progressBarRef.current) {
      const barW = 0.8 * (progress / 100);
      progressBarRef.current.scale.x = Math.max(0.001, barW / 0.8);
      progressBarRef.current.position.x = S1_X - 0.4 + barW / 2;
      const mat = progressBarRef.current.material as THREE.MeshBasicMaterial;
      mat.opacity = phase === 'uploading' ? 0.7 : 0.1;
    }

    // Belt rollers — spin proportional to belt speed
    if (beltRollersGroupRef.current) {
      beltRollersGroupRef.current.children.forEach((posGroup) => {
        posGroup.rotation.z -= delta * beltSpeed * 3;
      });
    }

    // Rollers (S2) — always spin, faster when processing
    const rollerSpeed = phase === 'processing' ? 6 : 1.0;
    if (roller1Ref.current) roller1Ref.current.rotation.z += delta * rollerSpeed;
    if (roller2Ref.current) roller2Ref.current.rotation.z -= delta * rollerSpeed;

    // Laser arms (S3) — oscillate when embedding
    if (laserArm1Ref.current) {
      const armTarget = phase === 'embedding' ? Math.sin(t * 1.5) * 0.12 : 0;
      laserArm1Ref.current.rotation.y += (armTarget - laserArm1Ref.current.rotation.y) * Math.min(1, delta * 5);
    }
    if (laserArm2Ref.current) {
      const armTarget = phase === 'embedding' ? Math.sin(t * 1.5 + Math.PI) * 0.12 : 0;
      laserArm2Ref.current.rotation.y += (armTarget - laserArm2Ref.current.rotation.y) * Math.min(1, delta * 5);
    }

    // Laser beams (S3) — pulse bright during embedding
    if (laserBeam1Ref.current) {
      const mat = laserBeam1Ref.current.material as THREE.LineBasicMaterial;
      mat.opacity = phase === 'embedding' ? 0.4 + Math.sin(t * 8) * 0.35 : 0.05;
    }
    if (laserBeam2Ref.current) {
      const mat = laserBeam2Ref.current.material as THREE.LineBasicMaterial;
      mat.opacity = phase === 'embedding' ? 0.4 + Math.sin(t * 8 + 1) * 0.35 : 0.05;
    }

    // Vacuum nozzle (S4) — descends during complete
    if (vacuumNozzleRef.current) {
      const nozzleTarget = phase === 'complete' ? 0.3 : 0.85;
      vacuumNozzleRef.current.position.y += (nozzleTarget - vacuumNozzleRef.current.position.y) * Math.min(1, delta * 2);
    }

    // LEDs — always blink (brighter when their station is active)
    if (led1Ref.current) {
      const mat = led1Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = phase === 'uploading' ? (Math.sin(t * 6) > 0 ? 0.9 : 0.3) : (Math.sin(t * 2) > 0 ? 0.5 : 0.15);
    }
    if (led2Ref.current) {
      const mat = led2Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = phase === 'processing' ? (Math.sin(t * 5) > 0 ? 0.9 : 0.3) : (Math.sin(t * 2.3) > 0 ? 0.5 : 0.15);
    }
    if (led3Ref.current) {
      const mat = led3Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = phase === 'embedding' ? (Math.sin(t * 4) > 0 ? 0.9 : 0.3) : (Math.sin(t * 1.7) > 0 ? 0.5 : 0.15);
    }
    if (led4Ref.current) {
      const mat = led4Ref.current.material as THREE.MeshBasicMaterial;
      mat.opacity = phase === 'complete' ? 0.9 : (Math.sin(t * 1.5) > 0 ? 0.5 : 0.15);
    }

    // S2 — Paper shreds flying out of shredder
    if (particlesS2Ref.current) {
      particlesS2Ref.current.children.forEach((child, i) => {
        const mesh = child as THREE.Mesh;
        const mat = mesh.material as THREE.MeshBasicMaterial;
        if (phase === 'processing' || phase === 'embedding') {
          const cycle = (t * 0.5 + i * 0.07) % 1;
          const angle = (i / 12) * Math.PI * 2 + i * 0.8;
          const radius = cycle * 0.9;
          mesh.position.x = Math.cos(angle) * radius * 0.6;
          mesh.position.y = 0.3 + Math.sin(cycle * Math.PI) * 0.5;
          mesh.position.z = Math.sin(angle) * radius;
          mesh.rotation.x = t * 3 + i;
          mesh.rotation.z = t * 2 + i * 0.7;
          mat.opacity = Math.sin(cycle * Math.PI) * 0.7;
        } else {
          mat.opacity = 0;
        }
      });
    }

    // S3 input — Paper shreds: travel from S2 and pile up, then get zapped
    if (particlesS3InRef.current) {
      particlesS3InRef.current.children.forEach((child, i) => {
        const mesh = child as THREE.Mesh;
        const mat = mesh.material as THREE.MeshBasicMaterial;
        // Fixed pile position for each shred (consistent across phases)
        const pileX = ((i % 5) - 2) * 0.11;
        const pileY = ITEM_Y + 0.008 + Math.floor(i / 5) * 0.007;
        const pileZ = ((i % 4) - 1.5) * 0.12;
        if (phase === 'processing') {
          // Shreds traveling rightward from S2 toward the pile
          const flow = (t * 0.45 + i * 0.06) % 1;
          mesh.position.x = -2.0 + flow * (2.0 + pileX);
          mesh.position.y = ITEM_Y + 0.01;
          mesh.position.z = pileZ * flow;
          mesh.rotation.z = i * 0.5 + t * 0.3;
          mat.opacity = flow * 0.75;
        } else if (phase === 'embedding') {
          // Pile sitting at S3, flashing when laser zaps
          mesh.position.x = pileX;
          mesh.position.y = pileY;
          mesh.position.z = pileZ;
          mesh.rotation.z = i * 0.5;
          const zapCycle = (t * 1.5 + i * 0.25) % 1;
          mat.opacity = zapCycle < 0.15 ? 0.95 : Math.max(0.15, 0.65 - zapCycle * 0.5);
        } else {
          mat.opacity = 0;
        }
      });
    }

    // S3 output — Digital 1s and 0s sliding right along belt toward S4
    if (particlesS3OutRef.current) {
      particlesS3OutRef.current.children.forEach((child, i) => {
        const seg = child as THREE.LineSegments;
        const mat = seg.material as THREE.LineBasicMaterial;
        if (phase === 'embedding' || phase === 'complete') {
          const flow = (t * 0.35 + i * 0.12) % 1;
          seg.position.x = flow * (S4_X - S3_X);
          seg.position.y = ITEM_Y + 0.03;
          seg.position.z = (i % 3 - 1) * 0.12;
          seg.rotation.y = Math.sin(t + i) * 0.2;
          mat.opacity = 0.5 + Math.sin(flow * Math.PI) * 0.3;
        } else {
          mat.opacity = 0;
        }
      });
    }

    // S4 — Digital 1s and 0s: accumulate on belt, then get vacuumed up
    if (particlesS4Ref.current) {
      particlesS4Ref.current.children.forEach((child, i) => {
        const seg = child as THREE.LineSegments;
        const mat = seg.material as THREE.LineBasicMaterial;
        if (phase === 'embedding') {
          // Bits accumulating on belt
          seg.position.x = -0.4 + (i / 10) * 0.8;
          seg.position.y = ITEM_Y + 0.02 + (i % 3) * 0.02;
          seg.position.z = (i % 4 - 1.5) * 0.1;
          seg.rotation.z = i * 0.5;
          mat.opacity = 0.6;
        } else if (phase === 'complete') {
          const cycle = (t * 0.5 + i * 0.1) % 1;
          const startX = -0.4 + (i / 10) * 0.8;
          const startZ = (i % 4 - 1.5) * 0.1;
          if (cycle < 0.35) {
            // Phase 1: converge toward nozzle mouth
            const gather = cycle / 0.35;
            seg.position.x = startX * (1 - gather * gather);
            seg.position.y = ITEM_Y + 0.03 + gather * 0.12;
            seg.position.z = startZ * (1 - gather * gather);
            seg.rotation.y = gather * Math.PI * 2 + i;
            mat.opacity = 0.8;
          } else {
            // Phase 2: shoot straight up through the hose tube
            const rise = (cycle - 0.35) / 0.65;
            seg.position.x = Math.sin(rise * Math.PI * 3 + i) * 0.015;
            seg.position.y = 0.18 + rise * 1.25;
            seg.position.z = Math.cos(rise * Math.PI * 3 + i) * 0.015;
            seg.rotation.y = rise * Math.PI * 5 + i;
            mat.opacity = 0.9 * (1 - rise * 0.65);
          }
        } else {
          mat.opacity = 0;
        }
      });
    }
  });

  return (
    <group>
      {/* ══════════════════════════════════════════
          CONVEYOR BELT
          ══════════════════════════════════════════ */}

      {/* Belt surface — solid fill + edges */}
      <mesh position={[0, BELT_Y, 0]}>
        <boxGeometry args={[BELT_LEN, 0.04, BELT_W]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <lineSegments geometry={beltEdges} position={[0, BELT_Y, 0]}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.45} />
      </lineSegments>

      {/* Rails — solid box + edges */}
      {[-1, 1].map((sign) => (
        <group key={`rail-${sign}`} position={[0, BELT_Y, sign * RAIL_OFFSET]}>
          <mesh>
            <boxGeometry args={[BELT_LEN + 0.5, 0.08, 0.1]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.08} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={railEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
          </lineSegments>
        </group>
      ))}

      {/* Chevrons */}
      <lineSegments geometry={chevronGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.3} />
      </lineSegments>

      {/* Rollers underneath — solid cylinder + edges */}
      <group ref={beltRollersGroupRef}>
        {rollerPositions.map((rx, i) => (
          <group key={`roller-${i}`} position={[rx, BELT_Y - 0.12, 0]}>
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.08, 0.08, BELT_W + 0.2, 10]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.05} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={beltRollerEdges} rotation={[Math.PI / 2, 0, 0]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.3} />
            </lineSegments>
          </group>
        ))}
      </group>

      {/* Support legs — solid box + edges */}
      {[
        { x: BELT_LEN / 2 - 0.3, z: BELT_W / 2 + 0.04 },
        { x: BELT_LEN / 2 - 0.3, z: -(BELT_W / 2 + 0.04) },
        { x: -(BELT_LEN / 2 - 0.3), z: BELT_W / 2 + 0.04 },
        { x: -(BELT_LEN / 2 - 0.3), z: -(BELT_W / 2 + 0.04) },
      ].map((leg, i) => (
        <group key={`leg-${i}`} position={[leg.x, BELT_Y - 0.32, leg.z]}>
          <mesh>
            <boxGeometry args={[0.06, 0.6, 0.06]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.06} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={legEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.3} />
          </lineSegments>
        </group>
      ))}

      {/* ══════════════════════════════════════════
          PAPER STACK (traveling item)
          ══════════════════════════════════════════ */}
      <group ref={itemGroupRef} position={[-6, 2.5, 0]}>
        {Array.from({ length: SHEET_COUNT }).map((_, i) => {
          const ox = (i % 2 === 0 ? 0.02 : -0.015) * (i > 0 ? 1 : 0);
          const oz = (i % 3 === 0 ? 0.01 : -0.01) * (i > 0 ? 1 : 0);
          return (
            <group key={`sheet-${i}`} position={[ox, i * SHEET_H, oz]}>
              <mesh>
                <boxGeometry args={[SHEET_W, SHEET_H, SHEET_D]} />
                <meshBasicMaterial
                  color={GREEN} transparent opacity={0.25} toneMapped={false}
                  side={THREE.DoubleSide}
                  userData={{ baseOpacity: 0.25 }}
                />
              </mesh>
              <lineSegments geometry={sheetEdges}>
                <lineBasicMaterial
                  color={GREEN} transparent opacity={0.7}
                  userData={{ baseOpacity: 0.7 }}
                />
              </lineSegments>
            </group>
          );
        })}
        <lineSegments geometry={csvLinesGeo}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.55} userData={{ baseOpacity: 0.55 }} />
        </lineSegments>
      </group>

      {/* ══════════════════════════════════════════
          STATION 1 — Upload / Hopper
          ══════════════════════════════════════════ */}
      <group position={[S1_X, BELT_Y + 0.8, 0]}>
        {/* Main housing body — solid fill + edges */}
        <mesh>
          <boxGeometry args={[0.9, 1.0, 1.0]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.15} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={hopperBodyEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.65} />
        </lineSegments>

        {/* Flared intake rim */}
        <mesh position={[0, 0.58, 0]}>
          <boxGeometry args={[1.2, 0.15, 1.3]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.12} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={hopperRimEdges} position={[0, 0.58, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
        </lineSegments>

        {/* Base plate */}
        <mesh position={[0, -0.53, 0]}>
          <boxGeometry args={[1.1, 0.06, 1.2]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.2} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={hopperBaseEdges} position={[0, -0.53, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.5} />
        </lineSegments>

        {/* Detail panel lines */}
        <lineSegments geometry={hopperDetailGeo}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.35} />
        </lineSegments>
      </group>

      {/* Upload LED */}
      <mesh ref={led1Ref} position={[S1_X + 0.25, BELT_Y + 0.18, 0.52]}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
      </mesh>

      {/* Progress bar */}
      <lineSegments geometry={progressBarBgGeo}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.4} />
      </lineSegments>
      <mesh ref={progressBarRef} position={[S1_X - 0.4, BELT_Y - 0.15, 0]}>
        <boxGeometry args={[0.8, 0.04, 0.06]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
      </mesh>

      {/* ══════════════════════════════════════════
          STATION 2 — Process / Roller Press
          ══════════════════════════════════════════ */}

      {/* Side panels — solid box + edges */}
      {[-1, 1].map((zSign) => (
        <group key={`press-side-${zSign}`} position={[S2_X, BELT_Y + 0.6, zSign * (BELT_W / 2 + 0.15)]}>
          <mesh>
            <boxGeometry args={[0.8, 1.2, 0.08]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.15} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={pressSideEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
          </lineSegments>
        </group>
      ))}

      {/* Top crossbars connecting sides */}
      {[-1, 1].map((xSign) => (
        <group key={`press-bar-${xSign}`} position={[S2_X + xSign * 0.35, BELT_Y + 1.25, 0]}>
          <mesh>
            <boxGeometry args={[0.1, 0.1, BELT_W + 0.38]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.12} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={pressBarEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.5} />
          </lineSegments>
        </group>
      ))}

      {/* Upper roller — solid cylinder + edges (in group for rotation) */}
      <group ref={roller1Ref} position={[S2_X, BELT_Y + 0.45, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.15, 0.15, BELT_W + 0.1, 12]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={pressRoller1Edges} rotation={[Math.PI / 2, 0, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
        </lineSegments>
      </group>

      {/* Lower roller */}
      <group ref={roller2Ref} position={[S2_X, BELT_Y + 0.15, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.12, 0.12, BELT_W + 0.1, 12]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={pressRoller2Edges} rotation={[Math.PI / 2, 0, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
        </lineSegments>
      </group>

      {/* Control box on side — solid + edges */}
      <group position={[S2_X - 0.45, BELT_Y + 0.85, BELT_W / 2 + 0.2]}>
        <mesh>
          <boxGeometry args={[0.2, 0.3, 0.15]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.15} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={pressControlEdges}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.5} />
        </lineSegments>
      </group>

      {/* Base plates under each side panel */}
      {[-1, 1].map((zSign) => (
        <group key={`press-base-${zSign}`} position={[S2_X, BELT_Y - 0.025, zSign * (BELT_W / 2 + 0.15)]}>
          <mesh>
            <boxGeometry args={[0.9, 0.05, 0.15]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.2} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={pressBaseEdges}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.45} />
          </lineSegments>
        </group>
      ))}

      {/* Vent detail lines */}
      <lineSegments geometry={pressDetailGeo} position={[S2_X, BELT_Y + 0.6, 0]}>
        <lineBasicMaterial color={GREEN} transparent opacity={0.25} />
      </lineSegments>

      {/* Process LED */}
      <mesh ref={led2Ref} position={[S2_X - 0.4, BELT_Y + 1.06, BELT_W / 2 + 0.28]}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
      </mesh>

      {/* Paper shreds from shredder */}
      <group ref={particlesS2Ref} position={[S2_X, BELT_Y, 0]}>
        {Array.from({ length: 12 }).map((_, i) => (
          <mesh key={`ps2-${i}`}>
            <boxGeometry args={[0.07, 0.008, 0.035]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* ══════════════════════════════════════════
          STATION 3 — Embed / Laser Digitizer Arms
          ══════════════════════════════════════════ */}

      {/* Two laser arms, one on each side of belt */}
      {([-1, 1] as const).map((zSign, armIdx) => (
        <group key={`laser-arm-${zSign}`} position={[S3_X, BELT_Y, zSign * (BELT_W / 2 + 0.15)]}>
          {/* Pylon — solid box + edges */}
          <mesh position={[0, 0.7, 0]}>
            <boxGeometry args={[0.1, 1.4, 0.1]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={laserPylonEdges} position={[0, 0.7, 0]}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
          </lineSegments>

          {/* Base foot plate */}
          <mesh position={[0, 0.025, 0]}>
            <boxGeometry args={[0.2, 0.05, 0.2]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.25} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={laserBaseEdges} position={[0, 0.025, 0]}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.6} />
          </lineSegments>

          {/* Oscillating arm group (rotates at pylon top) */}
          <group ref={armIdx === 0 ? laserArm1Ref : laserArm2Ref} position={[0, 1.35, 0]}>
            {/* Horizontal arm bar extending inward over belt */}
            <mesh position={[0, 0, -zSign * 0.3]}>
              <boxGeometry args={[0.06, 0.06, 0.6]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={laserArmBarEdges} position={[0, 0, -zSign * 0.3]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
            </lineSegments>

            {/* ── Sci-fi ray gun head (Planet 51 style) ── */}
            {/* Antenna pointing up from gun body */}
            <mesh position={[0, -0.01, -zSign * 0.57]}>
              <cylinderGeometry args={[0.006, 0.006, 0.11, 4]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.4} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={gunAntennaEdges} position={[0, -0.01, -zSign * 0.57]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.8} />
            </lineSegments>

            {/* Round body sphere */}
            <mesh position={[0, -0.1, -zSign * 0.57]}>
              <sphereGeometry args={[0.065, 8, 6]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.35} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={gunBodyEdges} position={[0, -0.1, -zSign * 0.57]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.8} />
            </lineSegments>

            {/* Side fins on body */}
            {([-1, 1] as const).map((fSign) => (
              <group key={`fin-${fSign}`} position={[fSign * 0.075, -0.1, -zSign * 0.57]}>
                <mesh>
                  <boxGeometry args={[0.045, 0.01, 0.13]} />
                  <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
                </mesh>
                <lineSegments geometry={gunFinEdges}>
                  <lineBasicMaterial color={GREEN} transparent opacity={0.75} />
                </lineSegments>
              </group>
            ))}

            {/* Long thin barrel pointing down */}
            <mesh position={[0, -0.27, -zSign * 0.57]}>
              <cylinderGeometry args={[0.01, 0.016, 0.32, 6]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.4} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={gunBarrelEdges} position={[0, -0.27, -zSign * 0.57]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.85} />
            </lineSegments>

            {/* Glowing emitter tip at barrel end */}
            <mesh position={[0, -0.44, -zSign * 0.57]}>
              <sphereGeometry args={[0.022, 6, 5]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.5} toneMapped={false} />
            </mesh>
            <lineSegments geometry={gunEmitterEdges} position={[0, -0.44, -zSign * 0.57]}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.9} />
            </lineSegments>

            {/* Laser beam — line from emitter tip to belt */}
            <lineSegments
              ref={armIdx === 0 ? laserBeam1Ref : laserBeam2Ref}
              geometry={laserBeamGeo}
              position={[0, -0.47, -zSign * 0.57]}
            >
              <lineBasicMaterial color={GREEN} transparent opacity={0.05} />
            </lineSegments>
          </group>
        </group>
      ))}

      {/* Embed LED */}
      <mesh ref={led3Ref} position={[S3_X, BELT_Y + 1.52, BELT_W / 2 + 0.22]}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
      </mesh>

      {/* Paper shreds traveling from S2 and piling up at laser site */}
      <group ref={particlesS3InRef} position={[S3_X, BELT_Y, 0]}>
        {Array.from({ length: 20 }).map((_, i) => (
          <mesh key={`ps3i-${i}`}>
            <boxGeometry args={[0.07, 0.008, 0.032]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0} toneMapped={false} />
          </mesh>
        ))}
      </group>

      {/* Digital 1s and 0s sliding right along belt toward S4 */}
      <group ref={particlesS3OutRef} position={[S3_X, BELT_Y, 0]}>
        {Array.from({ length: 8 }).map((_, i) => (
          <lineSegments key={`ps3o-${i}`} geometry={i % 2 === 0 ? digit1Geo : digit0Geo}>
            <lineBasicMaterial color={GREEN} transparent opacity={0} />
          </lineSegments>
        ))}
      </group>

      {/* ══════════════════════════════════════════
          STATION 4 — Complete / Vacuum
          ══════════════════════════════════════════ */}
      <group position={[S4_X, BELT_Y, 0]}>
        {/* Support posts on each side */}
        {([-1, 1] as const).map((zSign) => (
          <group key={`vac-post-${zSign}`} position={[0, 0.8, zSign * (BELT_W / 2 + 0.15)]}>
            <mesh>
              <boxGeometry args={[0.1, 1.6, 0.1]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.25} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={vacuumPostEdges}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.65} />
            </lineSegments>
          </group>
        ))}

        {/* Crossbar connecting posts at top */}
        <mesh position={[0, 1.56, 0]}>
          <boxGeometry args={[0.08, 0.08, BELT_W + 0.38]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.2} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={vacuumCrossbarEdges} position={[0, 1.56, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.6} />
        </lineSegments>

        {/* Motor housing hanging from crossbar */}
        <mesh position={[0, 1.3, 0]}>
          <boxGeometry args={[0.3, 0.25, 0.3]} />
          <meshBasicMaterial color={GREEN} transparent opacity={0.3} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
        <lineSegments geometry={vacuumMotorEdges} position={[0, 1.3, 0]}>
          <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
        </lineSegments>

        {/* Base foot plates under posts */}
        {([-1, 1] as const).map((zSign) => (
          <group key={`vac-base-${zSign}`} position={[0, 0.025, zSign * (BELT_W / 2 + 0.15)]}>
            <mesh>
              <boxGeometry args={[0.2, 0.05, 0.2]} />
              <meshBasicMaterial color={GREEN} transparent opacity={0.25} toneMapped={false} side={THREE.DoubleSide} />
            </mesh>
            <lineSegments geometry={vacuumBaseEdges}>
              <lineBasicMaterial color={GREEN} transparent opacity={0.6} />
            </lineSegments>
          </group>
        ))}

        {/* Nozzle group — animates downward during complete */}
        <group ref={vacuumNozzleRef} position={[0, 0.85, 0]}>
          {/* Long ribbed hose — extends upward from nozzle into motor housing */}
          <mesh position={[0, 0.595, 0]}>
            <cylinderGeometry args={[0.048, 0.048, 0.75, 8]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.2} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={vacuumHoseCylEdges} position={[0, 0.595, 0]}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.55} />
          </lineSegments>
          {/* Rib rings along hose */}
          <lineSegments geometry={vacuumHoseRibsGeo} position={[0, 0.595, 0]}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.7} />
          </lineSegments>

          {/* Dramatic flared nozzle cone — wide open at bottom */}
          <mesh position={[0, 0.03, 0]}>
            <cylinderGeometry args={[0.04, 0.44, 0.4, 8]} />
            <meshBasicMaterial color={GREEN} transparent opacity={0.25} toneMapped={false} side={THREE.DoubleSide} />
          </mesh>
          <lineSegments geometry={vacuumNozzleEdges} position={[0, 0.03, 0]}>
            <lineBasicMaterial color={GREEN} transparent opacity={0.75} />
          </lineSegments>
        </group>
      </group>

      {/* Complete LED */}
      <mesh ref={led4Ref} position={[S4_X, BELT_Y + 1.47, BELT_W / 2 + 0.22]}>
        <sphereGeometry args={[0.035, 8, 8]} />
        <meshBasicMaterial color={GREEN} transparent opacity={0.1} toneMapped={false} />
      </mesh>

      {/* Digital 1s and 0s accumulating on belt then vacuumed up */}
      <group ref={particlesS4Ref} position={[S4_X, BELT_Y, 0]}>
        {Array.from({ length: 10 }).map((_, i) => (
          <lineSegments key={`ps4-${i}`} geometry={i % 2 === 0 ? digit1Geo : digit0Geo}>
            <lineBasicMaterial color={GREEN} transparent opacity={0} />
          </lineSegments>
        ))}
      </group>
    </group>
  );
}

/* ════════════════════════════════════════════════
   Exported wrapper component
   ════════════════════════════════════════════════ */
export const AssemblyLine3D: React.FC<AssemblyLine3DProps> = ({ phase, progress }) => {
  const label = phase === 'uploading' ? `Uploading\u2026 ${progress}%`
    : phase === 'processing' ? 'Ingesting\u2026'
    : phase === 'embedding' ? 'Embedding vectors\u2026'
    : phase === 'complete' ? 'Complete!'
    : '';

  return (
    <div className="assembly-line-container">
      <Canvas
        gl={{ alpha: true, premultipliedAlpha: false, antialias: true }}
        camera={{ position: [0, 3.5, 8], fov: 38 }}
        onCreated={({ gl }): void => {
          gl.setClearColor(0x000000, 0);
        }}
        style={{ background: 'transparent' }}
      >
        <Suspense fallback={null}>
          <AssemblyLineScene phase={phase} progress={progress} />
          <EffectComposer frameBufferType={HalfFloatType}>
            <Bloom
              luminanceThreshold={0.1}
              luminanceSmoothing={0.9}
              intensity={1.8}
              mipmapBlur
            />
          </EffectComposer>
        </Suspense>
      </Canvas>
      {label && (
        <div className="assembly-line-label">{label}</div>
      )}
    </div>
  );
};
