/**
 * Loading Spinner Component
 * Reusable loading indicator for async operations
 */

import React from 'react';
import './LoadingSpinner.css';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'small' | 'medium' | 'large';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Loading...',
  size = 'medium',
}) => {
  return (
    <div className="loading-spinner-container">
      <div className={`spinner spinner-${size}`} role="status" aria-live="polite" />
      {message && <p className="spinner-message">{message}</p>}
    </div>
  );
};
