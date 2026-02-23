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
          <span className="action-icon">🔍</span>
          <h3>Submit a Query</h3>
          <p>Ask questions about your data in natural language</p>
        </div>

        <div className="action-card" onClick={(): void => navigate('/datasets')} role="button" tabIndex={0}>
          <span className="action-icon">📊</span>
          <h3>Manage Datasets</h3>
          <p>Upload and manage your CSV datasets</p>
        </div>

        <div className="action-card" onClick={(): void => navigate('/history')} role="button" tabIndex={0}>
          <span className="action-icon">📜</span>
          <h3>View History</h3>
          <p>Browse your past queries and results</p>
        </div>
      </div>
    </div>
  );
};
