/**
 * Query Input Component
 * Natural language query input with example questions
 */

import React, { useState, useEffect, FormEvent, ChangeEvent, KeyboardEvent } from 'react';
import * as queriesService from '../../services/queries';
import * as datasetsService from '../../services/datasets';
import type { Query, QueryExample, Dataset } from '../../types';
import './QueryInput.css';

interface QueryInputProps {
  onSubmit: (query: Query) => void;
  isProcessing?: boolean;
  onCancel?: () => void;
  initialQueryText?: string;
  initialDatasetIds?: string[];
}

export const QueryInput: React.FC<QueryInputProps> = ({
  onSubmit,
  isProcessing = false,
  onCancel,
  initialQueryText,
  initialDatasetIds,
}) => {
  const [queryText, setQueryText] = useState<string>(initialQueryText || '');
  const [examples, setExamples] = useState<QueryExample[]>([]);
  const [error, setError] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>(initialDatasetIds || []);

  useEffect(() => {
    const loadData = async (): Promise<void> => {
      try {
        // Load example queries
        const exampleList: QueryExample[] = await queriesService.getExamples();
        setExamples(exampleList);

        // Load available datasets
        const datasetList = await datasetsService.list();
        setDatasets(datasetList.datasets);
      } catch (err) {
        console.error('Failed to load data:', err);
      }
    };

    void loadData();
  }, []);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');

    if (!queryText.trim()) {
      setError('Please enter a query');
      return;
    }

    setSubmitting(true);

    try {
      // Pass selected dataset IDs if any are selected (empty array means "all datasets")
      const datasetIdsToSubmit: string[] | undefined =
        selectedDatasetIds.length > 0 ? selectedDatasetIds : undefined;

      const query: Query = await queriesService.submit(queryText.trim(), datasetIdsToSubmit);
      onSubmit(query);
      setQueryText(''); // Clear input after submission
      // Keep dataset selection for next query (user preference)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to submit query. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleExampleClick = (exampleText: string): void => {
    setQueryText(exampleText);
    setError('');
  };

  const handleQueryChange = (e: ChangeEvent<HTMLTextAreaElement>): void => {
    setQueryText(e.target.value);
    setError('');
  };

  const handleQueryKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      if (!submitting && !isProcessing && queryText.trim()) {
        const form = e.currentTarget.closest('form');
        form?.requestSubmit();
      }
    }
  };

  const handleCancelClick = (): void => {
    if (onCancel) {
      onCancel();
    }
  };

  const handleDatasetToggle = (datasetId: string): void => {
    setSelectedDatasetIds((prev: string[]) => {
      if (prev.includes(datasetId)) {
        // Remove dataset from selection
        return prev.filter((id: string) => id !== datasetId);
      } else {
        // Add dataset to selection
        return [...prev, datasetId];
      }
    });
  };

  const handleSelectAllDatasets = (): void => {
    if (selectedDatasetIds.length === datasets.length) {
      // Deselect all
      setSelectedDatasetIds([]);
    } else {
      // Select all
      setSelectedDatasetIds(datasets.map((d: Dataset) => d.id));
    }
  };

  return (
    <div className="query-input">
      <h2>Ask a Question</h2>

      <form onSubmit={(e) => void handleSubmit(e)}>
        <div className="form-group">
          <label htmlFor="query-text">Natural Language Query</label>
          <textarea
            id="query-text"
            value={queryText}
            onChange={handleQueryChange}
            onKeyDown={handleQueryKeyDown}
            placeholder="e.g., Show me the top 10 customers by revenue"
            disabled={submitting || isProcessing}
            rows={4}
            aria-label="Query text"
            aria-required="true"
          />
        </div>

        {datasets.length > 0 && (
          <div className="form-group">
            <label htmlFor="dataset-selector">Target Datasets (optional)</label>
            <p className="help-text">
              Select specific datasets to query, or leave empty to search all datasets
            </p>
            <div className="dataset-selector">
              <button
                type="button"
                onClick={handleSelectAllDatasets}
                className="select-all-button"
                disabled={submitting || isProcessing}
              >
                {selectedDatasetIds.length === datasets.length ? 'Deselect All' : 'Select All'}
              </button>
              <div className="dataset-list">
                {datasets.map((dataset: Dataset) => (
                  <label key={dataset.id} className="dataset-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedDatasetIds.includes(dataset.id)}
                      onChange={(): void => handleDatasetToggle(dataset.id)}
                      disabled={submitting || isProcessing}
                      aria-label={`Select dataset ${dataset.filename}`}
                    />
                    <span className="dataset-name">{dataset.filename}</span>
                    <span className="dataset-meta">
                      ({dataset.row_count.toLocaleString()} rows)
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        <div className="button-group">
          <button
            type="submit"
            disabled={submitting || isProcessing || !queryText.trim()}
            className="submit-button"
          >
            {submitting ? 'Submitting...' : isProcessing ? 'Processing...' : 'Submit Query'}
          </button>

          {isProcessing && onCancel && (
            <button type="button" onClick={handleCancelClick} className="cancel-button">
              Cancel
            </button>
          )}
        </div>
      </form>

      {examples.length > 0 && (
        <div className="examples-section">
          <h3>Example Questions</h3>
          <div className="examples-list">
            {examples.map((example: QueryExample) => (
              <button
                key={example.id}
                onClick={(): void => handleExampleClick(example.text)}
                className="example-button"
                disabled={submitting || isProcessing}
                title={example.description}
              >
                {example.text}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
