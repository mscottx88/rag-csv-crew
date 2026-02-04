/**
 * Query Page
 * Natural language query interface with result display
 */

import React, { useState } from 'react';
import { QueryInput } from '../components/Query/QueryInput';
import { ResultDisplay } from '../components/Query/ResultDisplay';
import * as queriesService from '../services/queries';
import type { Query as QueryType } from '../types';
import './Query.css';

export const Query: React.FC = () => {
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

  return (
    <div className="query-page">
      <h1>Query Your Data</h1>
      <p className="page-description">
        Ask questions about your data in natural language. Our AI will convert your query into SQL
        and display the results.
      </p>

      <QueryInput
        onSubmit={handleQuerySubmit}
        isProcessing={isPolling}
        onCancel={handleCancel}
      />

      {currentQuery && <ResultDisplay query={currentQuery} onCancel={isPolling ? handleCancel : undefined} />}
    </div>
  );
};
