/**
 * Dataset List Component
 * Table view of datasets with delete functionality
 */

import React, { useState, useEffect } from 'react';
import * as datasetsService from '../../services/datasets';
import type { Dataset, DatasetList as DatasetListType } from '../../types';
import './DatasetList.css';

interface DatasetListProps {
  refresh?: number; // Increment to trigger refresh
}

export const DatasetList: React.FC<DatasetListProps> = ({ refresh = 0 }) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    const loadDatasets = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const data: DatasetListType = await datasetsService.list();
        setDatasets(data.datasets);
      } catch (err) {
        setError('Failed to load datasets');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    void loadDatasets();
  }, [refresh]);

  const handleDeleteClick = (id: string): void => {
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
      setDatasets((prev: Dataset[]): Dataset[] => prev.filter((d: Dataset): boolean => d.id !== id));
      setDeleteConfirm(null);
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
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Rows</th>
            <th>Columns</th>
            <th>Uploaded</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset: Dataset) => (
            <tr key={dataset.id}>
              <td>{dataset.filename}</td>
              <td>{dataset.row_count.toLocaleString()}</td>
              <td>{dataset.column_count}</td>
              <td>{formatDate(dataset.uploaded_at)}</td>
              <td>
                <button
                  onClick={(): void => handleDeleteClick(dataset.id)}
                  disabled={deleting === dataset.id}
                  className="delete-button"
                  aria-label={`Delete ${dataset.filename}`}
                >
                  {deleting === dataset.id ? 'Deleting...' : 'Delete'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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
              <button onClick={handleDeleteCancel} className="cancel-button">
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
