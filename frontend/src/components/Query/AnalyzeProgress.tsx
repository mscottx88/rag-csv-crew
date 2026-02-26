/**
 * AnalyzeProgress Component
 * Wireframe circuit/node graph — a cyan signal dot travels from node to node
 * lighting up each visited node. Represents the "Schema Inspector / analyzing" phase.
 * Color: cyan (#00eeff)
 */

import React, { useEffect, useRef, useState } from 'react';
import './AnalyzeProgress.css';

interface AnalyzeProgressProps {
  label?: string;
}

interface GraphNode {
  x: number;
  y: number;
}

interface GraphEdge {
  from: number;
  to: number;
}

// 9-node graph arranged in a diamond/grid pattern
const NODES: GraphNode[] = [
  { x: 50, y: 12 },  // 0 top
  { x: 22, y: 32 },  // 1 upper-left
  { x: 78, y: 32 },  // 2 upper-right
  { x: 12, y: 58 },  // 3 mid-left
  { x: 50, y: 50 },  // 4 center
  { x: 88, y: 58 },  // 5 mid-right
  { x: 22, y: 80 },  // 6 lower-left
  { x: 78, y: 80 },  // 7 lower-right
  { x: 50, y: 100 }, // 8 bottom
];

const EDGES: GraphEdge[] = [
  { from: 0, to: 1 }, { from: 0, to: 2 },
  { from: 1, to: 3 }, { from: 1, to: 4 },
  { from: 2, to: 4 }, { from: 2, to: 5 },
  { from: 3, to: 6 },
  { from: 4, to: 6 }, { from: 4, to: 7 },
  { from: 5, to: 7 },
  { from: 6, to: 8 }, { from: 7, to: 8 },
];

const COLOR: string = '#00eeff';
const SIGNAL_SPEED: number = 0.022;

export const AnalyzeProgress: React.FC<AnalyzeProgressProps> = ({ label = 'Analyzing...' }) => {
  const edgeIdxRef = useRef<number>(0);
  const progressRef = useRef<number>(0);
  const litNodesRef = useRef<Set<number>>(new Set<number>([0]));
  const rafRef = useRef<number>(0);
  const [, tick] = useState<number>(0);

  useEffect(() => {
    const loop = (): void => {
      progressRef.current += SIGNAL_SPEED;

      if (progressRef.current >= 1) {
        progressRef.current = 0;
        const edge: GraphEdge = EDGES[edgeIdxRef.current]!;
        litNodesRef.current.add(edge.to);
        edgeIdxRef.current = (edgeIdxRef.current + 1) % EDGES.length;
        // Reset after a full pass
        if (edgeIdxRef.current === 0) {
          litNodesRef.current = new Set<number>([0]);
        }
      }

      tick((n: number) => n + 1);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return (): void => { cancelAnimationFrame(rafRef.current); };
  }, []);

  const currentEdge: GraphEdge = EDGES[edgeIdxRef.current]!;
  const fromNode: GraphNode = NODES[currentEdge.from]!;
  const toNode: GraphNode = NODES[currentEdge.to]!;
  const t: number = progressRef.current;
  const sigX: number = fromNode.x + (toNode.x - fromNode.x) * t;
  const sigY: number = fromNode.y + (toNode.y - fromNode.y) * t;
  const litNodes: Set<number> = litNodesRef.current;

  return (
    <div className="analyze-progress-container">
      <svg viewBox="0 0 100 115" className="analyze-svg" role="img" aria-label="Analyzing schema">
        <defs>
          <filter id="anly-bloom" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="0" y="0" width="100" height="115" fill="#000" />

        {/* Edges */}
        {EDGES.map((e: GraphEdge, i: number) => {
          const from: GraphNode = NODES[e.from]!;
          const to: GraphNode = NODES[e.to]!;
          const isActive: boolean = i === edgeIdxRef.current;
          return (
            <line
              key={i}
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={COLOR}
              strokeWidth={isActive ? 1.2 : 0.5}
              opacity={isActive ? 0.9 : 0.18}
            />
          );
        })}

        {/* Nodes + signal */}
        <g filter="url(#anly-bloom)">
          {NODES.map((n: GraphNode, i: number) => {
            const isLit: boolean = litNodes.has(i);
            return (
              <g key={i}>
                <circle
                  cx={n.x} cy={n.y}
                  r={isLit ? 4.5 : 3}
                  fill={isLit ? COLOR : '#000'}
                  stroke={COLOR}
                  strokeWidth={isLit ? 1.5 : 0.8}
                  opacity={isLit ? 1 : 0.35}
                />
                {/* Small inner square for variety */}
                {isLit && (
                  <rect
                    x={n.x - 1.5} y={n.y - 1.5}
                    width="3" height="3"
                    fill="#000" stroke="none"
                  />
                )}
              </g>
            );
          })}

          {/* Signal dot */}
          <circle cx={sigX} cy={sigY} r="3.5" fill={COLOR} opacity="1" />
          {/* Signal trail */}
          <circle cx={sigX} cy={sigY} r="6" fill={COLOR} opacity="0.18" />
        </g>
      </svg>
      <div className="analyze-progress-label">{label}</div>
    </div>
  );
};
