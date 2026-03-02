/**
 * Dashboard Page
 * Welcome page with quick navigation and card-expand transition animation.
 *
 * Card clicks trigger a two-part animation:
 * 1. Header scramble + lightning (via shared pageTransition utility)
 * 2. Card expansion overlay (Dashboard-specific, expands from card to grid area)
 *
 * Both overlays are appended to document.body so they persist across route changes.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  createHeaderTransition,
  getRouteConfig,
  isTransitioning,
} from '../utils/pageTransition';
import './Dashboard.css';

/* ── Card definitions ── */

interface CardDef {
  route: string;
  color: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}

const CARDS: CardDef[] = [
  {
    route: '/query',
    color: 'cyan',
    title: 'Submit a Query',
    description: 'Ask questions about your data in natural language',
    icon: (
      <svg className="action-icon-svg action-icon-cyan" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="20" cy="20" r="12" strokeWidth="2" />
        <line x1="29" y1="29" x2="40" y2="40" strokeWidth="2" strokeLinecap="round" />
        <line x1="14" y1="20" x2="26" y2="20" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="17" y1="25" x2="23" y2="25" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="17" y1="15" x2="23" y2="15" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
      </svg>
    ),
  },
  {
    route: '/upload',
    color: 'green',
    title: 'Upload CSV',
    description: 'Upload a new CSV dataset to query',
    icon: (
      <svg className="action-icon-svg action-icon-green" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="20" width="32" height="24" rx="2" strokeWidth="2" />
        <polyline points="16,28 24,20 32,28" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="24" y1="20" x2="24" y2="38" strokeWidth="2" strokeLinecap="round" />
        <line x1="14" y1="8" x2="34" y2="8" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
        <line x1="18" y1="13" x2="30" y2="13" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
      </svg>
    ),
  },
  {
    route: '/datasets',
    color: 'orange',
    title: 'Browse Datasets',
    description: 'View and manage your uploaded datasets',
    icon: (
      <svg className="action-icon-svg action-icon-orange" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="4" width="40" height="40" rx="2" strokeWidth="2" />
        <line x1="4" y1="16" x2="44" y2="16" strokeWidth="1.5" />
        <line x1="4" y1="28" x2="44" y2="28" strokeWidth="1.5" />
        <line x1="18" y1="4" x2="18" y2="44" strokeWidth="1.5" />
        <line x1="32" y1="4" x2="32" y2="44" strokeWidth="1.5" />
        <circle cx="11" cy="10" r="2" strokeWidth="1.5" opacity="0.6" />
        <circle cx="25" cy="22" r="2" strokeWidth="1.5" opacity="0.6" />
        <circle cx="38" cy="34" r="2" strokeWidth="1.5" opacity="0.6" />
      </svg>
    ),
  },
  {
    route: '/history',
    color: 'gold',
    title: 'View History',
    description: 'Browse your past queries and results',
    icon: (
      <svg className="action-icon-svg action-icon-gold" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="24" cy="24" r="18" strokeWidth="2" />
        <circle cx="24" cy="24" r="2" strokeWidth="1.5" />
        <line x1="24" y1="24" x2="24" y2="12" strokeWidth="2" strokeLinecap="round" />
        <line x1="24" y1="24" x2="34" y2="28" strokeWidth="2" strokeLinecap="round" />
        <line x1="24" y1="6" x2="24" y2="9" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="24" y1="39" x2="24" y2="42" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="6" y1="24" x2="9" y2="24" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="39" y1="24" x2="42" y2="24" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
      </svg>
    ),
  },
];

/* ── Dashboard component ── */

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);
  const gridRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const headerOverlayRef = useRef<HTMLDivElement | null>(null);
  const scrambleCancelsRef = useRef<(() => void)[]>([]);
  const [isAnimating, setIsAnimating] = useState<boolean>(false);

  // Clean up overlays if Dashboard unmounts unexpectedly (e.g. sidebar nav during animation)
  useEffect(() => {
    return () => {
      scrambleCancelsRef.current.forEach((cancel) => cancel());
      scrambleCancelsRef.current = [];
      if (overlayRef.current) {
        overlayRef.current.remove();
        overlayRef.current = null;
      }
      if (headerOverlayRef.current) {
        headerOverlayRef.current.remove();
        headerOverlayRef.current = null;
      }
      document.body.classList.remove('has-card-overlay');
    };
  }, []);

  const handleCardClick = useCallback(
    (index: number, route: string, color: string): void => {
      if (isAnimating || isTransitioning()) return;

      const cardEl = cardRefs.current[index];
      const gridEl = gridRef.current;
      if (!cardEl || !gridEl) {
        navigate(route);
        return;
      }

      const destConfig = getRouteConfig(route);
      if (!destConfig) {
        navigate(route);
        return;
      }

      setIsAnimating(true);

      const cardRect = cardEl.getBoundingClientRect();
      const gridRect = gridEl.getBoundingClientRect();

      // ── Header overlay: scramble + lightning (shared utility) ──
      const dashboardEl = gridEl.parentElement;
      const h1El = dashboardEl?.querySelector(':scope > h1') as HTMLElement | null;
      const descEl = dashboardEl?.querySelector(':scope > .page-description') as HTMLElement | null;

      if (h1El && descEl) {
        const headerResult = createHeaderTransition(h1El, descEl, destConfig);
        headerOverlayRef.current = headerResult.overlay;
        scrambleCancelsRef.current = headerResult.cancels;
      }

      // ── Card overlay: expand from card position to grid area ──
      const overlay = document.createElement('div');
      overlay.className = 'card-transition-overlay';
      overlay.setAttribute('data-color', color);
      overlay.innerHTML = cardEl.innerHTML;

      Object.assign(overlay.style, {
        top: `${cardRect.top}px`,
        left: `${cardRect.left}px`,
        width: `${cardRect.width}px`,
        height: `${cardRect.height}px`,
      });

      document.body.appendChild(overlay);
      overlayRef.current = overlay;

      // Trigger expansion on the next frame so the browser paints the start position first
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          Object.assign(overlay.style, {
            top: `${gridRect.top}px`,
            left: `${gridRect.left}px`,
            width: `${gridRect.width}px`,
            height: `${gridRect.height}px`,
          });
        });
      });

      // On expansion complete: navigate, wait for page to render, then reveal
      const onExpanded = (e: TransitionEvent): void => {
        if (e.target !== overlay || e.propertyName !== 'width') return;
        overlay.removeEventListener('transitionend', onExpanded);

        document.body.classList.add('has-card-overlay');

        // Navigate — Dashboard unmounts, destination page mounts underneath
        navigate(route);

        // Wait for React to render + browser to paint the destination page,
        // then fade card overlay out to reveal the fully-rendered page
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            overlay.classList.add('fade-out');

            const headerOv = headerOverlayRef.current;

            const onFaded = (fe: TransitionEvent): void => {
              if (fe.propertyName !== 'opacity') return;
              overlay.removeEventListener('transitionend', onFaded);
              overlay.remove();
              // Remove header overlay instantly — text already matches destination
              if (headerOv) {
                headerOv.remove();
              }
              document.body.classList.remove('has-card-overlay');
              if (overlayRef.current === overlay) {
                overlayRef.current = null;
              }
              headerOverlayRef.current = null;
              scrambleCancelsRef.current = [];
            };
            overlay.addEventListener('transitionend', onFaded);
          });
        });
      };

      overlay.addEventListener('transitionend', onExpanded);
    },
    [isAnimating, navigate],
  );

  return (
    <div className={`dashboard-page${isAnimating ? ' animating' : ''}`}>
      <h1>Welcome back, {user?.username}!</h1>
      <p className="page-description">
        Get started by uploading a CSV dataset or submitting a natural language query.
      </p>

      <div className="quick-actions" ref={gridRef}>
        {CARDS.map((card, i) => (
          <div
            key={card.route}
            className="action-card"
            ref={(el): void => { cardRefs.current[i] = el; }}
            onClick={(): void => handleCardClick(i, card.route, card.color)}
            role="button"
            tabIndex={0}
          >
            {card.icon}
            <h3>{card.title}</h3>
            <p>{card.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
