/**
 * Header Component
 * Application header with title, username, and logout button
 */

import React from 'react';
import { useAuth } from '../../context/AuthContext';
import './Header.css';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();

  const handleLogout = (): void => {
    logout();
  };

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="app-title">RAG CSV Crew</h1>
        </div>

        <div className="header-right">
          {user && (
            <>
              <span className="username">Welcome, {user.username}</span>
              <button onClick={handleLogout} className="logout-button" aria-label="Logout">
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
