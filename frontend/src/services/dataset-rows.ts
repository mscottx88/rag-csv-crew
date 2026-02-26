/**
 * Dataset Rows API service
 * Fetches paginated row data for the Dataset Inspector
 */

import api from './api';
import type { DatasetRowsResponse } from '../types';
import { AxiosResponse, AxiosError } from 'axios';

/**
 * Fetch paginated rows from a dataset
 * @param datasetId UUID of the dataset
 * @param offset Row offset (default 0)
 * @param limit Max rows to fetch (default 50)
 * @returns DatasetRowsResponse with columns, rows, and pagination info
 */
export const getRows = async (
  datasetId: string,
  offset: number = 0,
  limit: number = 50,
): Promise<DatasetRowsResponse> => {
  try {
    const response: AxiosResponse<DatasetRowsResponse> = await api.get<DatasetRowsResponse>(
      `/datasets/${datasetId}/rows`,
      { params: { offset, limit } },
    );
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 404) {
        throw new Error('Dataset not found');
      } else {
        throw new Error(detail || 'Failed to fetch dataset rows');
      }
    }
    throw error;
  }
};
