/**
 * Queries API service
 * Handles query submission, retrieval, cancellation, and history
 */

import api from './api';
import type { Query, QueryCreate, QueryHistory, QueryExample, PaginationParams } from '../types';
import { AxiosResponse } from 'axios';

/**
 * Submit a new natural language query
 * @param queryText Natural language query text
 * @param datasetIds Optional list of dataset IDs to query
 * @returns Query object with initial status
 */
export const submit = async (queryText: string, datasetIds?: string[]): Promise<Query> => {
  const request: QueryCreate = {
    query_text: queryText,
    dataset_ids: datasetIds,
  };

  const response: AxiosResponse<Query> = await api.post<Query>('/queries', request);
  return response.data;
};

/**
 * Get query by ID
 * @param id Query ID
 * @returns Query object with current status and results
 */
export const get = async (id: string): Promise<Query> => {
  const response: AxiosResponse<Query> = await api.get<Query>(`/queries/${id}`);
  return response.data;
};

/**
 * Cancel a running query
 * @param id Query ID
 * @returns Updated Query object with cancelled status
 */
export const cancel = async (id: string): Promise<Query> => {
  const response: AxiosResponse<Query> = await api.post<Query>(`/queries/${id}/cancel`);
  return response.data;
};

/**
 * Get query history with pagination and filtering
 * @param params Pagination and filter parameters
 * @returns QueryHistory with queries array and pagination info
 */
export const history = async (params?: PaginationParams): Promise<QueryHistory> => {
  const response: AxiosResponse<QueryHistory> = await api.get<QueryHistory>('/queries/history', {
    params: {
      page: params?.page || 1,
      page_size: params?.page_size || 20,
      status: params?.status,
    },
  });
  return response.data;
};

/**
 * Get example queries to help users get started
 * @returns Array of QueryExample objects
 */
export const getExamples = async (): Promise<QueryExample[]> => {
  const response: AxiosResponse<QueryExample[]> = await api.get<QueryExample[]>('/queries/examples');
  return response.data;
};

/**
 * Poll query status until completion
 * Polls every 2 seconds until status is completed, failed, or cancelled
 * @param id Query ID
 * @param onUpdate Callback for status updates
 * @returns Final Query object
 */
export const pollUntilComplete = async (
  id: string,
  onUpdate?: (query: Query) => void
): Promise<Query> => {
  const pollInterval: number = 2000; // 2 seconds per FR-025

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const query: Query = await get(id);

    if (onUpdate) {
      onUpdate(query);
    }

    // Check if query is in terminal state
    if (query.status === 'completed' || query.status === 'failed' || query.status === 'cancelled') {
      return query;
    }

    // Wait before next poll
    await new Promise((resolve: (value: unknown) => void): void => {
      setTimeout(resolve, pollInterval);
    });
  }
};
