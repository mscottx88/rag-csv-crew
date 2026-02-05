/**
 * Unit tests for auth API service
 *
 * Tests T129-TEST: Validates login and getCurrentUser functions
 *
 * Requirements:
 * - login(username): POST /auth/login, returns AuthToken
 * - getCurrentUser(): GET /auth/me, returns User
 * - Proper error handling for auth failures
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { login, getCurrentUser } from '../../src/services/auth';
import type { AuthToken, User } from '../../src/types';
import { AxiosError, type InternalAxiosRequestConfig } from 'axios';

// Mock the api module
vi.mock('../../src/services/api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('Auth API Service', () => {
  let mockApi: { post: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn> };

  beforeEach(async () => {
    vi.clearAllMocks();
    const apiModule: typeof import('../../src/services/api') = await import('../../src/services/api');
    mockApi = apiModule.default as unknown as { post: ReturnType<typeof vi.fn>; get: ReturnType<typeof vi.fn> };
  });

  describe('login', () => {
    it('should send POST request to /auth/login with username', async () => {
      const username: string = 'testuser';
      const mockResponse: AuthToken = {
        access_token: 'mock-token-123',
        token_type: 'bearer',
        username: 'testuser',
      };

      mockApi.post.mockResolvedValue({ data: mockResponse });

      await login(username);

      expect(mockApi.post).toHaveBeenCalledWith('/auth/login', { username: 'testuser' });
    });

    it('should return AuthToken with access_token and token_type', async () => {
      const username: string = 'testuser';
      const mockResponse: AuthToken = {
        access_token: 'mock-token-123',
        token_type: 'bearer',
        username: 'testuser',
      };

      mockApi.post.mockResolvedValue({ data: mockResponse });

      const result: AuthToken = await login(username);

      expect(result).toEqual(mockResponse);
      expect(result.access_token).toBe('mock-token-123');
      expect(result.token_type).toBe('bearer');
      expect(result.username).toBe('testuser');
    });

    it('should throw error when username is empty', async () => {
      await expect(login('')).rejects.toThrow('Username is required');
      await expect(login('   ')).rejects.toThrow('Username is required');
    });

    it('should throw error when server returns 400', async () => {
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 400',
        '400',
        config,
        undefined,
        {
          status: 400,
          statusText: 'Bad Request',
          data: { detail: 'Invalid username' },
          headers: {},
          config,
        }
      );
      mockApi.post.mockRejectedValue(error);

      await expect(login('baduser')).rejects.toThrow(/Invalid username/);
    });

    it('should throw error when server returns 500', async () => {
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 500',
        '500',
        config,
        undefined,
        {
          status: 500,
          statusText: 'Internal Server Error',
          data: { detail: 'Internal server error' },
          headers: {},
          config,
        }
      );
      mockApi.post.mockRejectedValue(error);

      await expect(login('testuser')).rejects.toThrow(/Server error/);
    });
  });

  describe('getCurrentUser', () => {
    it('should send GET request to /auth/me', async () => {
      const mockResponse: User = { username: 'testuser' };

      mockApi.get.mockResolvedValue({ data: mockResponse });

      await getCurrentUser();

      expect(mockApi.get).toHaveBeenCalledWith('/auth/me');
    });

    it('should return User object with username', async () => {
      const mockResponse: User = { username: 'testuser' };

      mockApi.get.mockResolvedValue({ data: mockResponse });

      const result: User = await getCurrentUser();

      expect(result).toEqual(mockResponse);
      expect(result.username).toBe('testuser');
    });

    it('should throw error when not authenticated (401)', async () => {
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 401',
        '401',
        config,
        undefined,
        {
          status: 401,
          statusText: 'Unauthorized',
          data: { detail: 'Not authenticated' },
          headers: {},
          config,
        }
      );
      mockApi.get.mockRejectedValue(error);

      await expect(getCurrentUser()).rejects.toThrow(/Not authenticated/);
    });

    it('should throw error when token is invalid', async () => {
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 401',
        '401',
        config,
        undefined,
        {
          status: 401,
          statusText: 'Unauthorized',
          data: { detail: 'Invalid token' },
          headers: {},
          config,
        }
      );
      mockApi.get.mockRejectedValue(error);

      await expect(getCurrentUser()).rejects.toThrow(/Not authenticated/);
    });
  });

  describe('Error Messages', () => {
    it('should provide user-friendly error messages', async () => {
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 400',
        '400',
        config,
        undefined,
        {
          status: 400,
          statusText: 'Bad Request',
          data: {},
          headers: {},
          config,
        }
      );
      mockApi.post.mockRejectedValue(error);

      await expect(login('testuser')).rejects.toThrow(/Invalid username/);
    });

    it('should preserve server error messages when available', async () => {
      const serverError: string = 'Username must be at least 3 characters';
      const config: InternalAxiosRequestConfig = {} as InternalAxiosRequestConfig;
      const error: AxiosError = new AxiosError(
        'Request failed with status code 400',
        '400',
        config,
        undefined,
        {
          status: 400,
          statusText: 'Bad Request',
          data: { detail: serverError },
          headers: {},
          config,
        }
      );
      mockApi.post.mockRejectedValue(error);

      await expect(login('ab')).rejects.toThrow(/Username must be at least 3 characters/);
    });
  });
});
