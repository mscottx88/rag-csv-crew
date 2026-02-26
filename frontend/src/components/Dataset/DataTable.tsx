/**
 * DataTable Component
 * Infinite-scroll data table with drag-and-drop column reordering
 * for the Dataset Inspector.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getRows } from '../../services/dataset-rows';
import type { DatasetRowsResponse } from '../../types';
import './DataTable.css';

interface DataTableProps {
  datasetId: string;
  totalRowCount: number;
}

/** Format a cell value for display. */
function formatCell(value: string | number | boolean | null): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="cell-null">NULL</span>;
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  return String(value);
}

export const DataTable: React.FC<DataTableProps> = ({ datasetId, totalRowCount }) => {
  const [columns, setColumns] = useState<string[]>([]);
  const [columnOrder, setColumnOrder] = useState<number[]>([]);
  const [allRows, setAllRows] = useState<(string | number | boolean | null)[][]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [batchSize, setBatchSize] = useState<number>(50);

  // Drag-and-drop state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  // Refs
  const sentinelRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef<boolean>(false);

  // ── Data fetching ──
  const loadNextBatch = useCallback(async (): Promise<void> => {
    if (loadingRef.current || !hasMore) return;
    loadingRef.current = true;
    setLoadingMore(true);

    try {
      const result: DatasetRowsResponse = await getRows(datasetId, allRows.length, batchSize);

      if (allRows.length === 0) {
        setColumns(result.columns);
        setColumnOrder(result.columns.map((_: string, i: number) => i));
      }

      setAllRows((prev: (string | number | boolean | null)[][]) => [...prev, ...result.rows]);
      setHasMore(result.has_more);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load data');
      }
    } finally {
      loadingRef.current = false;
      setLoadingMore(false);
      setLoading(false);
    }
  }, [datasetId, allRows.length, batchSize, hasMore]);

  // Initial load
  useEffect(() => {
    void loadNextBatch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  // ── Infinite scroll via IntersectionObserver ──
  useEffect(() => {
    const sentinel: HTMLDivElement | null = sentinelRef.current;
    if (!sentinel || !hasMore || loading) return;

    const observer: IntersectionObserver = new IntersectionObserver(
      (entries: IntersectionObserverEntry[]) => {
        if (entries[0]?.isIntersecting && !loadingRef.current) {
          void loadNextBatch();
        }
      },
      { rootMargin: '200px' },
    );

    observer.observe(sentinel);
    return (): void => { observer.disconnect(); };
  }, [hasMore, loading, loadNextBatch]);

  // ── Column drag-and-drop ──
  const handleDragStart = (e: React.DragEvent, index: number): void => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (e: React.DragEvent, index: number): void => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDropIndex(index);
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number): void => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null);
      setDropIndex(null);
      return;
    }

    const sourceIndex: number = dragIndex;
    setColumnOrder((prev: number[]) => {
      const next: number[] = [...prev];
      const removed: number = next.splice(sourceIndex, 1)[0] as number;
      next.splice(targetIndex, 0, removed);
      return next;
    });
    setDragIndex(null);
    setDropIndex(null);
  };

  const handleDragEnd = (): void => {
    setDragIndex(null);
    setDropIndex(null);
  };

  // ── Render states ──
  if (loading) {
    return <div className="table-loading">Loading data...</div>;
  }

  if (error) {
    return <div className="table-error">{error}</div>;
  }

  if (columns.length === 0) {
    return <div className="table-empty">No columns found in this dataset.</div>;
  }

  return (
    <div className="data-table-root">
      {/* Controls */}
      <div className="table-controls">
        <label>
          Rows per batch:
          <select
            value={batchSize}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>): void => {
              setBatchSize(Number(e.target.value));
            }}
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
        </label>
        <span className="row-count-display">
          Showing {allRows.length.toLocaleString()} of {totalRowCount.toLocaleString()} rows
        </span>
      </div>

      {/* Scrollable table area — both axes scroll inside this container */}
      <div className="table-scroll-container">
        <table className="data-table">
          <thead>
            <tr>
              <th className="row-num-header">#</th>
              {columnOrder.map((colIdx: number, visIdx: number) => (
                <th
                  key={colIdx}
                  draggable
                  onDragStart={(e: React.DragEvent): void => handleDragStart(e, visIdx)}
                  onDragOver={(e: React.DragEvent): void => handleDragOver(e, visIdx)}
                  onDrop={(e: React.DragEvent): void => handleDrop(e, visIdx)}
                  onDragEnd={handleDragEnd}
                  className={`${dragIndex === visIdx ? 'dragging' : ''} ${dropIndex === visIdx && dragIndex !== visIdx ? 'drop-target' : ''}`}
                >
                  <span className="drag-handle">&#x2261;</span>
                  {columns[colIdx]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {allRows.map((row: (string | number | boolean | null)[], rowIdx: number) => (
              <tr key={rowIdx}>
                <td className="row-num">{rowIdx + 1}</td>
                {columnOrder.map((colIdx: number) => (
                  <td key={colIdx}>{formatCell(row[colIdx] ?? null)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {/* Sentinel + status inside scroll container so they scroll with data */}
        {hasMore && (
          <div ref={sentinelRef} className="load-more-sentinel">
            {loadingMore && (
              <div className="loading-indicator">Loading more rows...</div>
            )}
          </div>
        )}

        {!hasMore && allRows.length > 0 && (
          <div className="load-more-sentinel">
            All {totalRowCount.toLocaleString()} rows loaded
          </div>
        )}
      </div>
    </div>
  );
};
