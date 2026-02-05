/**
 * Query Input Component
 * Natural language query input with example questions
 */

import React, { useState, useEffect, FormEvent, ChangeEvent } from 'react';
import * as queriesService from '../../services/queries';
import type { Query, QueryExample } from '../../types';
import './QueryInput.css';

interface QueryInputProps {
  onSubmit: (query: Query) => void;
  isProcessing?: boolean;
  onCancel?: () => void;
}

export const QueryInput: React.FC<QueryInputProps> = ({ onSubmit, isProcessing = false, onCancel }) => {
  const [queryText, setQueryText] = useState<string>('');
  const [examples, setExamples] = useState<QueryExample[]>([]);
  const [error, setError] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    const loadExamples = async (): Promise<void> => {
      try {
        const exampleList: QueryExample[] = await queriesService.getExamples();
        setExamples(exampleList);
      } catch (err) {
        console.error('Failed to load example queries:', err);
      }
    };

    void loadExamples();
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
      const query: Query = await queriesService.submit(queryText.trim());
      onSubmit(query);
      setQueryText(''); // Clear input after submission
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

  const handleCancelClick = (): void => {
    if (onCancel) {
      onCancel();
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
            placeholder="e.g., Show me the top 10 customers by revenue"
            disabled={submitting || isProcessing}
            rows={4}
            aria-label="Query text"
            aria-required="true"
          />
        </div>

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
