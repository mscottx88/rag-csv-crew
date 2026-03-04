/**
 * Query Page
 * Natural language query interface with result display.
 * Swaps between QueryInput and ResultDisplay — result area replaces
 * the input form and is internally scrollable.
 */

import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { QueryInput } from '../components/Query/QueryInput';
import { ResultDisplay } from '../components/Query/ResultDisplay';
import * as queriesService from '../services/queries';
import type { Query as QueryType } from '../types';
import './Query.css';

interface LocationState {
  queryText?: string;
  datasetIds?: string[];
}

export const Query: React.FC = () => {
  const location = useLocation();
  const state = location.state as LocationState | null;

  const [currentQuery, setCurrentQuery] = useState<QueryType | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  const handleQuerySubmit = async (query: QueryType): Promise<void> => {
    setCurrentQuery(query);
    setIsPolling(true);

    // Poll for query completion
    try {
      const finalQuery: QueryType = await queriesService.pollUntilComplete(
        query.id,
        (updatedQuery: QueryType): void => {
          setCurrentQuery(updatedQuery);
        }
      );
      setCurrentQuery(finalQuery);
    } catch (err) {
      console.error('Polling error:', err);
    } finally {
      setIsPolling(false);
    }
  };

  const handleCancel = async (): Promise<void> => {
    if (currentQuery) {
      try {
        const cancelledQuery: QueryType = await queriesService.cancel(currentQuery.id);
        setCurrentQuery(cancelledQuery);
        setIsPolling(false);
      } catch (err) {
        console.error('Cancel error:', err);
      }
    }
  };

  const handleBack = (): void => {
    setCurrentQuery(null);
    setIsPolling(false);
  };

  return (
    <div className="query-page">
      <h1>Query Your Data</h1>
      <p className="page-description">
        Ask questions about your data in natural language. Our AI will convert your query into SQL
        and display the results.
      </p>

      {currentQuery ? (
        <div className="query-result-view">
          {!isPolling && (
            <button
              className="back-button"
              onClick={handleBack}
              title="Back to query input"
              aria-label="Back to query input"
            >
              <svg className="back-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 2 L3.5 7 L9 12" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
              </svg>
              New Query
            </button>
          )}
          <ResultDisplay query={currentQuery} onCancel={isPolling ? handleCancel : undefined} />
        </div>
      ) : (
        <QueryInput
          onSubmit={(query) => void handleQuerySubmit(query)}
          isProcessing={isPolling}
          onCancel={() => void handleCancel()}
          initialQueryText={state?.queryText}
          initialDatasetIds={state?.datasetIds}
        />
      )}
    </div>
  );
};
