/**
 * History Page
 * View past queries and their results
 */

import React, { useState } from 'react';
import { QueryHistory } from '../components/Query/QueryHistory';
import { ResultDisplay } from '../components/Query/ResultDisplay';
import type { Query } from '../types';
import './History.css';

export const History: React.FC = () => {
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);

  const handleQuerySelect = (query: Query): void => {
    setSelectedQuery(query);
  };

  return (
    <div className="history-page">
      <h1>Query History</h1>
      <p className="page-description">
        Browse your past queries and view their results. Click on any query to see the full details.
      </p>

      <div className="history-layout">
        <div className="history-list-section">
          <QueryHistory onQuerySelect={handleQuerySelect} />
        </div>

        {selectedQuery && (
          <div className="history-result-section">
            <ResultDisplay query={selectedQuery} />
          </div>
        )}
      </div>
    </div>
  );
};
