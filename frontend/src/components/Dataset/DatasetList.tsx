/**
 * Dataset List Component
 * Expandable row list of datasets with neon wireframe twisties,
 * inline DataTable preview, and delete functionality.
 */

import React, { useState, useEffect } from 'react';
import * as datasetsService from '../../services/datasets';
import { DataTable } from './DataTable';
import type { Dataset, DatasetList as DatasetListType } from '../../types';
import './DatasetList.css';

interface DatasetListProps {
  refresh?: number; // Increment to trigger refresh
  onEmptyChange?: (isEmpty: boolean) => void;
}

export const DatasetList: React.FC<DatasetListProps> = ({ refresh = 0, onEmptyChange }) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const loadDatasets = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const data: DatasetListType = await datasetsService.list();
        setDatasets(data.datasets);
        onEmptyChange?.(data.datasets.length === 0);
      } catch (err) {
        setError('Failed to load datasets');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    void loadDatasets();
  }, [refresh]);

  const handleToggle = (id: string): void => {
    setExpandedId((prev: string | null) => (prev === id ? null : id));
  };

  const handleDeleteClick = (id: string, event: React.MouseEvent): void => {
    event.stopPropagation();
    setDeleteConfirm(id);
  };

  const handleDeleteCancel = (): void => {
    setDeleteConfirm(null);
  };

  const handleDeleteConfirm = async (id: string): Promise<void> => {
    setDeleting(id);
    setError('');

    try {
      await datasetsService.deleteDataset(id);
      const remaining: Dataset[] = datasets.filter((d: Dataset): boolean => d.id !== id);
      setDatasets(remaining);
      onEmptyChange?.(remaining.length === 0);
      setDeleteConfirm(null);
      if (expandedId === id) {
        setExpandedId(null);
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to delete dataset');
      }
    } finally {
      setDeleting(null);
    }
  };

  const formatDate = (dateStr: string): string => {
    const date: Date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  if (loading) {
    return <div className="dataset-list-loading">Loading datasets...</div>;
  }

  if (error) {
    return (
      <div className="dataset-list-error" role="alert">
        {error}
      </div>
    );
  }

  if (datasets.length === 0) {
    return (
      <div className="dataset-list-empty">
        <p>No datasets uploaded yet.</p>
        <p>Upload a CSV file to get started.</p>
      </div>
    );
  }

  return (
    <div className="dataset-list">
      <div className="dataset-list-header">
        <h2>Datasets</h2>
        <span className="dataset-count">{datasets.length} dataset{datasets.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="dataset-items">
        {datasets.map((dataset: Dataset) => {
          const isExpanded: boolean = expandedId === dataset.id;

          return (
            <div
              key={dataset.id}
              className={`dataset-item ${isExpanded ? 'dataset-item-expanded' : ''}`}
            >
              <div
                className="dataset-item-row"
                onClick={(): void => handleToggle(dataset.id)}
                role="button"
                tabIndex={0}
                onKeyPress={(e): void => {
                  if (e.key === 'Enter') {
                    handleToggle(dataset.id);
                  }
                }}
              >
                <div className="dataset-item-header">
                  <span className={`dataset-expand-indicator ${isExpanded ? 'expanded' : ''}`}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 1.5 L9.5 6 L3 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                    </svg>
                  </span>
                  <span className="dataset-filename">{dataset.filename}</span>
                  <div className="dataset-item-actions">
                    <span className="dataset-meta-badge">{dataset.row_count.toLocaleString()} rows</span>
                    <span className="dataset-meta-badge">{dataset.column_count} cols</span>
                    <button
                      onClick={(e): void => handleDeleteClick(dataset.id, e)}
                      disabled={deleting === dataset.id}
                      className="delete-button"
                      aria-label={`Delete ${dataset.filename}`}
                    >
                      {deleting === dataset.id ? 'Deleting...' : 'Delete'}
                    </button>
                  </div>
                </div>
                <div className="dataset-item-meta">
                  <span className="dataset-date">{formatDate(dataset.uploaded_at)}</span>
                  <span className="dataset-id">{dataset.id.slice(0, 8)}</span>
                </div>
              </div>

              {isExpanded && (
                <div className="dataset-item-detail">
                  <DataTable datasetId={dataset.id} totalRowCount={dataset.row_count} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {deleteConfirm && (
        <div className="confirm-dialog-overlay">
          <div className="confirm-dialog" role="dialog" aria-labelledby="dialog-title">
            <h3 id="dialog-title">Confirm Delete</h3>
            <p>
              Are you sure you want to delete{' '}
              <strong>
                {datasets.find((d: Dataset): boolean => d.id === deleteConfirm)?.filename}
              </strong>
              ?
            </p>
            <p className="confirm-warning">This action cannot be undone.</p>
            <div className="dialog-buttons">
              <button onClick={handleDeleteCancel} className="dialog-cancel-button">
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteConfirm(deleteConfirm)}
                className="confirm-button"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
