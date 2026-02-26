/**
 * Sidebar Component
 * Navigation menu for the application
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <nav className="sidebar-nav">
        <NavLink
          to="/"
          data-route=""
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
          end
        >
          <svg className="nav-icon-svg nav-icon-pink" viewBox="0 0 48 48" fill="none">
            <polygon points="24,4 44,16 44,36 24,44 4,36 4,16" strokeWidth="2" />
            <line x1="24" y1="4" x2="24" y2="44" strokeWidth="1.5" opacity="0.4" />
            <line x1="4" y1="16" x2="44" y2="36" strokeWidth="1.5" opacity="0.4" />
            <line x1="44" y1="16" x2="4" y2="36" strokeWidth="1.5" opacity="0.4" />
          </svg>
          <span className="nav-text">Dashboard</span>
        </NavLink>

        <NavLink
          to="/query"
          data-route="query"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <svg className="nav-icon-svg nav-icon-cyan" viewBox="0 0 48 48" fill="none">
            <circle cx="20" cy="20" r="12" strokeWidth="2" />
            <line x1="29" y1="29" x2="40" y2="40" strokeWidth="2" strokeLinecap="round" />
            <line x1="14" y1="20" x2="26" y2="20" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
            <line x1="17" y1="15" x2="23" y2="15" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
          </svg>
          <span className="nav-text">Query</span>
        </NavLink>

        <NavLink
          to="/upload"
          data-route="upload"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <svg className="nav-icon-svg nav-icon-green" viewBox="0 0 48 48" fill="none">
            <rect x="8" y="20" width="32" height="24" rx="2" strokeWidth="2" />
            <polyline points="16,28 24,20 32,28" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <line x1="24" y1="20" x2="24" y2="38" strokeWidth="2" strokeLinecap="round" />
            <line x1="14" y1="8" x2="34" y2="8" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
            <line x1="18" y1="13" x2="30" y2="13" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
          </svg>
          <span className="nav-text">Upload</span>
        </NavLink>

        <NavLink
          to="/datasets"
          data-route="datasets"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <svg className="nav-icon-svg nav-icon-orange" viewBox="0 0 48 48" fill="none">
            <rect x="4" y="4" width="40" height="40" rx="2" strokeWidth="2" />
            <line x1="4" y1="16" x2="44" y2="16" strokeWidth="1.5" />
            <line x1="4" y1="28" x2="44" y2="28" strokeWidth="1.5" />
            <line x1="18" y1="4" x2="18" y2="44" strokeWidth="1.5" />
            <line x1="32" y1="4" x2="32" y2="44" strokeWidth="1.5" />
          </svg>
          <span className="nav-text">Datasets</span>
        </NavLink>

        <NavLink
          to="/history"
          data-route="history"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <svg className="nav-icon-svg nav-icon-gold" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="18" strokeWidth="2" />
            <circle cx="24" cy="24" r="2" strokeWidth="1.5" />
            <line x1="24" y1="24" x2="24" y2="12" strokeWidth="2" strokeLinecap="round" />
            <line x1="24" y1="24" x2="34" y2="28" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span className="nav-text">History</span>
        </NavLink>
      </nav>
    </aside>
  );
};
