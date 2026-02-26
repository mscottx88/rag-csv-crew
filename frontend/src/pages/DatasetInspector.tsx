/**
 * Dataset Inspector Page
 * Displays dataset contents in an interactive table with infinite scroll
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { DataTable } from '../components/Dataset/DataTable';
import * as datasetsService from '../services/datasets';
import type { Dataset } from '../types';
import './DatasetInspector.css';

export const DatasetInspector: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!id) return;

    const loadDataset = async (): Promise<void> => {
      setLoading(true);
      setError('');
      try {
        const result: Dataset = await datasetsService.get(id);
        setDataset(result);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Failed to load dataset');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadDataset();
  }, [id]);

  if (loading) {
    return (
      <div className="inspector-page">
        <div className="inspector-loading">Loading dataset...</div>
      </div>
    );
  }

  if (error || !dataset) {
    return (
      <div className="inspector-page">
        <div className="inspector-header">
          <Link to="/datasets" className="back-link">
            <span className="back-link-arrow">&larr;</span> Datasets
          </Link>
        </div>
        <div className="inspector-error">
          <h2>Dataset Not Found</h2>
          <p>{error || 'The requested dataset could not be loaded.'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="inspector-page">
      <div className="inspector-header">
        <Link to="/datasets" className="back-link">
          <span className="back-link-arrow">&larr;</span> Datasets
        </Link>
        <h1>{dataset.filename}</h1>
        <div className="inspector-meta">
          {dataset.row_count.toLocaleString()} rows
          <span className="meta-sep">|</span>
          {dataset.column_count} columns
        </div>
      </div>

      <DataTable datasetId={dataset.id} totalRowCount={dataset.row_count} />
    </div>
  );
};
