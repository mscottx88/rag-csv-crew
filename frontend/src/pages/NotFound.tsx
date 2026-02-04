/**
 * Not Found Page (404)
 * Displayed when user navigates to an invalid route
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import './NotFound.css';

export const NotFound: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="not-found-page">
      <div className="not-found-content">
        <h1>404</h1>
        <h2>Page Not Found</h2>
        <p>The page you're looking for doesn't exist or has been moved.</p>
        <button onClick={(): void => navigate('/')} className="home-button">
          Go to Dashboard
        </button>
      </div>
    </div>
  );
};
