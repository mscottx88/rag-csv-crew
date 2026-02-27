/**
 * DataTable Component
 * Paginated + bi-directional infinite-scroll data table with sortable columns.
 *
 * Scrolling down auto-loads the next page (rows appended).
 * Scrolling up near the top auto-loads the previous page (rows prepended,
 * scroll position preserved via scrollHeight compensation).
 * Pagination controls allow jumping to any specific page directly.
 * Column widths lock after the first render and persist across all navigation.
 */

import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react';
import { getRows } from '../../services/dataset-rows';
import type { DatasetRowsResponse } from '../../types';
import { NeonSelect } from '../NeonSelect/NeonSelect';
import { NeonScrollbar } from '../NeonScrollbar/NeonScrollbar';
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
  return (
    <svg className={cls} viewBox="0 0 10 11" aria-hidden="true">
      <text x="0" y="9" fontFamily="Courier New,monospace" fontSize="9" fontWeight="700" fill="currentColor">#</text>
    </svg>
  );
}

// ── Sort icon ──────────────────────────────────────────────────────────────

function SortIcon(
  { active, direction }: { active: boolean; direction: 'asc' | 'desc' },
): React.ReactElement {
  const points: string = direction === 'asc' ? '1,6 4,2 7,6' : '1,2 4,6 7,2';
  return (
    <svg
      className={`sort-icon sort-icon--${direction}`}
      viewBox="0 0 8 8"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
      style={{ visibility: active ? 'visible' : 'hidden' }}
    >
      <polyline points={points} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Cell formatter ─────────────────────────────────────────────────────────

function formatCell(value: string | number | boolean | null): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="cell-null">NULL</span>;
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

// ── Pagination helpers ─────────────────────────────────────────────────────

function getPageNumbers(page: number, total: number): (number | '...')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_: unknown, i: number): number => i + 1);
  }
  const pages: Set<number> = new Set([1, total]);
  for (let i: number = Math.max(1, page - 2); i <= Math.min(total, page + 2); i++) {
    pages.add(i);
  }
  const sorted: number[] = Array.from(pages).sort((a: number, b: number): number => a - b);
  const result: (number | '...')[] = [];
  let prev: number = 0;
  for (const p of sorted) {
    if (p - prev > 1) result.push('...');
    result.push(p);
    prev = p;
  }
  return result;
}

interface PaginationControlsProps {
  page: number;
  totalPages: number;
  totalRows: number;
  pageSize: number;
  loading: boolean;
  onPage: (p: number) => void;
}

function PaginationControls({
  page,
  totalPages,
  totalRows,
  pageSize,
  loading,
  onPage,
}: PaginationControlsProps): React.ReactElement {
  const pageNums: (number | '...')[] = getPageNumbers(page, totalPages);
  const startRow: number = totalRows > 0 ? (page - 1) * pageSize + 1 : 0;
  const endRow: number = Math.min(page * pageSize, totalRows);

  return (
    <div className="pagination-controls">
      <span className="pagination-info">
        {totalRows > 0
          ? `${startRow.toLocaleString()}–${endRow.toLocaleString()} of ${totalRows.toLocaleString()}`
          : 'No rows'}
      </span>
      <div className="pagination-pips">
        <button
          className="pagination-btn"
          onClick={(): void => { onPage(page - 1); }}
          disabled={page <= 1 || loading}
          aria-label="Previous page"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="8,2 4,6 8,10" />
          </svg>
        </button>

        {pageNums.map((p: number | '...', i: number): React.ReactElement => {
          if (p === '...') {
            return <span key={`e${i}`} className="pagination-ellipsis">···</span>;
          }
          const pageNum: number = p;
          return (
            <button
              key={pageNum}
              className={`pagination-pip${pageNum === page ? ' active' : ''}`}
              onClick={(): void => { onPage(pageNum); }}
              disabled={loading}
              aria-label={`Page ${pageNum}`}
              aria-current={pageNum === page ? 'page' : undefined}
            >
              {pageNum}
            </button>
          );
        })}

        <button
          className="pagination-btn"
          onClick={(): void => { onPage(page + 1); }}
          disabled={page >= totalPages || loading}
          aria-label="Next page"
        >
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4,2 8,6 4,10" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export const DataTable: React.FC<DataTableProps> = ({ datasetId, totalRowCount }) => {
  const [columns, setColumns] = useState<string[]>([]);
  const [columnTypes, setColumnTypes] = useState<Record<string, string>>({});
  const [columnOrder, setColumnOrder] = useState<number[]>([]);
  const [allRows, setAllRows] = useState<(string | number | boolean | null)[][]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingTop, setLoadingTop] = useState<boolean>(false);
  const [loadingBottom, setLoadingBottom] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  // Page range currently held in allRows
  const [firstLoadedPage, setFirstLoadedPage] = useState<number>(1);
  const [hasMoreTop, setHasMoreTop] = useState<boolean>(false);
  const [hasMoreBottom, setHasMoreBottom] = useState<boolean>(true);

  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Refs: stable values for use inside async callbacks / event listeners
  const sortColumnRef = useRef<string | null>(null);
  const sortDirectionRef = useRef<'asc' | 'desc'>('asc');
  const loadingRef = useRef<boolean>(false);        // doLoad guard
  const loadingTopRef = useRef<boolean>(false);     // loadPrevPage guard
  const loadingBottomRef = useRef<boolean>(false);  // loadNextPage guard
  const generationRef = useRef<number>(0);
  const columnsRef = useRef<string[]>([]);          // set-once guard per dataset
  const firstLoadedPageRef = useRef<number>(1);     // mirrors firstLoadedPage state
  const lastLoadedPageRef = useRef<number>(1);      // no state mirror needed (not rendered)
  // Captured scrollHeight before prepend — used to restore scroll position
  const pendingScrollAdjustRef = useRef<number | null>(null);

  const [colWidths, setColWidths] = useState<number[]>([]);
  const tableRef = useRef<HTMLTableElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef<{ colIdx: number; startX: number; startWidth: number } | null>(null);
  const bottomSentinelRef = useRef<HTMLDivElement>(null);

  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  const totalPages: number = totalRowCount > 0 ? Math.ceil(totalRowCount / pageSize) : 1;

  // ── Full page load — resets allRows to a single page ─────────────────────

  const doLoad = useCallback((page: number, size: number): void => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    const myGeneration: number = generationRef.current;
    const offset: number = (page - 1) * size;
    setLoading(true);

    void getRows(
      datasetId,
      offset,
      size,
      sortColumnRef.current ?? undefined,
      sortDirectionRef.current,
    ).then((result: DatasetRowsResponse): void => {
      if (myGeneration !== generationRef.current) return;
      if (columnsRef.current.length === 0) {
        columnsRef.current = result.columns;
        setColumns(result.columns);
        setColumnTypes(result.column_types);
        setColumnOrder(result.columns.map((_: string, i: number): number => i));
      }
      firstLoadedPageRef.current = page;
      lastLoadedPageRef.current = page;
      setFirstLoadedPage(page);
      setHasMoreTop(page > 1);
      setHasMoreBottom(result.has_more);
      setAllRows(result.rows);
      setCurrentPage(page);
    }).catch((err: unknown): void => {
      if (myGeneration !== generationRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to load data');
    }).finally((): void => {
      if (myGeneration === generationRef.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    });
  }, [datasetId]);

  // ── Append next page (scroll down) ───────────────────────────────────────

  const loadNextPage = useCallback((): void => {
    if (loadingBottomRef.current || loadingTopRef.current || loadingRef.current) return;
    const nextPage: number = lastLoadedPageRef.current + 1;
    if (nextPage > Math.ceil(totalRowCount / pageSize)) return;

    loadingBottomRef.current = true;
    setLoadingBottom(true);
    const myGeneration: number = generationRef.current;
    const offset: number = (nextPage - 1) * pageSize;

    void getRows(
      datasetId,
      offset,
      pageSize,
      sortColumnRef.current ?? undefined,
      sortDirectionRef.current,
    ).then((result: DatasetRowsResponse): void => {
      if (myGeneration !== generationRef.current) return;
      lastLoadedPageRef.current = nextPage;
      setHasMoreBottom(result.has_more);
      setAllRows((prev: (string | number | boolean | null)[][]) => [...prev, ...result.rows]);
    }).catch((): void => { /* discard — stale generation */ })
      .finally((): void => {
        if (myGeneration === generationRef.current) {
          loadingBottomRef.current = false;
          setLoadingBottom(false);
        }
      });
  }, [datasetId, pageSize, totalRowCount]);

  // ── Prepend previous page (scroll to top) ────────────────────────────────

  const loadPrevPage = useCallback((): void => {
    if (loadingTopRef.current || loadingBottomRef.current || loadingRef.current) return;
    const prevPage: number = firstLoadedPageRef.current - 1;
    if (prevPage < 1) return;

    loadingTopRef.current = true;
    setLoadingTop(true);
    const myGeneration: number = generationRef.current;
    const offset: number = (prevPage - 1) * pageSize;

    // Capture current scrollHeight so we can compensate after prepend
    if (scrollContainerRef.current) {
      pendingScrollAdjustRef.current = scrollContainerRef.current.scrollHeight;
    }

    void getRows(
      datasetId,
      offset,
      pageSize,
      sortColumnRef.current ?? undefined,
      sortDirectionRef.current,
    ).then((result: DatasetRowsResponse): void => {
      if (myGeneration !== generationRef.current) return;
      firstLoadedPageRef.current = prevPage;
      setFirstLoadedPage(prevPage);
      setHasMoreTop(prevPage > 1);
      setAllRows((prev: (string | number | boolean | null)[][]) => [...result.rows, ...prev]);
    }).catch((): void => { /* discard — stale generation */ })
      .finally((): void => {
        if (myGeneration === generationRef.current) {
          loadingTopRef.current = false;
          setLoadingTop(false);
        }
      });
  }, [datasetId, pageSize]);

  // ── Initial load and reset on datasetId change ───────────────────────────

  useEffect((): void => {
    generationRef.current += 1;
    loadingRef.current = false;
    loadingTopRef.current = false;
    loadingBottomRef.current = false;
    sortColumnRef.current = null;
    sortDirectionRef.current = 'asc';
    columnsRef.current = [];
    setSortColumn(null);
    setSortDirection('asc');
    setColWidths([]);
    setColumns([]);
    setColumnTypes({});
    setColumnOrder([]);
    setAllRows([]);
    setCurrentPage(1);
    setFirstLoadedPage(1);
    setHasMoreTop(false);
    setHasMoreBottom(true);
    setLoading(true);
    doLoad(1, pageSize);
    // pageSize intentionally excluded — handled by handlePageSizeChange
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId, doLoad]);

  // ── Lock column widths after first data render ────────────────────────────

  useLayoutEffect(() => {
    if (colWidths.length > 0 || allRows.length === 0 || !tableRef.current) return;
    const ths = Array.from(
      tableRef.current.querySelectorAll<HTMLTableCellElement>('thead th'),
    );
    const widths: number[] = ths.map((th) => th.getBoundingClientRect().width);
    if (widths.length > 0 && widths.every((w) => w > 0)) {
      setColWidths(widths);
    }
  }, [allRows.length, colWidths.length]);

  // ── Restore scroll position after prepending rows ─────────────────────────
  // Prepending rows grows the DOM upward. Without compensation the viewport
  // appears to jump to the newly added content. We shift scrollTop by the
  // amount scrollHeight grew so the previously visible rows stay in view.

  useLayoutEffect(() => {
    if (pendingScrollAdjustRef.current !== null && scrollContainerRef.current) {
      const prevScrollHeight: number = pendingScrollAdjustRef.current;
      const delta: number = scrollContainerRef.current.scrollHeight - prevScrollHeight;
      scrollContainerRef.current.scrollTop += delta;
      pendingScrollAdjustRef.current = null;
    }
  }, [allRows.length]);

  // ── Bottom sentinel — loads next page as user scrolls down ───────────────

  useEffect(() => {
    const sentinel: HTMLDivElement | null = bottomSentinelRef.current;
    if (!sentinel || !hasMoreBottom || loading) return;

    const observer: IntersectionObserver = new IntersectionObserver(
      (entries: IntersectionObserverEntry[]) => {
        if (entries[0]?.isIntersecting && !loadingBottomRef.current && !loadingTopRef.current) {
          void loadNextPage();
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(sentinel);
    return (): void => { observer.disconnect(); };
  }, [hasMoreBottom, loading, loadNextPage]);

  // ── After doLoad: proactively trigger prev-page load if already at top ──────
  // When the user jumps to page N > 1 via pagination, scrollTop is reset to 0
  // and hasMoreTop becomes true, but no scroll event fires automatically.
  // This effect runs once after each doLoad completes and checks the condition.

  useEffect(() => {
    if (loading) return;
    const container: HTMLDivElement | null = scrollContainerRef.current;
    if (
      container &&
      hasMoreTop &&
      !loadingTopRef.current &&
      !loadingBottomRef.current &&
      container.scrollTop < 120
    ) {
      void loadPrevPage();
    }
    // Only run when loading transitions to false (i.e. doLoad just completed)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // ── Scroll listener — loads prev page and tracks current page ─────────────

  useEffect(() => {
    const container: HTMLDivElement | null = scrollContainerRef.current;
    if (!container || loading) return;

    const onScroll = (): void => {
      // Near-top threshold: trigger previous-page load
      if (
        container.scrollTop < 120 &&
        hasMoreTop &&
        !loadingTopRef.current &&
        !loadingBottomRef.current &&
        !loadingRef.current
      ) {
        void loadPrevPage();
      }

      // Update the current-page indicator based on scroll position within loaded range
      const loadedPageCount: number = lastLoadedPageRef.current - firstLoadedPageRef.current + 1;
      if (loadedPageCount > 0) {
        const maxScroll: number = container.scrollHeight - container.clientHeight;
        if (maxScroll > 0) {
          const fraction: number = container.scrollTop / maxScroll;
          const totalLoadedRows: number = loadedPageCount * pageSize;
          const visibleRow: number = Math.floor(fraction * totalLoadedRows);
          const estimatedPage: number =
            firstLoadedPageRef.current + Math.floor(visibleRow / pageSize);
          setCurrentPage(
            Math.max(firstLoadedPageRef.current,
              Math.min(estimatedPage, lastLoadedPageRef.current)),
          );
        }
      }
    };

    container.addEventListener('scroll', onScroll, { passive: true });
    return (): void => { container.removeEventListener('scroll', onScroll); };
  }, [loading, hasMoreTop, loadPrevPage, pageSize]);

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
    generationRef.current += 1;
    loadingRef.current = false;
    loadingTopRef.current = false;
    loadingBottomRef.current = false;
    doLoad(1, pageSize);
  };

  // ── Explicit page navigation ──────────────────────────────────────────────

  const handlePageChange = (page: number): void => {
    if (page < 1 || page > totalPages || loadingRef.current) return;
    generationRef.current += 1;
    loadingRef.current = false;
    loadingTopRef.current = false;
    loadingBottomRef.current = false;
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
    doLoad(page, pageSize);
  };

  // ── Manual column resizing ────────────────────────────────────────────────

  const handleResizeMouseDown = (e: React.MouseEvent, colIdx: number): void => {
    e.preventDefault();
    e.stopPropagation();
    resizingRef.current = {
      colIdx,
      startX: e.clientX,
      startWidth: colWidths[colIdx] ?? 0,
    };
  };

  useEffect(() => {
    const onMouseMove = (e: MouseEvent): void => {
      const resizing = resizingRef.current;
      if (!resizing) return;
      const delta: number = e.clientX - resizing.startX;
      const newWidth: number = Math.max(40, resizing.startWidth + delta);
      setColWidths((prev: number[]) => {
        const next: number[] = [...prev];
        next[resizing.colIdx] = newWidth;
        return next;
      });
    };
    const onMouseUp = (): void => { resizingRef.current = null; };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return (): void => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

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
    setColWidths((prev: number[]) => {
      if (prev.length === 0) return prev;
      const next: number[] = [...prev];
      const removed: number = next.splice(sourceIndex + 1, 1)[0] as number;
      next.splice(targetIndex + 1, 0, removed);
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
      {/* Controls bar */}
      <div className="table-controls">
        <label>
          Page size:
          <NeonSelect
            value={String(pageSize)}
            onChange={(val: string): void => {
              const size: number = Number(val);
              generationRef.current += 1;
              loadingRef.current = false;
              loadingTopRef.current = false;
              loadingBottomRef.current = false;
              setPageSize(size);
              doLoad(1, size);
            }}
            options={[
              { value: '25', label: '25' },
              { value: '50', label: '50' },
              { value: '100', label: '100' },
              { value: '200', label: '200' },
            ]}
            color="orange"
          />
        </label>
        <span className="row-count-display">
          {totalRowCount.toLocaleString()} rows
        </span>
      </div>

      {/* Scrollable table area */}
      <NeonScrollbar className="table-scroll-container" scrollRef={scrollContainerRef} color="orange">
        {/* Top loading indicator when prepending a previous page */}
        {loadingTop && (
          <div className="load-top-sentinel">
            <div className="loading-indicator">Loading previous page…</div>
          </div>
        )}

        <table
          ref={tableRef}
          className={`data-table${colWidths.length > 0 ? ' fixed-layout' : ''}`}
          style={colWidths.length > 0
            ? { width: colWidths.reduce((s: number, w: number) => s + w, 0) }
            : undefined}
        >
          {colWidths.length > 0 && (
            <colgroup>
              {colWidths.map((w: number, i: number) => (
                <col key={i} style={{ width: w }} />
              ))}
            </colgroup>
          )}
          <thead>
            <tr>
              <th className="row-num-header">
                #
                {colWidths.length > 0 && (
                  <div
                    className="col-resize-handle"
                    onMouseDown={(e: React.MouseEvent): void => handleResizeMouseDown(e, 0)}
                    onClick={(e: React.MouseEvent): void => { e.stopPropagation(); }}
                  />
                )}
              </th>
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
                    {colWidths.length > 0 && (
                      <div
                        className="col-resize-handle"
                        onMouseDown={(e: React.MouseEvent): void => handleResizeMouseDown(e, visIdx + 1)}
                        onClick={(e: React.MouseEvent): void => { e.stopPropagation(); }}
                      />
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {allRows.map((row: (string | number | boolean | null)[], rowIdx: number) => (
              <tr key={rowIdx}>
                <td className="row-num">
                  {((firstLoadedPage - 1) * pageSize + rowIdx + 1).toLocaleString()}
                </td>
                {columnOrder.map((colIdx: number) => (
                  <td key={colIdx}>{formatCell(row[colIdx] ?? null)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {/* Bottom sentinel — triggers loading next page */}
        {hasMoreBottom && (
          <div ref={bottomSentinelRef} className="load-more-sentinel">
            {loadingBottom && (
              <div className="loading-indicator">Loading more rows…</div>
            )}
          </div>
        )}
        {!hasMoreBottom && allRows.length > 0 && (
          <div className="load-more-sentinel">
            All {totalRowCount.toLocaleString()} rows loaded
          </div>
        )}
      </NeonScrollbar>

      {/* Pagination controls */}
      <PaginationControls
        page={currentPage}
        totalPages={totalPages}
        totalRows={totalRowCount}
        pageSize={pageSize}
        loading={loading}
        onPage={handlePageChange}
      />
    </div>
  );
};
