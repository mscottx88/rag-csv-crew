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
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: 'Invalid username' } },
        isAxiosError: true,
      });

      await expect(login('baduser')).rejects.toThrow('Invalid username');
    });

    it('should throw error when server returns 500', async () => {
      mockApi.post.mockRejectedValue({
        response: { status: 500, data: { detail: 'Internal server error' } },
        isAxiosError: true,
      });

      await expect(login('testuser')).rejects.toThrow('Server error. Please try again later.');
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
      mockApi.get.mockRejectedValue({
        response: { status: 401, data: { detail: 'Not authenticated' } },
        isAxiosError: true,
      });

      await expect(getCurrentUser()).rejects.toThrow('Not authenticated. Please login.');
    });

    it('should throw error when token is invalid', async () => {
      mockApi.get.mockRejectedValue({
        response: { status: 401, data: { detail: 'Invalid token' } },
        isAxiosError: true,
      });

      await expect(getCurrentUser()).rejects.toThrow('Not authenticated. Please login.');
    });
  });

  describe('Error Messages', () => {
    it('should provide user-friendly error messages', async () => {
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: {} },
        isAxiosError: true,
      });

      await expect(login('testuser')).rejects.toThrow('Invalid username');
    });

    it('should preserve server error messages when available', async () => {
      const serverError: string = 'Username must be at least 3 characters';
      mockApi.post.mockRejectedValue({
        response: { status: 400, data: { detail: serverError } },
        isAxiosError: true,
      });

      await expect(login('ab')).rejects.toThrow(serverError);
    });
  });
});
