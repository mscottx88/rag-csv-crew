/**
 * Result Display Component
 * Displays query results with HTML rendering and metadata
 */

import React, { useRef, useEffect } from 'react';
import type { Query, Dataset } from '../../types';
import { AgentConsole } from './AgentConsole';
import { SearchProgress } from './SearchProgress';
import { AnalyzeProgress } from './AnalyzeProgress';
import { SQLProgress } from './SQLProgress';
import { ExecuteProgress } from './ExecuteProgress';
import { ProcessProgress } from './ProcessProgress';
import { HTMLProgress } from './HTMLProgress';
import './ResultDisplay.css';

interface ResultDisplayProps {
  query: Query;
  datasets?: Dataset[];
  onCancel?: () => void;
}

type QueryStage = 'search' | 'analyze' | 'sql' | 'execute' | 'process' | 'html';

/** Ordered pipeline stages — index determines forward-only progression. */
const STAGE_ORDER: QueryStage[] = ['search', 'analyze', 'sql', 'execute', 'process', 'html'];

/**
 * Map a backend progress_message to a pipeline stage.
 *
 * Checks are ordered to match the real backend pipeline so that when a message
 * is ambiguous (e.g. "Executing SQL query") the LATER stage wins — we test
 * later stages first and fall through to earlier ones.
 *
 * Pipeline: search → analyze → sql → execute → process → html
 */
function getQueryStage(message: string): QueryStage {
  const m: string = message.toLowerCase();

  // 6. HTML — formatting final output (test first — most specific)
  if (m.includes('html') || m.includes('formatting') || m.includes('result analyst')) return 'html';

  // 5. Process — collating returned rows
  if (m.includes('processing') || m.includes('rows') || m.includes('completed')) return 'process';

  // 4. Execute — running the query against the database
  if (m.includes('executing') || m.includes('database')) return 'execute';

  // 3. SQL — generation, validation, Schema Inspector agent
  if (m.includes('sql') || m.includes('translating') || m.includes('schema inspector')
    || m.includes('syntax')) return 'sql';

  // 2. Analyze — confidence scoring, query-type classification
  if (m.includes('analyzing') || m.includes('confidence') || m.includes('query type')
    || m.includes('clarification') || m.includes('merging')) return 'analyze';

  // 1. Search — hybrid/vector/data-value search for relevant columns
  if (m.includes('search') || m.includes('scanning') || m.includes('keyword')
    || m.includes('column') || m.includes('hybrid')) return 'search';

  return 'search';
}

function getStageLabel(stage: QueryStage): string {
  switch (stage) {
    case 'search': return 'Searching columns...';
    case 'analyze': return 'Analyzing results...';
    case 'sql': return 'Generating SQL...';
    case 'execute': return 'Executing query...';
    case 'process': return 'Processing rows...';
    case 'html': return 'Formatting output...';
  }
}

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ query, datasets, onCancel }) => {
  /** High-water mark: once we reach stage N we never regress below it. */
  const highWaterRef = useRef<number>(0);

  // Reset the high-water mark when the query changes or finishes.
  useEffect(() => {
    if (query.status !== 'pending' && query.status !== 'processing') {
      highWaterRef.current = 0;
    }
  }, [query.id, query.status]);

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
            <span className="metadata-value">{(query.execution_time_ms / 1000).toFixed(2)}s</span>
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
      case 'html':    return <HTMLProgress label={label} />;
    }
  };

  const renderContent = (): JSX.Element => {
    if (query.status === 'pending' || query.status === 'processing') {
      const message: string = query.progress_message || '';
      const detectedStage: QueryStage = getQueryStage(message);
      const detectedIndex: number = STAGE_ORDER.indexOf(detectedStage);

      // Enforce monotonic forward progression — never regress, and advance
      // by at most one step at a time so every phase gets shown.
      if (detectedIndex > highWaterRef.current) {
        highWaterRef.current = Math.min(detectedIndex, highWaterRef.current + 1);
      }

      const stage: QueryStage = STAGE_ORDER[highWaterRef.current];
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
              {(['search', 'analyze', 'sql', 'execute', 'process', 'html'] as QueryStage[]).map(
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
