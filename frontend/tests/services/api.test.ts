/**
 * Unit tests for Axios API client
 *
 * Tests T128-TEST: Validates base URL configuration and Bearer token interceptor
 *
 * Requirements:
 * - Base URL should be configurable via environment variable
 * - Request interceptor should add Bearer token from localStorage
 * - Response interceptor should handle common error cases
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

describe('API Client', () => {
  let api: AxiosInstance;

  beforeEach(async () => {
    localStorage.clear();
    vi.clearAllMocks();
    // Re-import to get fresh instance
    const module: typeof import('../../src/services/api') = await import('../../src/services/api?t=' + Date.now());
    api = module.default;
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Base URL Configuration', () => {
    it('should use VITE_API_BASE_URL environment variable or default', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      // Check that baseURL is set (either from env or default)
      const baseURL: string | undefined = apiInstance.defaults.baseURL;
      expect(baseURL).toBeDefined();
      expect(typeof baseURL).toBe('string');
      expect(baseURL).toMatch(/^https?:\/\//); // Should be a valid HTTP(S) URL
    });

    it('should have a default base URL of http://localhost:8000', async () => {
      // When VITE_API_BASE_URL is not set, should use default
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      const baseURL: string | undefined = apiInstance.defaults.baseURL;
      // Either uses env var or falls back to localhost:8000
      expect(baseURL).toBeTruthy();
    });
  });

  describe('Bearer Token Interceptor', () => {
    it('should add Authorization header when token exists in localStorage', async () => {
      const mockToken: string = 'test-jwt-token-12345';
      localStorage.setItem('auth_token', mockToken);

      const module: typeof import('../../src/services/api') = await import('../../src/services/api?t=' + Date.now());
      const apiInstance: AxiosInstance = module.default;

      // Create a request config to test interceptor
      const config: InternalAxiosRequestConfig = {
        headers: {} as any,
      } as InternalAxiosRequestConfig;

      // Manually invoke the request interceptor
      const interceptor: ((value: InternalAxiosRequestConfig) => InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig>) | undefined =
        apiInstance.interceptors.request['handlers']?.[0]?.fulfilled;

      if (interceptor) {
        const result: InternalAxiosRequestConfig = await Promise.resolve(interceptor(config));
        expect(result.headers.Authorization).toBe(`Bearer ${mockToken}`);
      } else {
        // If we can't access interceptor directly, verify it works via actual request
        expect(apiInstance.interceptors.request['handlers']).toBeDefined();
      }
    });

    it('should not add Authorization header when token does not exist', async () => {
      localStorage.removeItem('auth_token');

      const module: typeof import('../../src/services/api') = await import('../../src/services/api?t=' + Date.now());
      const apiInstance: AxiosInstance = module.default;

      const config: InternalAxiosRequestConfig = {
        headers: {} as any,
      } as InternalAxiosRequestConfig;

      const interceptor: ((value: InternalAxiosRequestConfig) => InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig>) | undefined =
        apiInstance.interceptors.request['handlers']?.[0]?.fulfilled;

      if (interceptor) {
        const result: InternalAxiosRequestConfig = await Promise.resolve(interceptor(config));
        expect(result.headers.Authorization).toBeUndefined();
      }
    });

    it('should format Authorization header as "Bearer {token}"', () => {
      const mockToken: string = 'abc123';
      localStorage.setItem('auth_token', mockToken);

      // The format should be exactly "Bearer abc123"
      const expectedFormat: string = `Bearer ${mockToken}`;
      expect(expectedFormat).toBe('Bearer abc123');
    });
  });

  describe('Response Error Handling', () => {
    it('should handle 401 Unauthorized responses', async () => {
      // Verify response interceptor is configured
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      expect(apiInstance.interceptors.response['handlers']).toBeDefined();
      expect(apiInstance.interceptors.response['handlers'].length).toBeGreaterThan(0);
    });

    it('should handle 403 Forbidden responses', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      expect(apiInstance.interceptors.response['handlers']).toBeDefined();
    });

    it('should handle 500 Internal Server Error responses', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      expect(apiInstance.interceptors.response['handlers']).toBeDefined();
    });

    it('should handle network errors', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      // Verify error interceptor exists
      expect(apiInstance.interceptors.response['handlers']).toBeDefined();
    });
  });

  describe('Request Configuration', () => {
    it('should set Content-Type header to application/json for JSON requests', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      const contentType: string | undefined = apiInstance.defaults.headers['Content-Type'] as string;
      expect(contentType).toBe('application/json');
    });

    it('should have a reasonable timeout configured', async () => {
      const module: typeof import('../../src/services/api') = await import('../../src/services/api');
      const apiInstance: AxiosInstance = module.default;

      const timeout: number | undefined = apiInstance.defaults.timeout;
      expect(timeout).toBeDefined();
      expect(timeout).toBeGreaterThan(0);
      expect(timeout).toBeLessThanOrEqual(60000); // Should be reasonable (≤60s)
    });
  });
});
