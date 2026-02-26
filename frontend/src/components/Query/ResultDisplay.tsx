/**
 * Result Display Component
 * Displays query results with HTML rendering and metadata
 */

import React from 'react';
import type { Query, Dataset } from '../../types';
import { AgentConsole } from './AgentConsole';
import { SearchProgress } from './SearchProgress';
import { AnalyzeProgress } from './AnalyzeProgress';
import { SQLProgress } from './SQLProgress';
import { ExecuteProgress } from './ExecuteProgress';
import { ProcessProgress } from './ProcessProgress';
import './ResultDisplay.css';

interface ResultDisplayProps {
  query: Query;
  datasets?: Dataset[];
  onCancel?: () => void;
}

type QueryStage = 'search' | 'analyze' | 'sql' | 'execute' | 'process' | 'working';

function getQueryStage(message: string): QueryStage {
  if (message.includes('search') || message.includes('column')) return 'search';
  if (message.includes('Schema Inspector') || message.includes('analyzing')) return 'analyze';
  if (message.includes('SQL') || message.includes('translating')) return 'sql';
  if (message.includes('executing') || message.includes('query')) return 'execute';
  if (message.includes('processing') || message.includes('rows')) return 'process';
  return 'working';
}

function getStageLabel(stage: QueryStage): string {
  switch (stage) {
    case 'search': return 'Searching...';
    case 'analyze': return 'Analyzing...';
    case 'sql': return 'Generating SQL...';
    case 'execute': return 'Executing...';
    case 'process': return 'Processing...';
    default: return 'Working...';
  }
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

  const renderAnimation = (stage: QueryStage, label: string): JSX.Element => {
    switch (stage) {
      case 'search':  return <SearchProgress label={label} />;
      case 'analyze': return <AnalyzeProgress label={label} />;
      case 'sql':     return <SQLProgress label={label} />;
      case 'execute': return <ExecuteProgress label={label} />;
      case 'process': return <ProcessProgress label={label} />;
      default:        return <SearchProgress label={label} />;
    }
  };

  const renderContent = (): JSX.Element => {
    if (query.status === 'pending' || query.status === 'processing') {
      const message: string = query.progress_message || '';
      const stage: QueryStage = getQueryStage(message);
      const label: string = getStageLabel(stage);

      return (
        <div className="result-processing">
          <div className="query-animation-wrap">
            {renderAnimation(stage, label)}

            {message && (
              <p className="query-progress-message">{message}</p>
            )}

            {/* Stage indicator bar */}
            <div className="query-stages">
              {(['search', 'analyze', 'sql', 'execute', 'process'] as QueryStage[]).map(
                (s: QueryStage) => (
                  <div
                    key={s}
                    className={`query-stage-pip ${stage === s ? 'active' : ''}`}
                    title={getStageLabel(s)}
                  />
                )
              )}
            </div>

            {onCancel && (
              <button onClick={onCancel} className="cancel-query-btn">
                ✕ Cancel
              </button>
            )}
          </div>
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

      <AgentConsole agentLogs={query.agent_logs} />
    </div>
  );
};
