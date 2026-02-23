/**
 * Component tests for ResultDisplay - Tests T139-TEST
 * Validates HTML rendering and cancellation
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ResultDisplay } from '../../../src/components/Query/ResultDisplay';
import type { Query } from '../../../src/types';

describe('ResultDisplay Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render HTML content safely', () => {
    const query: Query = {
      id: 'query-1',
      query_text: 'Show me data',
      status: 'completed',
      submitted_at: '2024-01-01T00:00:00Z',
      completed_at: '2024-01-01T00:00:05Z',
      execution_time_ms: 5000,
      result_count: 10,
      response: {
        query_id: 'query-1',
        id: 'response-1',
        html_content: '<h1>Test Results</h1><p>Sample data</p>',
        plain_text: 'Test Results\nSample data',
        confidence_score: 0.95,
        generated_at: '2024-01-01T00:00:05Z',
      },
    };

    render(<ResultDisplay query={query} />);

    const heading: HTMLElement = screen.getByRole('heading', { name: /test results/i });
    expect(heading).toBeInTheDocument();
    expect(screen.getByText(/sample data/i)).toBeInTheDocument();
  });

  it('should show query metadata (execution time, row count)', () => {
    const query: Query = {
      id: 'query-2',
      query_text: 'Show me data',
      status: 'completed',
      submitted_at: '2024-01-01T00:00:00Z',
      completed_at: '2024-01-01T00:00:05Z',
      execution_time_ms: 5000,
      result_count: 42,
      response: {
        query_id: 'query-2',
        id: 'response-2',
        html_content: '<p>Results</p>',
        plain_text: 'Results',
        confidence_score: 0.90,
        generated_at: '2024-01-01T00:00:05Z',
      },
    };

    render(<ResultDisplay query={query} />);

    expect(screen.getByText(/5000ms/i)).toBeInTheDocument();
    expect(screen.getByText(/42/i)).toBeInTheDocument();
  });

  it('should show cancel button for running queries', () => {
    const mockOnCancel: () => void = vi.fn();
    const query: Query = {
      id: 'query-3',
      query_text: 'Show me data',
      status: 'processing',
      submitted_at: '2024-01-01T00:00:00Z',
    };

    render(<ResultDisplay query={query} onCancel={mockOnCancel} />);

    const cancelButton: HTMLElement = screen.getByRole('button', { name: /cancel query/i });
    expect(cancelButton).toBeInTheDocument();
  });

  it('should handle empty results', () => {
    const query: Query = {
      id: 'query-4',
      query_text: 'Show me data',
      status: 'completed',
      submitted_at: '2024-01-01T00:00:00Z',
      completed_at: '2024-01-01T00:00:05Z',
    };

    render(<ResultDisplay query={query} />);

    expect(screen.getByText(/no results available/i)).toBeInTheDocument();
  });

  it('should show error state', () => {
    const query: Query = {
      id: 'query-5',
      query_text: 'Show me data',
      status: 'failed',
      submitted_at: '2024-01-01T00:00:00Z',
      error_message: 'Database connection failed',
    };

    render(<ResultDisplay query={query} />);

    expect(screen.getByText(/query failed/i)).toBeInTheDocument();
    expect(screen.getByText(/database connection failed/i)).toBeInTheDocument();
  });

  it('should show confidence score for clarifications', () => {
    const query: Query = {
      id: 'query-6',
      query_text: 'Show me data',
      status: 'completed',
      submitted_at: '2024-01-01T00:00:00Z',
      completed_at: '2024-01-01T00:00:05Z',
      response: {
        query_id: 'query-6',
        id: 'response-6',
        html_content: '<p>Clarification needed</p>',
        plain_text: 'Clarification needed',
        confidence_score: 0.45,
        generated_at: '2024-01-01T00:00:05Z',
      },
    };

    render(<ResultDisplay query={query} />);

    // Confidence score should be displayed as percentage
    expect(screen.getByText(/45\.0%/i)).toBeInTheDocument();
  });

  it('should call onCancel when cancel button is clicked', async () => {
    const user: ReturnType<typeof userEvent.setup> = userEvent.setup();
    const mockOnCancel: () => void = vi.fn();
    const query: Query = {
      id: 'query-7',
      query_text: 'Show me data',
      status: 'processing',
      submitted_at: '2024-01-01T00:00:00Z',
    };

    render(<ResultDisplay query={query} onCancel={mockOnCancel} />);

    const cancelButton: HTMLElement = screen.getByRole('button', { name: /cancel query/i });
    await user.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalledTimes(1);
  });

  it('should show spinner for processing queries', () => {
    const query: Query = {
      id: 'query-8',
      query_text: 'Show me data',
      status: 'processing',
      submitted_at: '2024-01-01T00:00:00Z',
    };

    render(<ResultDisplay query={query} />);

    expect(screen.getByText(/processing your query/i)).toBeInTheDocument();
  });
});
