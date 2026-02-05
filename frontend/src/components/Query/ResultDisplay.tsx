/**
 * Result Display Component
 * Displays query results with HTML rendering and metadata
 */

import React from 'react';
import type { Query, Dataset } from '../../types';
import './ResultDisplay.css';

interface ResultDisplayProps {
  query: Query;
  datasets?: Dataset[];
  onCancel?: () => void;
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ query, datasets, onCancel }) => {
  const renderStatus = (): JSX.Element => {
    switch (query.status) {
      case 'pending':
        return <div className="status-badge status-pending">Pending</div>;
      case 'processing':
        return <div className="status-badge status-processing">Processing...</div>;
      case 'completed':
        return <div className="status-badge status-completed">Completed</div>;
      case 'failed':
        return <div className="status-badge status-failed">Failed</div>;
      case 'cancelled':
        return <div className="status-badge status-cancelled">Cancelled</div>;
      default:
        return <div className="status-badge">Unknown</div>;
    }
  };

  const renderDatasets = (): JSX.Element | null => {
    if (!query.dataset_ids || query.dataset_ids.length === 0) {
      return (
        <div className="query-datasets">
          <span className="datasets-label">Datasets:</span>
          <span className="datasets-value">All datasets</span>
        </div>
      );
    }

    // Find dataset names from IDs
    const datasetNames: string[] = query.dataset_ids
      .map((id: string) => {
        const dataset: Dataset | undefined = datasets?.find((d: Dataset) => d.id === id);
        return dataset?.filename || id;
      });

    return (
      <div className="query-datasets">
        <span className="datasets-label">Datasets:</span>
        <span className="datasets-value">{datasetNames.join(', ')}</span>
      </div>
    );
  };

  const renderMetadata = (): JSX.Element | null => {
    if (query.status !== 'completed') {
      return null;
    }

    const confidenceScore = query.response?.confidence_score;

    return (
      <div className="metadata">
        {query.execution_time_ms !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Execution Time:</span>
            <span className="metadata-value">{query.execution_time_ms}ms</span>
          </div>
        )}
        {query.result_count !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Rows:</span>
            <span className="metadata-value">{query.result_count.toLocaleString()}</span>
          </div>
        )}
        {confidenceScore !== undefined && (
          <div className="metadata-item">
            <span className="metadata-label">Confidence:</span>
            <span className="metadata-value">{(confidenceScore * 100).toFixed(1)}%</span>
          </div>
        )}
      </div>
    );
  };

  const renderContent = (): JSX.Element => {
    if (query.status === 'pending' || query.status === 'processing') {
      return (
        <div className="result-processing">
          <div className="spinner" />
          <p>Processing your query...</p>
          {onCancel && (
            <button onClick={onCancel} className="cancel-button">
              Cancel Query
            </button>
          )}
        </div>
      );
    }

    if (query.status === 'failed') {
      return (
        <div className="result-error">
          <h3>Query Failed</h3>
          <p>{query.error_message || 'An error occurred while processing your query.'}</p>
        </div>
      );
    }

    if (query.status === 'cancelled') {
      return (
        <div className="result-cancelled">
          <h3>Query Cancelled</h3>
          <p>The query was cancelled before completion.</p>
        </div>
      );
    }

    if (query.status === 'completed' && query.response?.html_content) {
      return (
        <div
          className="result-html"
          dangerouslySetInnerHTML={{ __html: query.response.html_content }}
        />
      );
    }

    return (
      <div className="result-empty">
        <p>No results available.</p>
      </div>
    );
  };

  return (
    <div className="result-display">
      <div className="result-header">
        <h3>Query Result</h3>
        {renderStatus()}
      </div>

      <div className="result-query">
        <strong>Query:</strong> {query.query_text}
      </div>

      {renderDatasets()}

      {renderMetadata()}

      <div className="result-content">{renderContent()}</div>
    </div>
  );
};
