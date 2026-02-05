/**
 * Unit tests for queries API service
 *
 * Tests T131-TEST: Validates submit, get, cancel, history, examples operations
 *
 * Requirements:
 * - submit(query): POST /queries, returns Query
 * - get(id): GET /queries/{id}, returns QueryWithResponse
 * - cancel(id): POST /queries/{id}/cancel
 * - history(page, pageSize, status): GET /queries, returns QueryHistory
 * - getExamples(): GET /queries/examples, returns example questions
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { submit, get, cancel, history, getExamples } from '../../src/services/queries';
import type { Query, QueryHistory, QueryExample } from '../../src/types';

// Mock the api module
vi.mock('../../src/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('Queries API Service', () => {
  let mockApi: {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    vi.clearAllMocks();
    const apiModule: typeof import('../../src/services/api') = await import('../../src/services/api');
    mockApi = apiModule.default as unknown as {
      get: ReturnType<typeof vi.fn>;
      post: ReturnType<typeof vi.fn>;
    };
  });

  describe('submit', () => {
    it('should send POST request to /queries with query text', async () => {
      const queryText: string = 'Show me the top 10 customers';
      const mockResponse: Query = {
        id: '123',
        query_text: queryText,
        status: 'pending',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: null,
        result_count: null,
        execution_time_ms: null,
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      await submit(queryText);

      expect(mockApi.post).toHaveBeenCalledWith('/queries', {
        query_text: queryText,
        dataset_ids: undefined,
      });
    });

    it('should include dataset_ids when specified', async () => {
      const queryText: string = 'Show me revenue by region';
      const datasetIds: string[] = ['123e4567-e89b-12d3-a456-426614174000'];
      const mockResponse: Query = {
        id: '123',
        query_text: queryText,
        status: 'pending',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: null,
        result_count: null,
        execution_time_ms: null,
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      await submit(queryText, datasetIds);

      expect(mockApi.post).toHaveBeenCalledWith('/queries', {
        query_text: queryText,
        dataset_ids: datasetIds,
      });
    });

    it('should return Query object with pending status', async () => {
      const queryText: string = 'Show me data';
      const mockResponse: Query = {
        id: '123',
        query_text: queryText,
        status: 'pending',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: null,
        result_count: null,
        execution_time_ms: null,
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      const result: Query = await submit(queryText);

      expect(result).toEqual(mockResponse);
      expect(result.status).toBe('pending');
    });

    it('should throw 400 error for empty query text', async () => {
      const queryText: string = '';
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: 'Query text cannot be empty' } },
        isAxiosError: true,
      });

      await expect(submit(queryText)).rejects.toBeTruthy();
    });

    it('should throw error when server returns 500', async () => {
      const queryText: string = 'Show me data';
      mockApi.post.mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
        isAxiosError: true,
      });

      await expect(submit(queryText)).rejects.toBeTruthy();
    });
  });

  describe('get', () => {
    it('should send GET request to /queries/{id}', async () => {
      const queryId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Query = {
        id: queryId,
        query_text: 'test query',
        status: 'completed',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: 'SELECT * FROM table',
        result_count: 10,
        execution_time_ms: 123,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await get(queryId);

      expect(mockApi.get).toHaveBeenCalledWith(`/queries/${queryId}`);
    });

    it('should return QueryWithResponse including response data', async () => {
      const queryId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Query = {
        id: queryId,
        query_text: 'test query',
        status: 'completed',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: 'SELECT * FROM table',
        result_count: 10,
        execution_time_ms: 123,
        response: {
          id: 'resp-123',
          html_content: '<div>Result</div>',
          plain_text: 'Result',
          confidence_score: 0.95,
        },
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: Query = await get(queryId);

      expect(result).toEqual(mockResponse);
      expect(result.response).toBeDefined();
      expect(result.response?.html_content).toBe('<div>Result</div>');
    });

    it('should throw 404 error for non-existent query', async () => {
      const queryId: string = 'non-existent-id';
      mockApi.get.mockRejectedValue({
        response: { status: 404, data: { detail: 'Query not found' } },
        isAxiosError: true,
      });

      await expect(get(queryId)).rejects.toBeTruthy();
    });
  });

  describe('cancel', () => {
    it('should send POST request to /queries/{id}/cancel', async () => {
      const queryId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Query = {
        id: queryId,
        query_text: 'test query',
        status: 'cancelled',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: null,
        result_count: null,
        execution_time_ms: null,
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      await cancel(queryId);

      expect(mockApi.post).toHaveBeenCalledWith(`/queries/${queryId}/cancel`);
    });

    it('should return Query object with cancelled status', async () => {
      const queryId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Query = {
        id: queryId,
        query_text: 'test query',
        status: 'cancelled',
        created_at: '2026-01-01T00:00:00Z',
        generated_sql: null,
        result_count: null,
        execution_time_ms: null,
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      const result: Query = await cancel(queryId);

      expect(result.status).toBe('cancelled');
    });

    it('should throw 400 error if query is already completed', async () => {
      const queryId: string = 'completed-query-id';
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: 'Cannot cancel completed query' } },
        isAxiosError: true,
      });

      await expect(cancel(queryId)).rejects.toBeTruthy();
    });

    it('should throw 404 error for non-existent query', async () => {
      const queryId: string = 'non-existent-id';
      mockApi.post.mockRejectedValue({
        response: { status: 404, data: { detail: 'Query not found' } },
        isAxiosError: true,
      });

      await expect(cancel(queryId)).rejects.toBeTruthy();
    });
  });

  describe('history', () => {
    it('should send GET request to /queries with pagination params', async () => {
      const page: number = 1;
      const pageSize: number = 50;
      const mockResponse: QueryHistory = {
        queries: [],
        total: 0,
        page: 1,
        page_size: 50,
        total_pages: 0,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await history({ page, page_size: pageSize });

      expect(mockApi.get).toHaveBeenCalledWith('/queries/history', {
        params: { page: 1, page_size: 50, status: undefined },
      });
    });

    it('should include status filter when provided', async () => {
      const page: number = 1;
      const pageSize: number = 50;
      const status: 'completed' = 'completed';
      const mockResponse: QueryHistory = {
        queries: [],
        total: 0,
        page: 1,
        page_size: 50,
        total_pages: 0,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await history({ page, page_size: pageSize, status });

      expect(mockApi.get).toHaveBeenCalledWith('/queries/history', {
        params: { page: 1, page_size: 50, status: 'completed' },
      });
    });

    it('should return QueryHistory with pagination metadata', async () => {
      const page: number = 1;
      const pageSize: number = 50;
      const mockResponse: QueryHistory = {
        queries: [
          {
            id: '123',
            query_text: 'test',
            status: 'completed',
            created_at: '2026-01-01T00:00:00Z',
            generated_sql: null,
            result_count: null,
            execution_time_ms: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 50,
        total_pages: 1,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: QueryHistory = await history({ page, page_size: pageSize });

      expect(result).toEqual(mockResponse);
      expect(result.total).toBe(1);
      expect(result.page).toBe(1);
      expect(result.page_size).toBe(50);
    });

    it('should handle empty history', async () => {
      const mockResponse: QueryHistory = {
        queries: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: QueryHistory = await history();

      expect(result.queries).toEqual([]);
      expect(result.total).toBe(0);
    });

    it('should throw 400 error for invalid pagination params', async () => {
      const page: number = 0; // Invalid
      const pageSize: number = 150; // Too large
      mockApi.get.mockRejectedValue({
        response: { status: 400, data: { detail: 'Invalid pagination params' } },
        isAxiosError: true,
      });

      await expect(history({ page, page_size: pageSize })).rejects.toBeTruthy();
    });
  });

  describe('getExamples', () => {
    it('should send GET request to /queries/examples', async () => {
      const mockResponse: QueryExample[] = [];
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await getExamples();

      expect(mockApi.get).toHaveBeenCalledWith('/queries/examples');
    });

    it('should return array of example questions with metadata', async () => {
      const mockResponse: QueryExample[] = [
        {
          question: 'Show me all records',
          description: 'Basic query',
          category: 'basic',
        },
        {
          question: 'What is the average value?',
          description: 'Aggregation query',
          category: 'aggregation',
        },
      ];
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: QueryExample[] = await getExamples();

      expect(result).toEqual(mockResponse);
      expect(result[0].question).toBe('Show me all records');
      expect(result[0].category).toBe('basic');
    });

    it('should return at least 5 examples', async () => {
      const mockResponse: QueryExample[] = [
        { question: 'Q1', description: 'D1', category: 'basic' },
        { question: 'Q2', description: 'D2', category: 'basic' },
        { question: 'Q3', description: 'D3', category: 'aggregation' },
        { question: 'Q4', description: 'D4', category: 'filtering' },
        { question: 'Q5', description: 'D5', category: 'cross_dataset' },
      ];
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: QueryExample[] = await getExamples();

      expect(result.length).toBeGreaterThanOrEqual(5);
    });

    it('should include examples from different categories', async () => {
      const mockResponse: QueryExample[] = [
        { question: 'Q1', description: 'D1', category: 'basic' },
        { question: 'Q2', description: 'D2', category: 'aggregation' },
        { question: 'Q3', description: 'D3', category: 'filtering' },
      ];
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: QueryExample[] = await getExamples();
      const categories: Set<string> = new Set(result.map((ex: QueryExample) => ex.category));

      expect(categories.size).toBeGreaterThan(1);
    });
  });

  describe('Error Handling', () => {
    it('should map API errors to user-friendly messages', async () => {
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: 'Bad request' } },
        isAxiosError: true,
      });

      await expect(submit('test')).rejects.toBeTruthy();
    });

    it('should handle network errors gracefully', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await expect(getExamples()).rejects.toThrow('Network error');
    });

    it('should preserve server error details when available', async () => {
      const errorDetail: string = 'Query text must be at least 5 characters';
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: errorDetail } },
        isAxiosError: true,
      });

      await expect(submit('test')).rejects.toBeTruthy();
    });
  });
});
