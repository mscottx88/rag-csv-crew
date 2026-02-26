/**
 * History Page
 * View past queries and their results
 */

import React from 'react';
import { QueryHistory } from '../components/Query/QueryHistory';
import './History.css';

export const History: React.FC = () => {
  return (
    <div className="history-page">
      <h1>Query History</h1>
      <p className="page-description">
        Browse your past queries and view their results. Click on any query to expand the full details.
      </p>

      <QueryHistory />
    </div>
  );
};
