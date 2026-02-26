/**
 * Dashboard Page
 * Welcome page with quick navigation
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Dashboard.css';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="dashboard-page">
      <div className="welcome-section">
        <h1>Welcome back, {user?.username}!</h1>
        <p>Get started by uploading a CSV dataset or submitting a natural language query.</p>
      </div>

      <div className="quick-actions">
        <div className="action-card" onClick={(): void => navigate('/query')} role="button" tabIndex={0}>
          <svg className="action-icon-svg action-icon-cyan" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="20" cy="20" r="12" strokeWidth="2" />
            <line x1="29" y1="29" x2="40" y2="40" strokeWidth="2" strokeLinecap="round" />
            <line x1="14" y1="20" x2="26" y2="20" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
            <line x1="17" y1="25" x2="23" y2="25" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
            <line x1="17" y1="15" x2="23" y2="15" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
          </svg>
          <h3>Submit a Query</h3>
          <p>Ask questions about your data in natural language</p>
        </div>

        <div className="action-card" onClick={(): void => navigate('/upload')} role="button" tabIndex={0}>
          <svg className="action-icon-svg action-icon-green" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="8" y="20" width="32" height="24" rx="2" strokeWidth="2" />
            <polyline points="16,28 24,20 32,28" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <line x1="24" y1="20" x2="24" y2="38" strokeWidth="2" strokeLinecap="round" />
            <line x1="14" y1="8" x2="34" y2="8" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
            <line x1="18" y1="13" x2="30" y2="13" strokeWidth="1.5" strokeLinecap="round" opacity="0.4" />
          </svg>
          <h3>Upload CSV</h3>
          <p>Upload a new CSV dataset to query</p>
        </div>

        <div className="action-card" onClick={(): void => navigate('/datasets')} role="button" tabIndex={0}>
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
          <h3>Browse Datasets</h3>
          <p>View and manage your uploaded datasets</p>
        </div>

        <div className="action-card" onClick={(): void => navigate('/history')} role="button" tabIndex={0}>
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
          <h3>View History</h3>
          <p>Browse your past queries and results</p>
        </div>
      </div>
    </div>
  );
};
