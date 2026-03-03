/**
 * Dashboard Page
 * Welcome page with 3D animated wireframe navigation objects.
 * Uses the shared pageTransition utility for consistent animations.
 */

import React, { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { animatePageTransition, isTransitioning } from '../utils/pageTransition';
import { NeonScene } from '../components/Dashboard3D/NeonScene';
import { CRTTerminal } from '../components/Dashboard3D/CRTTerminal';
import { TapeDrive } from '../components/Dashboard3D/TapeDrive';
import { Database } from '../components/Dashboard3D/Database';
import { DotMatrixPrinter } from '../components/Dashboard3D/DotMatrixPrinter';
import './Dashboard.css';

/* ── Card definitions ── */

interface CardDef {
  route: string;
  color: string;
  title: string;
  description: string;
  Scene: React.FC<{ hovered: boolean }>;
}

const CARDS: CardDef[] = [
  {
    route: '/query',
    color: 'cyan',
    title: 'Submit a Query',
    description: 'Ask questions about your data in natural language',
    Scene: CRTTerminal,
  },
  {
    route: '/upload',
    color: 'green',
    title: 'Upload CSV',
    description: 'Upload a new CSV dataset to query',
    Scene: TapeDrive,
  },
  {
    route: '/datasets',
    color: 'orange',
    title: 'Browse Datasets',
    description: 'View and manage your uploaded datasets',
    Scene: Database,
  },
  {
    route: '/history',
    color: 'gold',
    title: 'View History',
    description: 'Browse your past queries and results',
    Scene: DotMatrixPrinter,
  },
];

/* ── Dashboard component ── */

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  /* Mutable pointer positions — one {x,y} per card, updated on mousemove.
     Using a ref avoids re-renders on every mouse move. */
  const pointersRef = useRef(CARDS.map(() => ({ x: 0, y: 0 })));

  const handlePointerMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>, index: number): void => {
      const rect = e.currentTarget.getBoundingClientRect();
      const ptr = pointersRef.current[index];
      if (!ptr) return;
      // Mutate the existing object so the ref captured by NeonScene stays current
      ptr.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      ptr.y = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    },
    [],
  );

  const handleCardClick = useCallback(
    (route: string): void => {
      if (isTransitioning()) return;
      animatePageTransition(route, navigate);
    },
    [navigate],
  );

  return (
    <div className="dashboard-page">
      <h1>Welcome back, {user?.username}!</h1>
      <p className="page-description">
        Get started by uploading a CSV dataset or submitting a natural language query.
      </p>

      <div className="quick-actions">
        {CARDS.map((card, i) => {
          const isHovered = hoveredIndex === i;
          return (
            <div
              key={card.route}
              className="action-card"
              onClick={(): void => handleCardClick(card.route)}
              onMouseEnter={(): void => setHoveredIndex(i)}
              onMouseLeave={(): void => setHoveredIndex(null)}
              onMouseMove={(e): void => handlePointerMove(e, i)}
              role="button"
              tabIndex={0}
            >
              <div className="action-card-canvas">
                <NeonScene hovered={isHovered} pointer={pointersRef.current[i] ?? { x: 0, y: 0 }}>
                  <card.Scene hovered={isHovered} />
                </NeonScene>
              </div>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
