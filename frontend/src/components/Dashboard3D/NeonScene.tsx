/**
 * NeonScene — Shared Canvas wrapper for dashboard 3D objects.
 * Provides consistent camera, transparent background, Bloom glow,
 * and pointer-based rotation tracking.
 *
 * The renderer clears to fully transparent so the card's CSS background
 * shows through uniformly. HalfFloatType on the EffectComposer preserves
 * alpha through the Bloom pass.
 *
 * PointerTracker wraps children in a group that:
 *  - When hovered: rotates toward the mouse (±45° max based on distance from center)
 *  - When idle: slowly auto-rotates on Y
 */

import React, { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { HalfFloatType } from 'three';
import * as THREE from 'three';

interface NeonSceneProps {
  children: React.ReactNode;
  hovered: boolean;
  /** Normalised pointer coords (-1 … +1) updated from the HTML card div. */
  pointer: { x: number; y: number };
}

const MAX_ANGLE = Math.PI / 4; // ±45 degrees
const AUTO_SPEED = 0.15;       // rad/s idle auto-rotation

/** Wrapper group that rotates children based on pointer or auto-rotation. */
function PointerTracker({
  children,
  hovered,
  pointer,
}: {
  children: React.ReactNode;
  hovered: boolean;
  pointer: { x: number; y: number };
}): React.JSX.Element {
  const groupRef = useRef<THREE.Group>(null);
  const autoAngleRef = useRef(0);
  const wasHoveredRef = useRef(false);

  useFrame((_, delta) => {
    if (!groupRef.current) return;

    if (hovered) {
      // On first hover frame, normalize rotation.y into [-π, π] so the
      // lerp to the mouse target (±45°) never jumps more than ~180°.
      if (!wasHoveredRef.current) {
        const mod = ((groupRef.current.rotation.y % (Math.PI * 2)) + Math.PI * 3) % (Math.PI * 2) - Math.PI;
        groupRef.current.rotation.y = mod;
        wasHoveredRef.current = true;
      }

      // Rotate proportionally to mouse distance from center
      const targetY = pointer.x * MAX_ANGLE;
      const targetX = pointer.y * MAX_ANGLE;
      const f = Math.min(1, delta * 6);
      groupRef.current.rotation.y += (targetY - groupRef.current.rotation.y) * f;
      groupRef.current.rotation.x += (targetX - groupRef.current.rotation.x) * f;
      // Keep auto-angle in sync so unhover transition is seamless
      autoAngleRef.current = groupRef.current.rotation.y;
    } else {
      wasHoveredRef.current = false;
      // Slow continuous auto-rotation on Y, ease X back to 0
      autoAngleRef.current += delta * AUTO_SPEED;
      const f = Math.min(1, delta * 3);
      groupRef.current.rotation.y += (autoAngleRef.current - groupRef.current.rotation.y) * f;
      groupRef.current.rotation.x += (0 - groupRef.current.rotation.x) * f;
    }
  });

  return <group ref={groupRef}>{children}</group>;
}

export const NeonScene: React.FC<NeonSceneProps> = ({ children, hovered, pointer }) => (
  <Canvas
    className="action-card-canvas"
    gl={{ alpha: true, premultipliedAlpha: false, antialias: true }}
    camera={{ position: [0, 0, 5], fov: 45 }}
    onCreated={({ gl }): void => {
      gl.setClearColor(0x000000, 0);
    }}
    style={{ background: 'transparent' }}
  >
    <Suspense fallback={null}>
      <PointerTracker hovered={hovered} pointer={pointer}>
        {children}
      </PointerTracker>
      <EffectComposer frameBufferType={HalfFloatType}>
        <Bloom
          luminanceThreshold={0.1}
          luminanceSmoothing={0.9}
          intensity={hovered ? 2.5 : 1.5}
          mipmapBlur
        />
      </EffectComposer>
    </Suspense>
  </Canvas>
);
