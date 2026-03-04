/**
 * QueryScene — Shared Canvas wrapper for query-phase 3D animations.
 * Transparent background, Bloom glow. No pointer tracking — each 3D
 * object animates autonomously via its own useFrame loop.
 */

import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { HalfFloatType } from 'three';

interface QuerySceneProps {
  children: React.ReactNode;
  cameraZ?: number;
  cameraY?: number;
  fov?: number;
}

export const QueryScene: React.FC<QuerySceneProps> = ({
  children,
  cameraZ = 5,
  cameraY = 0,
  fov = 45,
}) => (
  <Canvas
    gl={{ alpha: true, premultipliedAlpha: false, antialias: true }}
    camera={{ position: [0, cameraY, cameraZ], fov }}
    onCreated={({ gl }): void => {
      gl.setClearColor(0x000000, 0);
    }}
    style={{ background: 'transparent', width: '100%', height: '100%' }}
  >
    <Suspense fallback={null}>
      {children}
      <EffectComposer frameBufferType={HalfFloatType}>
        <Bloom
          luminanceThreshold={0.1}
          luminanceSmoothing={0.9}
          intensity={2.0}
          mipmapBlur
        />
      </EffectComposer>
    </Suspense>
  </Canvas>
);
