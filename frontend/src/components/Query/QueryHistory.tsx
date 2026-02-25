/**
 * Query History Component
 * Paginated list of past queries with status filtering
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import * as queriesService from '../../services/queries';
import type { Query, QueryHistory as QueryHistoryType, QueryStatus } from '../../types';
import './QueryHistory.css';

interface QueryHistoryProps {
  onQuerySelect?: (query: Query) => void;
  refresh?: number;
}

export const QueryHistory: React.FC<QueryHistoryProps> = ({ onQuerySelect, refresh = 0 }) => {
  const navigate = useNavigate();
  const [history, setHistory] = useState<QueryHistoryType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<QueryStatus | undefined>(undefined);
  const [currentPage, setCurrentPage] = useState<number>(1);

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
    if (onQuerySelect) {
      onQuerySelect(query);
    }
  };

  const handleRerun = (query: Query, event: React.MouseEvent): void => {
    // Stop propagation to prevent triggering handleQueryClick
    event.stopPropagation();

    // Navigate to Query page with pre-filled query text and dataset IDs
    navigate('/query', {
      state: {
        queryText: query.query_text,
        datasetIds: query.dataset_ids || [],
      },
    });
  };

  const handleStatusFilterChange = (status: QueryStatus | undefined): void => {
    setStatusFilter(status);
    setCurrentPage(1); // Reset to first page
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

    return <span className={`status-badge ${classMap[status]}`}>{status}</span>;
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

  if (!history || history.queries.length === 0) {
    return (
      <div className="history-empty">
        <p>No query history found.</p>
      </div>
    );
  }

  const totalPages: number = Math.ceil(history.total / history.page_size);

  return (
    <div className="query-history">
      <div className="history-header">
        <h2>Query History</h2>
        <div className="filter-group">
          <label htmlFor="status-filter">Filter by status:</label>
          <select
            id="status-filter"
            value={statusFilter || ''}
            onChange={(e): void =>
              handleStatusFilterChange(
                e.target.value ? (e.target.value as QueryStatus) : undefined
              )
            }
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      <div className="history-list">
        {history.queries.map((query: Query) => (
          <div
            key={query.id}
            className="history-item"
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
              <span className="history-query">{query.query_text}</span>
              <div className="history-item-actions">
                {renderStatusBadge(query.status)}
                <button
                  className="rerun-button"
                  onClick={(e): void => handleRerun(query, e)}
                  title="Re-run this query"
                  aria-label={`Re-run query: ${query.query_text}`}
                >
                  ▶ Re-run
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
        ))}
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
    </div>
  );
};
