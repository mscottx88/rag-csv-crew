/**
 * Query History Component
 * Paginated list of past queries with inline expand/collapse results
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as queriesService from '../../services/queries';
import { ResultDisplay } from './ResultDisplay';
import { useQueryReplay } from './useQueryReplay';
import { NeonSelect } from '../NeonSelect/NeonSelect';
import type { Query, QueryHistory as QueryHistoryType, QueryStatus } from '../../types';
import './QueryHistory.css';

interface QueryHistoryProps {
  refresh?: number;
}

export const QueryHistory: React.FC<QueryHistoryProps> = ({ refresh = 0 }) => {
  const navigate = useNavigate();
  const [history, setHistory] = useState<QueryHistoryType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<QueryStatus | undefined>(undefined);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, Query>>({});
  const [detailLoading, setDetailLoading] = useState<string | null>(null);
  const [replayingId, setReplayingId] = useState<string | null>(null);
  const { replayState, startReplay, stopReplay } = useQueryReplay();

  useEffect(() => {
    const loadHistory = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const data: QueryHistoryType = await queriesService.history({
          page: currentPage,
          page_size: 20,
          status: statusFilter,
        });
        setHistory(data);
      } catch (err) {
        setError('Failed to load query history');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    void loadHistory();
  }, [currentPage, statusFilter, refresh]);

  const handleQueryClick = (query: Query): void => {
    const nextId: string | null = expandedId === query.id ? null : query.id;
    setExpandedId(nextId);

    // Fetch full query details (with response) when expanding, if not cached
    if (nextId && !detailCache[nextId]) {
      setDetailLoading(nextId);
      void queriesService.get(nextId).then((full: Query) => {
        setDetailCache((prev: Record<string, Query>) => ({ ...prev, [nextId]: full }));
        setDetailLoading((cur: string | null) => (cur === nextId ? null : cur));
      }).catch((err: unknown) => {
        console.error('Failed to load query details:', err);
        setDetailLoading((cur: string | null) => (cur === nextId ? null : cur));
      });
    }
  };

  // Clear replayingId when replay finishes
  useEffect(() => {
    if (!replayState.isReplaying && replayingId) {
      setReplayingId(null);
    }
  }, [replayState.isReplaying, replayingId]);

  const handleReplay = (query: Query, event: React.MouseEvent): void => {
    event.stopPropagation();

    // If already replaying this query, stop it
    if (replayingId === query.id) {
      stopReplay();
      setReplayingId(null);
      return;
    }

    // Stop any existing replay
    if (replayingId) {
      stopReplay();
    }

    // Expand the item if not already
    if (expandedId !== query.id) {
      setExpandedId(query.id);
    }

    // Use cached detail or fetch it first
    const cached: Query | undefined = detailCache[query.id];
    if (cached?.progress_timeline && cached.progress_timeline.length > 0) {
      setReplayingId(query.id);
      startReplay(cached.progress_timeline);
    } else {
      // Fetch full details then start replay
      setDetailLoading(query.id);
      void queriesService.get(query.id).then((full: Query) => {
        setDetailCache((prev: Record<string, Query>) => ({ ...prev, [query.id]: full }));
        setDetailLoading((cur: string | null) => (cur === query.id ? null : cur));
        if (full.progress_timeline && full.progress_timeline.length > 0) {
          setReplayingId(query.id);
          startReplay(full.progress_timeline);
        }
      }).catch((err: unknown) => {
        console.error('Failed to load query for replay:', err);
        setDetailLoading((cur: string | null) => (cur === query.id ? null : cur));
      });
    }
  };

  const handleRerun = (query: Query, event: React.MouseEvent): void => {
    event.stopPropagation();
    navigate('/query', {
      state: {
        queryText: query.query_text,
        datasetIds: query.dataset_ids || [],
      },
    });
  };

  const handleStatusFilterChange = (status: QueryStatus | undefined): void => {
    setStatusFilter(status);
    setCurrentPage(1);
  };

  const handlePageChange = (page: number): void => {
    setCurrentPage(page);
  };

  const formatDate = (dateStr: string): string => {
    const date: Date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const renderStatusBadge = (status: QueryStatus): JSX.Element => {
    const classMap: Record<QueryStatus, string> = {
      pending: 'status-pending',
      processing: 'status-processing',
      completed: 'status-completed',
      failed: 'status-failed',
      cancelled: 'status-cancelled',
    };

    return (
      <span className={`status-badge ${classMap[status]}`}>
        {status === 'completed' && (
          <svg className="status-check-icon" width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M1.5 5.5 L4 8 L8.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
        )}
        {status}
      </span>
    );
  };

  if (loading) {
    return <div className="history-loading">Loading history...</div>;
  }

  if (error) {
    return (
      <div className="history-error" role="alert">
        {error}
      </div>
    );
  }

  if (!history && !statusFilter) {
    return (
      <div className="history-empty">
        <p>No query history found.</p>
      </div>
    );
  }

  const totalPages: number = history ? Math.ceil(history.total / history.page_size) : 0;

  return (
    <div className="query-history">
      <div className="history-header">
        <h2>Query History</h2>
        <div className="filter-group">
          <label htmlFor="status-filter">Status</label>
          <NeonSelect
            id="status-filter"
            value={statusFilter ?? ''}
            onChange={(val: string): void =>
              handleStatusFilterChange(val ? (val as QueryStatus) : undefined)
            }
            options={[
              { value: '', label: 'All' },
              { value: 'pending', label: 'Pending' },
              { value: 'processing', label: 'Processing' },
              { value: 'completed', label: 'Completed' },
              { value: 'failed', label: 'Failed' },
              { value: 'cancelled', label: 'Cancelled' },
            ]}
            color="gold"
          />
        </div>
      </div>

      {(!history || history.queries.length === 0) ? (
        <div className="history-empty">
          <p>No queries match the selected filter.</p>
        </div>
      ) : (
      <>
      <div className="history-list">
        {history.queries.map((query: Query) => {
          const isExpanded: boolean = expandedId === query.id;

          return (
            <div
              key={query.id}
              className={`history-item ${isExpanded ? 'history-item-expanded' : ''}`}
            >
              <div
                className="history-item-row"
                onClick={(): void => handleQueryClick(query)}
                role="button"
                tabIndex={0}
                onKeyPress={(e): void => {
                  if (e.key === 'Enter') {
                    handleQueryClick(query);
                  }
                }}
              >
                <div className="history-item-header">
                  <span className={`expand-indicator ${isExpanded ? 'expanded' : ''}`}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 1.5 L9.5 6 L3 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                    </svg>
                  </span>
                  <span className="history-query">{query.query_text}</span>
                  <div className="history-item-actions">
                    {renderStatusBadge(query.status)}
                    {query.status === 'completed' && (
                      <button
                        className={`replay-button ${replayingId === query.id ? 'replaying' : ''}`}
                        onClick={(e): void => handleReplay(query, e)}
                        title={replayingId === query.id ? 'Stop replay' : 'Replay execution'}
                        aria-label={`Replay query: ${query.query_text}`}
                      >
                        <svg className="replay-icon" width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <path d="M1.5 1.5 A5 5 0 1 1 1 6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" fill="none" />
                          <path d="M1.5 1.5 L3.5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                          <path d="M1.5 1.5 L1.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                        </svg>
                        {replayingId === query.id ? 'Stop' : 'Replay'}
                      </button>
                    )}
                    <button
                      className="rerun-button"
                      onClick={(e): void => handleRerun(query, e)}
                      title="Re-run this query"
                      aria-label={`Re-run query: ${query.query_text}`}
                    >
                      <svg className="rerun-icon" width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M2 1 L8.5 5 L2 9" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                      </svg>
                      Re-run
                    </button>
                  </div>
                </div>
                <div className="history-item-meta">
                  <span className="history-date">{formatDate(query.submitted_at)}</span>
                  {query.result_count !== undefined && (
                    <span className="history-rows">{query.result_count} rows</span>
                  )}
                  {query.execution_time_ms !== undefined && (
                    <span className="history-time">{query.execution_time_ms}ms</span>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="history-item-detail">
                  {detailLoading === query.id ? (
                    <div className="history-detail-loading">Loading details...</div>
                  ) : replayingId === query.id && replayState.isReplaying ? (
                    <ResultDisplay
                      query={{
                        ...(detailCache[query.id] || query),
                        status: 'processing' as QueryStatus,
                        progress_message: replayState.currentMessage,
                      }}
                    />
                  ) : (
                    <ResultDisplay query={detailCache[query.id] || query} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={(): void => handlePageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="pagination-button"
          >
            Previous
          </button>
          <span className="pagination-info">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={(): void => handlePageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="pagination-button"
          >
            Next
          </button>
        </div>
      )}
      </>
      )}
    </div>
  );
};
