/**
 * Result Display Component
 * Displays query results with HTML rendering and metadata
 */

import React, { useRef, useEffect, useState } from 'react';
import type { Query, Dataset } from '../../types';
import * as datasetsService from '../../services/datasets';
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
  onCancel?: () => void;
}

type QueryStage = 'search' | 'analyze' | 'sql' | 'execute' | 'process' | 'html';

/** Ordered pipeline stages — index determines forward-only progression. */
const STAGE_ORDER: QueryStage[] = ['search', 'analyze', 'sql', 'execute', 'process', 'html'];

/** Minimum time each animation stage is displayed, even if the backend moves faster. */
const MIN_STAGE_MS = 1500;

/**
 * Map a backend progress_message to a pipeline stage.
 *
 * Uses ordered prefix/phrase matching against known backend messages to avoid
 * ambiguous keyword collisions (e.g. "data value search" during analyze phase).
 *
 * Pipeline: search → analyze → sql → execute → process → html
 */
function getQueryStage(message: string): QueryStage {
  const m: string = message.toLowerCase();

  // ── html: Result Analyst formatting ──
  if (m.includes('result analyst') || m.includes('formatting result')) return 'html';

  // ── process: final row processing + completion ──
  if (m.startsWith('query completed') || m.startsWith('completed successfully')) return 'process';

  // ── execute: running SQL against the database ──
  if (m.startsWith('executing sql') || m.includes('validating syntax')) return 'execute';

  // ── sql: generation, schema inspection, validation, parameter extraction ──
  if (
    m.includes('generating sql') || m.includes('sql generator')
    || m.includes('schema inspector') || m.includes('loading database schema')
    || m.includes('crewai') || m.includes('agent') || m.includes('translating')
    || m.includes('cleaning sql') || m.includes('validating sql')
    || m.includes('sql validation') || m.includes('parameterized')
    || m.includes('extracting') || m.includes('filter keyword')
    || m.includes('matched values') || m.includes('agent execution')
    || m.includes('collaborating') || m.includes('optimizing')
    || m.includes('mapping columns') || m.includes('where clauses')
    || m.includes('finalizing') || m.includes('relationships between')
  ) return 'sql';

  // ── analyze: confidence scoring, data-value search, merging, clarification ──
  if (
    m.includes('confidence') || m.includes('analyzing')
    || m.includes('query type') || m.includes('clarification')
    || m.includes('merging') || m.includes('data value')
    || m.includes('recalculating') || m.includes('improved to')
    || m.includes('low confidence')
  ) return 'analyze';

  // ── search: hybrid/vector/full-text/exact search ──
  if (
    m.includes('hybrid search') || m.includes('search thread')
    || m.includes('vector') || m.includes('full-text')
    || m.includes('exact match') || m.includes('fusing')
    || m.includes('deduplicating') || m.includes('fusion')
    || m.includes('parallel search') || m.includes('starting hybrid')
    || m.includes('columns found') || m.includes('matches')
  ) return 'search';

  // ── initial messages map to search (first stage) ──
  if (m.includes('starting query') || m === '') return 'search';

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

export const ResultDisplay: React.FC<ResultDisplayProps> = ({ query, onCancel }) => {
  /** High-water mark for stage pips — tracks displayStageIdx, never regresses. */
  const highWaterRef = useRef<number>(0);
  /**
   * True if this component instance ever observed a pending/processing status.
   * Prevents the post-completion animation from firing when a completed query is
   * expanded in history (where the component mounts directly into completed state).
   */
  const wasProcessingRef = useRef<boolean>(
    query.status === 'pending' || query.status === 'processing',
  );
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  /**
   * displayStageIdx — the stage index currently shown in the animation.
   * Advances toward detectedIndex one step at a time, with a minimum
   * dwell of MIN_STAGE_MS per stage so every animation gets screen time.
   */
  const [displayStageIdx, setDisplayStageIdx] = useState<number>(0);
  const displayStageStartRef = useRef<number>(Date.now());

  // Fetch datasets for name resolution
  useEffect(() => {
    if (query.dataset_ids && query.dataset_ids.length > 0) {
      void datasetsService.list().then((data) => {
        setDatasets(data.datasets);
      }).catch(() => {
        // Silently fail — will show truncated IDs as fallback
      });
    }
  }, [query.dataset_ids]);

  // Track whether this instance ever saw an active processing state.
  useEffect(() => {
    if (query.status === 'pending' || query.status === 'processing') {
      wasProcessingRef.current = true;
    }
  }, [query.status]);

  // Reset display stage and high-water mark when a new query starts.
  useEffect(() => {
    setDisplayStageIdx(0);
    displayStageStartRef.current = Date.now();
    highWaterRef.current = 0;
  }, [query.id]);

  // Derive the target stage from the latest backend message.
  const detectedStage: QueryStage = getQueryStage(query.progress_message || '');
  const detectedIndex: number = STAGE_ORDER.indexOf(detectedStage);

  /**
   * When the backend reports completed (and this component witnessed processing),
   * keep driving displayStageIdx all the way to the last stage so every animation
   * (including 'html') gets its screen time.
   * If the component mounted directly into completed (history view), skip animation.
   */
  const effectiveDetectedIndex: number =
    query.status === 'completed' && wasProcessingRef.current
      ? STAGE_ORDER.length - 1
      : detectedIndex;

  /**
   * Step displayStageIdx toward effectiveDetectedIndex one stage at a time,
   * waiting at least MIN_STAGE_MS before each advance.
   * Continues running after status=completed only if wasProcessingRef is set.
   */
  useEffect(() => {
    const shouldAdvance =
      query.status === 'pending' ||
      query.status === 'processing' ||
      (query.status === 'completed' && wasProcessingRef.current && displayStageIdx < STAGE_ORDER.length - 1);
    if (!shouldAdvance) return;
    if (displayStageIdx >= effectiveDetectedIndex) return;

    const elapsed: number = Date.now() - displayStageStartRef.current;
    const delay: number = Math.max(0, MIN_STAGE_MS - elapsed);

    const timer: ReturnType<typeof setTimeout> = setTimeout(() => {
      displayStageStartRef.current = Date.now();
      setDisplayStageIdx(prev => Math.min(prev + 1, STAGE_ORDER.length - 1));
    }, delay);

    return (): void => { clearTimeout(timer); };
  }, [displayStageIdx, effectiveDetectedIndex, query.status]);

  const renderStatus = (): JSX.Element => {
    switch (query.status) {
      case 'pending':
        return <div className="status-badge status-pending">Pending</div>;
      case 'processing':
        return <div className="status-badge status-processing">Processing...</div>;
      case 'completed':
        return <div className="status-badge status-completed"><svg className="status-check-icon" width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1.5 5.5 L4 8 L8.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" /></svg>Completed</div>;
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
        const dataset: Dataset | undefined = datasets.find((d: Dataset) => d.id === id);
        return dataset?.filename || id.slice(0, 8);
      });

    const count: number = datasetNames.length;

    return (
      <div className="query-datasets">
        <span className="datasets-label">Datasets:</span>
        <span className="datasets-value">
          {count === 1 ? datasetNames[0] : `${count} selected`}
        </span>
        {count > 1 && (
          <span className="datasets-list">{datasetNames.join(', ')}</span>
        )}
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
    // Show animation while processing, or while we're still playing remaining stages
    // after the backend has completed (so html stage always gets its MIN_STAGE_MS).
    const isShowingAnimation =
      query.status === 'pending' ||
      query.status === 'processing' ||
      (query.status === 'completed' && wasProcessingRef.current && displayStageIdx < STAGE_ORDER.length - 1);

    if (isShowingAnimation) {
      const message: string = query.progress_message || '';

      /* displayStageIdx is the throttled index — drives both animation and pips. */
      const displayStage: QueryStage = STAGE_ORDER[displayStageIdx] ?? 'search';
      const label: string = getStageLabel(displayStage);

      /* High-water mark tracks the display stage (stays in sync with animation). */
      if (displayStageIdx > highWaterRef.current) {
        highWaterRef.current = displayStageIdx;
      }

      return (
        <div className="result-processing">
          <div className="query-animation-wrap">
            {/* Animation matches the throttled display stage */}
            {renderAnimation(displayStage, label)}

            {message && (
              <p className="query-progress-message">{message}</p>
            )}

            {/* Stage indicator pips — advance with display stage */}
            <div className="query-stages">
              {STAGE_ORDER.map(
                (s: QueryStage, i: number) => (
                  <div
                    key={s}
                    className={`query-stage-pip ${displayStage === s ? 'active' : ''} ${i <= highWaterRef.current ? 'reached' : ''}`}
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
