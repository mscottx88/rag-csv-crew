/**
 * DataTable Component
 * Infinite-scroll data table with sortable columns and data-type icons.
 *
 * Column headers show: drag-handle | type-icon | name | sort-icon
 * Clicking a column header cycles sort: none → asc → desc → none
 * Sort is applied server-side; state resets to offset 0 on each change.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getRows } from '../../services/dataset-rows';
import type { DatasetRowsResponse } from '../../types';
import './DataTable.css';

interface DataTableProps {
  datasetId: string;
  totalRowCount: number;
}

// ── Type icons ─────────────────────────────────────────────────────────────

function TypeIcon({ type }: { type: string }): React.ReactElement {
  const t: string = type.toLowerCase();
  const cls: string = 'col-type-icon';

  if (t === 'integer' || t === 'bigint' || t === 'smallint' ||
      t === 'int' || t === 'int2' || t === 'int4' || t === 'int8') {
    return (
      <svg className={cls} viewBox="0 0 19 11" aria-hidden="true">
        <text x="0"   y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">1</text>
        <text x="6.5" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">2</text>
        <text x="13"  y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">3</text>
      </svg>
    );
  }

  if (t === 'numeric' || t === 'decimal' || t === 'real' ||
      t.startsWith('float') || t.includes('double')) {
    return (
      <svg className={cls} viewBox="0 0 26 11" aria-hidden="true">
        <text x="0" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">1.23</text>
      </svg>
    );
  }

  if (t === 'text' || t.startsWith('varchar') || t.startsWith('char') ||
      t === 'bpchar' || t === 'character varying') {
    return (
      <svg className={cls} viewBox="0 0 19 11" aria-hidden="true">
        <text x="0"   y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">A</text>
        <text x="6.5" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">B</text>
        <text x="13"  y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">C</text>
      </svg>
    );
  }

  if (t === 'boolean' || t === 'bool') {
    return (
      <svg className={cls} viewBox="0 0 18 11" aria-hidden="true">
        <text x="0" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">T/F</text>
      </svg>
    );
  }

  if (t === 'date') {
    return (
      <svg className={cls} viewBox="0 0 13 12" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden="true">
        <rect x="0.5" y="1.5" width="12" height="10" rx="1" />
        <line x1="0.5"  y1="4.5" x2="12.5" y2="4.5" />
        <line x1="3.5"  y1="0.5" x2="3.5"  y2="3" />
        <line x1="9.5"  y1="0.5" x2="9.5"  y2="3" />
        <rect x="2"    y="6.5" width="1.5" height="1.5" fill="currentColor" stroke="none" />
        <rect x="5.75" y="6.5" width="1.5" height="1.5" fill="currentColor" stroke="none" />
        <rect x="9.5"  y="6.5" width="1.5" height="1.5" fill="currentColor" stroke="none" />
        <rect x="2"    y="9"   width="1.5" height="1.5" fill="currentColor" stroke="none" />
        <rect x="5.75" y="9"   width="1.5" height="1.5" fill="currentColor" stroke="none" />
      </svg>
    );
  }

  if (t.startsWith('timestamp') || t === 'timestamptz') {
    return (
      <svg className={cls} viewBox="0 0 13 12" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden="true">
        <rect x="0.5" y="1.5" width="12" height="10" rx="1" />
        <line x1="0.5" y1="4.5" x2="12.5" y2="4.5" />
        <line x1="3.5" y1="0.5" x2="3.5"  y2="3" />
        <line x1="9.5" y1="0.5" x2="9.5"  y2="3" />
        <circle cx="6.5" cy="8.5" r="2.2" />
        <line x1="6.5" y1="8.5" x2="6.5" y2="7" />
        <line x1="6.5" y1="8.5" x2="7.7" y2="8.5" />
      </svg>
    );
  }

  // Default: uuid, unknown, etc.
  return (
    <svg className={cls} viewBox="0 0 10 11" aria-hidden="true">
      <text x="0" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">#</text>
    </svg>
  );
}

// ── Sort icon ──────────────────────────────────────────────────────────────

function SortIcon(
  { active, direction }: { active: boolean; direction: 'asc' | 'desc' },
): React.ReactElement | null {
  if (!active) return null;
  if (direction === 'asc') {
    return (
      <svg className="sort-icon sort-icon--asc" viewBox="0 0 8 8" fill="none"
           stroke="currentColor" aria-label="sorted ascending" aria-hidden="true">
        <polyline points="1,6 4,2 7,6" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className="sort-icon sort-icon--desc" viewBox="0 0 8 8" fill="none"
         stroke="currentColor" aria-label="sorted descending" aria-hidden="true">
      <polyline points="1,2 4,6 7,2" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Cell formatter ─────────────────────────────────────────────────────────

function formatCell(value: string | number | boolean | null): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="cell-null">NULL</span>;
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  return String(value);
}

// ── Component ──────────────────────────────────────────────────────────────

export const DataTable: React.FC<DataTableProps> = ({ datasetId, totalRowCount }) => {
  const [columns, setColumns] = useState<string[]>([]);
  const [columnTypes, setColumnTypes] = useState<Record<string, string>>({});
  const [columnOrder, setColumnOrder] = useState<number[]>([]);
  const [allRows, setAllRows] = useState<(string | number | boolean | null)[][]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [batchSize, setBatchSize] = useState<number>(50);

  // Sort state for rendering
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Refs: hold current values accessible inside callbacks without stale closures
  const sortColumnRef = useRef<string | null>(null);
  const sortDirectionRef = useRef<'asc' | 'desc'>('asc');
  const currentOffsetRef = useRef<number>(0);
  const hasMoreRef = useRef<boolean>(true);
  const loadingRef = useRef<boolean>(false);
  // Generation counter — incremented on sort/dataset change to discard in-flight stale responses
  const generationRef = useRef<number>(0);

  // Drag-and-drop state
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  const sentinelRef = useRef<HTMLDivElement>(null);

  // ── Data fetching ─────────────────────────────────────────────────────────

  const loadNextBatch = useCallback(async (): Promise<void> => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    setLoadingMore(true);

    const myGeneration: number = generationRef.current;
    const offset: number = currentOffsetRef.current;

    try {
      const result: DatasetRowsResponse = await getRows(
        datasetId,
        offset,
        batchSize,
        sortColumnRef.current ?? undefined,
        sortDirectionRef.current,
      );

      // Discard stale response if sort changed while this request was in flight
      if (myGeneration !== generationRef.current) return;

      if (offset === 0) {
        setColumns(result.columns);
        setColumnOrder(result.columns.map((_: string, i: number) => i));
        setColumnTypes(result.column_types);
        setAllRows(result.rows);
      } else {
        setAllRows((prev: (string | number | boolean | null)[][]) => [...prev, ...result.rows]);
      }

      currentOffsetRef.current += result.rows.length;
      hasMoreRef.current = result.has_more;
      setHasMore(result.has_more);
    } catch (err) {
      if (myGeneration !== generationRef.current) return;
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load data');
      }
    } finally {
      if (myGeneration === generationRef.current) {
        loadingRef.current = false;
        setLoadingMore(false);
        setLoading(false);
      }
    }
  }, [datasetId, batchSize]);

  // Initial load and reset on datasetId change
  useEffect(() => {
    generationRef.current += 1;
    currentOffsetRef.current = 0;
    hasMoreRef.current = true;
    loadingRef.current = false;
    sortColumnRef.current = null;
    sortDirectionRef.current = 'asc';
    setSortColumn(null);
    setSortDirection('asc');
    setAllRows([]);
    setHasMore(true);
    setLoading(true);
    void loadNextBatch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]);

  // Infinite scroll via IntersectionObserver
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

  // ── Sort toggle ───────────────────────────────────────────────────────────

  const handleSortToggle = (colName: string): void => {
    if (sortColumnRef.current === colName) {
      if (sortDirectionRef.current === 'asc') {
        sortDirectionRef.current = 'desc';
        setSortDirection('desc');
      } else {
        sortColumnRef.current = null;
        sortDirectionRef.current = 'asc';
        setSortColumn(null);
        setSortDirection('asc');
      }
    } else {
      sortColumnRef.current = colName;
      sortDirectionRef.current = 'asc';
      setSortColumn(colName);
      setSortDirection('asc');
    }

    // Invalidate in-flight request, reset pagination, reload from scratch
    generationRef.current += 1;
    currentOffsetRef.current = 0;
    hasMoreRef.current = true;
    loadingRef.current = false;
    setAllRows([]);
    setHasMore(true);
    setLoading(true);
    void loadNextBatch();
  };

  // ── Column drag-and-drop ──────────────────────────────────────────────────

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

  // ── Render states ─────────────────────────────────────────────────────────

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
              {columnOrder.map((colIdx: number, visIdx: number) => {
                const colName: string = columns[colIdx] ?? '';
                const colType: string = columnTypes[colName] ?? 'text';
                const isActive: boolean = sortColumn === colName;
                return (
                  <th
                    key={colIdx}
                    draggable
                    onDragStart={(e: React.DragEvent): void => handleDragStart(e, visIdx)}
                    onDragOver={(e: React.DragEvent): void => handleDragOver(e, visIdx)}
                    onDrop={(e: React.DragEvent): void => handleDrop(e, visIdx)}
                    onDragEnd={handleDragEnd}
                    onClick={(): void => handleSortToggle(colName)}
                    className={[
                      dragIndex === visIdx ? 'dragging' : '',
                      dropIndex === visIdx && dragIndex !== visIdx ? 'drop-target' : '',
                      isActive ? 'sorted' : '',
                    ].filter(Boolean).join(' ')}
                  >
                    <span className="th-inner">
                      <span className="drag-handle">&#x2261;</span>
                      <TypeIcon type={colType} />
                      <span className="col-name">{colName}</span>
                      <SortIcon active={isActive} direction={sortDirection} />
                    </span>
                  </th>
                );
              })}
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
