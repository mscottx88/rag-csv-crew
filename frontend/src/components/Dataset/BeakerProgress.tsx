/**
 * Beaker Progress Component
 * Animated SVG lab beaker that fills with liquid to show upload progress
 */

import React from 'react';
import './BeakerProgress.css';

interface BeakerProgressProps {
  progress: number; // 0–100
}

const INNER_TOP: number = 21;
const INNER_BOTTOM: number = 104;
const INNER_HEIGHT: number = INNER_BOTTOM - INNER_TOP; // 83 SVG units

export const BeakerProgress: React.FC<BeakerProgressProps> = ({ progress }) => {
  const clampedProgress: number = Math.min(100, Math.max(0, progress));
  const liquidTop: number = INNER_BOTTOM - (clampedProgress / 100) * INNER_HEIGHT;
  const liquidHeight: number = INNER_BOTTOM - liquidTop + 12; // extend past bottom, clipped

  return (
    <div className="beaker-progress-container">
      <svg
        viewBox="0 0 100 120"
        className="beaker-svg"
        role="img"
        aria-label={`Upload progress: ${clampedProgress}%`}
      >
        <defs>
          {/* Clip liquid fill to beaker interior */}
          <clipPath id="beaker-clip">
            <path d="M 25 21 L 25 104 Q 25 113 50 113 Q 75 113 75 104 L 75 21 Z" />
          </clipPath>

          {/* Gradient for liquid */}
          <linearGradient id="liquid-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b9ff3" />
            <stop offset="100%" stopColor="#4f5fc4" />
          </linearGradient>
        </defs>

        {/* ── Liquid fill ── */}
        <rect
          className="beaker-fill"
          x="0"
          y={liquidTop}
          width="100"
          height={liquidHeight}
          fill="url(#liquid-grad)"
          opacity="0.82"
          clipPath="url(#beaker-clip)"
        />

        {/* ── Bubbles (visible only when liquid is present) ── */}
        {clampedProgress > 4 && (
          <g clipPath="url(#beaker-clip)">
            <circle className="bubble bubble-a" cx="38" cy="101" r="2.4" fill="white" opacity="0.55" />
            <circle className="bubble bubble-b" cx="57" cy="101" r="1.7" fill="white" opacity="0.45" />
            <circle className="bubble bubble-c" cx="47" cy="101" r="1.2" fill="white" opacity="0.50" />
          </g>
        )}

        {/* ── Glass outline ── */}

        {/* Flat rim at top (wider than body) */}
        <rect x="14" y="13" width="72" height="7" rx="1.5"
          fill="none" stroke="#667eea" strokeWidth="2" />

        {/* Left body wall */}
        <line x1="22" y1="20" x2="22" y2="106"
          stroke="#667eea" strokeWidth="2" strokeLinecap="round" />

        {/* Right body wall */}
        <line x1="78" y1="20" x2="78" y2="106"
          stroke="#667eea" strokeWidth="2" strokeLinecap="round" />

        {/* Rounded bottom */}
        <path d="M 22 106 Q 22 116 50 116 Q 78 116 78 106"
          fill="none" stroke="#667eea" strokeWidth="2" strokeLinecap="round" />

        {/* Graduation marks on right inner wall */}
        <line x1="69" y1="38" x2="75" y2="38" stroke="#667eea" strokeWidth="1.2" opacity="0.45" />
        <line x1="69" y1="54" x2="75" y2="54" stroke="#667eea" strokeWidth="1.2" opacity="0.45" />
        <line x1="69" y1="70" x2="75" y2="70" stroke="#667eea" strokeWidth="1.2" opacity="0.45" />
        <line x1="69" y1="86" x2="75" y2="86" stroke="#667eea" strokeWidth="1.2" opacity="0.45" />

        {/* Glass shine / reflection on left inner wall */}
        <line x1="31" y1="23" x2="29" y2="99"
          stroke="white" strokeWidth="2.5" opacity="0.22" strokeLinecap="round" />

        {/* Secondary faint reflection */}
        <line x1="36" y1="23" x2="35" y2="60"
          stroke="white" strokeWidth="1" opacity="0.12" strokeLinecap="round" />
      </svg>

      <div className="beaker-progress-label">{clampedProgress}%</div>
    </div>
  );
};
