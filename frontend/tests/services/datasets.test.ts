/**
 * Unit tests for datasets API service
 *
 * Tests T130-TEST: Validates list, upload, get, delete operations
 *
 * Requirements:
 * - list(): GET /datasets, returns DatasetList
 * - upload(file): POST /datasets with multipart/form-data
 * - get(id): GET /datasets/{id}, returns Dataset
 * - delete(id): DELETE /datasets/{id}
 * - Progress tracking for uploads
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { list, upload, get, deleteDataset } from '../../src/services/datasets';
import type { Dataset, DatasetList } from '../../src/types';
import { AxiosError, type InternalAxiosRequestConfig } from 'axios';

// Mock the api module
vi.mock('../../src/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Datasets API Service', () => {
  let mockApi: {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    vi.clearAllMocks();
    const apiModule: typeof import('../../src/services/api') = await import('../../src/services/api');
    mockApi = apiModule.default as unknown as {
      get: ReturnType<typeof vi.fn>;
      post: ReturnType<typeof vi.fn>;
      delete: ReturnType<typeof vi.fn>;
    };
  });

  describe('list', () => {
    it('should send GET request to /datasets', async () => {
      const mockResponse: DatasetList = { datasets: [], total: 0 };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await list();

      expect(mockApi.get).toHaveBeenCalledWith('/datasets');
    });

    it('should return DatasetList with datasets array', async () => {
      const mockResponse: DatasetList = {
        datasets: [
          {
            id: '123',
            filename: 'test.csv',
            row_count: 100,
            column_count: 5,
            columns: [],
            created_at: '2026-01-01T00:00:00Z',
            owner: 'testuser',
          },
        ],
        total: 1,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: DatasetList = await list();

      expect(result).toEqual(mockResponse);
      expect(result.datasets).toHaveLength(1);
      expect(result.total).toBe(1);
    });

    it('should handle empty dataset list', async () => {
      const mockResponse: DatasetList = { datasets: [], total: 0 };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: DatasetList = await list();

      expect(result.datasets).toEqual([]);
      expect(result.total).toBe(0);
    });

    it('should include dataset metadata (id, filename, row_count, column_count)', async () => {
      const mockResponse: DatasetList = {
        datasets: [
          {
            id: '123',
            filename: 'test.csv',
            row_count: 100,
            column_count: 5,
            columns: [],
            created_at: '2026-01-01T00:00:00Z',
            owner: 'testuser',
          },
        ],
        total: 1,
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: DatasetList = await list();
      const dataset: Dataset = result.datasets[0];

      expect(dataset.id).toBe('123');
      expect(dataset.filename).toBe('test.csv');
      expect(dataset.row_count).toBe(100);
      expect(dataset.column_count).toBe(5);
    });
  });

  describe('upload', () => {
    it('should send POST request to /datasets with multipart/form-data', async () => {
      const mockFile: File = new File(['content'], 'test.csv', { type: 'text/csv' });
      const mockResponse: Dataset = {
        id: '123',
        filename: 'test.csv',
        row_count: 10,
        column_count: 3,
        columns: [],
        created_at: '2026-01-01T00:00:00Z',
        owner: 'testuser',
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      await upload(mockFile);

      expect(mockApi.post).toHaveBeenCalledWith(
        '/datasets',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      );
    });

    it('should accept onProgress callback for upload progress', async () => {
      const mockFile: File = new File(['content'], 'test.csv', { type: 'text/csv' });
      const onProgress: ReturnType<typeof vi.fn> = vi.fn();
      const mockResponse: Dataset = {
        id: '123',
        filename: 'test.csv',
        row_count: 10,
        column_count: 3,
        columns: [],
        created_at: '2026-01-01T00:00:00Z',
        owner: 'testuser',
      };

      mockApi.post.mockImplementation((url: string, data: unknown, config?: { onUploadProgress?: (event: { loaded: number; total: number }) => void }) => {
        // Simulate progress
        if (config?.onUploadProgress) {
          config.onUploadProgress({ loaded: 50, total: 100 });
          config.onUploadProgress({ loaded: 100, total: 100 });
        }
        return Promise.resolve({ data: mockResponse });
      });

      await upload(mockFile, onProgress);

      expect(onProgress).toHaveBeenCalledWith({ loaded: 50, total: 100, percentage: 50 });
      expect(onProgress).toHaveBeenCalledWith({ loaded: 100, total: 100, percentage: 100 });
    });

    it('should return Dataset object on successful upload', async () => {
      const mockFile: File = new File(['content'], 'test.csv', { type: 'text/csv' });
      const mockResponse: Dataset = {
        id: '123',
        filename: 'test.csv',
        row_count: 10,
        column_count: 3,
        columns: [],
        created_at: '2026-01-01T00:00:00Z',
        owner: 'testuser',
      };
      mockApi.post.mockResolvedValue({ data: mockResponse });

      const result: Dataset = await upload(mockFile);

      expect(result).toEqual(mockResponse);
      expect(result.id).toBe('123');
      expect(result.filename).toBe('test.csv');
    });

    it('should handle file validation errors (400)', async () => {
      const mockFile: File = new File(['invalid'], 'test.txt', { type: 'text/plain' });

      await expect(upload(mockFile)).rejects.toThrow('Only CSV files are allowed');
    });

    it('should handle filename conflicts (409)', async () => {
      const mockFile: File = new File(['content'], 'existing.csv', { type: 'text/csv' });
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 409',
        '409',
        config,
        undefined,
        {
          status: 409,
          statusText: 'Conflict',
          data: { detail: 'File already exists' },
          headers: {},
          config,
        }
      );
      mockApi.post.mockRejectedValue(error);

      await expect(upload(mockFile)).rejects.toMatchObject({
        status: 409,
        message: 'File already exists',
        filename: 'existing.csv',
      });
    });

    it('should handle upload cancellation', async () => {
      const mockFile: File = new File(['content'], 'test.csv', { type: 'text/csv' });
      mockApi.post.mockRejectedValue(new Error('Upload canceled'));

      await expect(upload(mockFile)).rejects.toThrow('Upload canceled');
    });
  });

  describe('get', () => {
    it('should send GET request to /datasets/{id}', async () => {
      const datasetId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Dataset = {
        id: datasetId,
        filename: 'test.csv',
        row_count: 100,
        column_count: 5,
        columns: [],
        created_at: '2026-01-01T00:00:00Z',
        owner: 'testuser',
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      await get(datasetId);

      expect(mockApi.get).toHaveBeenCalledWith(`/datasets/${datasetId}`);
    });

    it('should return Dataset object with full details', async () => {
      const datasetId: string = '123e4567-e89b-12d3-a456-426614174000';
      const mockResponse: Dataset = {
        id: datasetId,
        filename: 'test.csv',
        row_count: 100,
        column_count: 5,
        columns: [
          { name: 'id', data_type: 'integer' },
          { name: 'name', data_type: 'text' },
        ],
        created_at: '2026-01-01T00:00:00Z',
        owner: 'testuser',
      };
      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: Dataset = await get(datasetId);

      expect(result).toEqual(mockResponse);
      expect(result.columns).toHaveLength(2);
    });

    it('should throw 404 error for non-existent dataset', async () => {
      const datasetId: string = 'non-existent-id';
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 404',
        '404',
        config,
        undefined,
        {
          status: 404,
          statusText: 'Not Found',
          data: { detail: 'Dataset not found' },
          headers: {},
          config,
        }
      );
      mockApi.get.mockRejectedValue(error);

      await expect(get(datasetId)).rejects.toThrow(/Dataset not found/);
    });
  });

  describe('delete', () => {
    it('should send DELETE request to /datasets/{id}', async () => {
      const datasetId: string = '123e4567-e89b-12d3-a456-426614174000';
      mockApi.delete.mockResolvedValue({ status: 204 });

      await deleteDataset(datasetId);

      expect(mockApi.delete).toHaveBeenCalledWith(`/datasets/${datasetId}`);
    });

    it('should return success on 204 No Content', async () => {
      const datasetId: string = '123e4567-e89b-12d3-a456-426614174000';
      mockApi.delete.mockResolvedValue({ status: 204 });

      await expect(deleteDataset(datasetId)).resolves.toBeUndefined();
    });

    it('should throw 404 error for non-existent dataset', async () => {
      const datasetId: string = 'non-existent-id';
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 404',
        '404',
        config,
        undefined,
        {
          status: 404,
          statusText: 'Not Found',
          data: { detail: 'Dataset not found' },
          headers: {},
          config,
        }
      );
      mockApi.delete.mockRejectedValue(error);

      await expect(deleteDataset(datasetId)).rejects.toThrow(/Dataset not found/);
    });

    it('should throw 403 error if not owner', async () => {
      const datasetId: string = 'someone-elses-dataset';
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 403',
        '403',
        config,
        undefined,
        {
          status: 403,
          statusText: 'Forbidden',
          data: { detail: 'Forbidden' },
          headers: {},
          config,
        }
      );
      mockApi.delete.mockRejectedValue(error);

      await expect(deleteDataset(datasetId)).rejects.toThrow(/You do not have permission/);
    });
  });

  describe('Error Handling', () => {
    it('should map API errors to user-friendly messages', async () => {
      mockApi.get.mockRejectedValue({
        response: { status: 500, data: {} },
        isAxiosError: true,
      });

      await expect(list()).rejects.toBeTruthy();
    });

    it('should handle network errors gracefully', async () => {
      mockApi.get.mockRejectedValue(new Error('Network error'));

      await expect(list()).rejects.toThrow('Network error');
    });
  });
});
