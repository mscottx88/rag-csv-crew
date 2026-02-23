/**
 * Datasets API service
 * Handles dataset upload, list, get, and delete operations
 */

import api from './api';
import type { Dataset, DatasetList, UploadProgress } from '../types';
import { AxiosResponse, AxiosError, AxiosProgressEvent } from 'axios';

/**
 * List all datasets for the authenticated user
 * @returns DatasetList with datasets array and total count
 */
export const list = async (): Promise<DatasetList> => {
  try {
    const response: AxiosResponse<DatasetList> = await api.get<DatasetList>('/datasets');
    return response.data;
  } catch (error) {
    console.error('Failed to list datasets:', error);
    throw error;
  }
};

/**
 * Upload a CSV file as a new dataset
 * @param file CSV file to upload
 * @param onProgress Optional callback for upload progress
 * @returns Dataset object with metadata
 * @throws {Error} If file validation fails or upload fails
 */
export const upload = async (
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<Dataset> => {
  // Validate file type
  if (!file.name.toLowerCase().endsWith('.csv')) {
    throw new Error('Only CSV files are allowed');
  }

  // Validate file size (max 100MB)
  const maxSize: number = 100 * 1024 * 1024; // 100MB in bytes
  if (file.size > maxSize) {
    throw new Error('File size exceeds 100MB limit');
  }

  try {
    const formData: FormData = new FormData();
    formData.append('file', file);

    const response: AxiosResponse<Dataset> = await api.post<Dataset>('/datasets', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent: AxiosProgressEvent): void => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total),
          };
          onProgress(progress);
        }
      },
    });

    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 400) {
        throw new Error(detail || 'Invalid file format');
      } else if (status === 409) {
        // Conflict: Filename already exists
        throw {
          status: 409,
          message: detail || 'A file with this name already exists',
          filename: file.name,
        };
      } else {
        throw new Error(detail || 'Upload failed. Please try again.');
      }
    }
    throw error;
  }
};

/**
 * Get dataset by ID
 * @param id Dataset ID
 * @returns Dataset object with full details
 * @throws {Error} If dataset not found or request fails
 */
export const get = async (id: string): Promise<Dataset> => {
  try {
    const response: AxiosResponse<Dataset> = await api.get<Dataset>(`/datasets/${id}`);
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 404) {
        throw new Error('Dataset not found');
      } else {
        throw new Error(detail || 'Failed to get dataset');
      }
    }
    throw error;
  }
};

/**
 * Delete dataset by ID
 * @param id Dataset ID
 * @throws {Error} If dataset not found or deletion fails
 */
export const deleteDataset = async (id: string): Promise<void> => {
  try {
    await api.delete(`/datasets/${id}`);
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 404) {
        throw new Error('Dataset not found');
      } else if (status === 403) {
        throw new Error('You do not have permission to delete this dataset');
      } else {
        throw new Error(detail || 'Failed to delete dataset');
      }
    }
    throw error;
  }
};
