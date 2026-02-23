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
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
          end
        >
          <span className="nav-icon">🏠</span>
          <span className="nav-text">Dashboard</span>
        </NavLink>

        <NavLink
          to="/query"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-icon">🔍</span>
          <span className="nav-text">Query</span>
        </NavLink>

        <NavLink
          to="/datasets"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-icon">📊</span>
          <span className="nav-text">Datasets</span>
        </NavLink>

        <NavLink
          to="/history"
          className={({ isActive }): string => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-icon">📜</span>
          <span className="nav-text">History</span>
        </NavLink>
      </nav>
    </aside>
  );
};
