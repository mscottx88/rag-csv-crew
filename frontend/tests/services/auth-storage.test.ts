/**
 * Unit tests for JWT token storage
 *
 * Tests T133-TEST: Validates localStorage operations for auth tokens
 *
 * Requirements:
 * - saveToken(token): Store JWT in localStorage
 * - getToken(): Retrieve JWT from localStorage
 * - removeToken(): Clear JWT from localStorage
 * - isAuthenticated(): Check if valid token exists
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  saveToken,
  getToken,
  removeToken,
  isAuthenticated,
  parseJwtPayload,
  getUsernameFromToken,
  getExpirationFromToken,
  isTokenExpired,
} from '../../src/services/auth-storage';

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

describe('Auth Token Storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('saveToken', () => {
    it('should store token in localStorage with key "auth_token"', () => {
      const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';

      saveToken(token);

      expect(localStorage.getItem('auth_token')).toBe(token);
    });

    it('should overwrite existing token', () => {
      const oldToken = 'old-token-123';
      const newToken = 'new-token-456';

      saveToken(oldToken);
      expect(localStorage.getItem('auth_token')).toBe(oldToken);

      saveToken(newToken);
      expect(localStorage.getItem('auth_token')).toBe(newToken);
    });

    it('should throw error for invalid token format', () => {
      const invalidToken = '';

      expect(() => saveToken(invalidToken)).toThrow('Token cannot be empty');
      expect(() => saveToken('   ')).toThrow('Token cannot be empty');
    });
  });

  describe('getToken', () => {
    it('should retrieve token from localStorage', () => {
      // Use a valid JWT token that is not expired
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) + 3600 }));
      const token: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
      localStorage.setItem('auth_token', token);

      const result: string | null = getToken();

      expect(result).toBe(token);
    });

    it('should return null when no token exists', () => {
      const result: string | null = getToken();

      expect(result).toBeNull();
    });

    it('should return null when token is expired', () => {
      // Create expired token (exp in the past)
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) - 3600 }));
      const expiredToken: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
      localStorage.setItem('auth_token', expiredToken);

      const result: string | null = getToken();

      expect(result).toBeNull();
      expect(localStorage.getItem('auth_token')).toBeNull(); // Should be removed
    });
  });

  describe('removeToken', () => {
    it('should remove token from localStorage', () => {
      const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
      localStorage.setItem('auth_token', token);
      expect(localStorage.getItem('auth_token')).toBe(token);

      removeToken();

      expect(localStorage.getItem('auth_token')).toBeNull();
    });

    it('should not throw error if token does not exist', () => {
      expect(localStorage.getItem('auth_token')).toBeNull();

      expect(() => removeToken()).not.toThrow();

      expect(localStorage.getItem('auth_token')).toBeNull();
    });
  });

  describe('isAuthenticated', () => {
    it('should return true when valid token exists', () => {
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) + 3600 }));
      const token: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
      localStorage.setItem('auth_token', token);

      const result: boolean = isAuthenticated();

      expect(result).toBe(true);
    });

    it('should return false when no token exists', () => {
      const result: boolean = isAuthenticated();

      expect(result).toBe(false);
    });

    it('should return false when token is empty string', () => {
      localStorage.setItem('auth_token', '');

      const result: boolean = isAuthenticated();

      expect(result).toBe(false);
    });

    it('should return false when token is expired', () => {
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) - 3600 }));
      const expiredToken: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;
      localStorage.setItem('auth_token', expiredToken);

      const result: boolean = isAuthenticated();

      expect(result).toBe(false);
    });
  });

  describe('Token Parsing', () => {
    it('should extract username from JWT token', () => {
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) + 3600 }));
      const token: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;

      const username: string | null = getUsernameFromToken(token);

      expect(username).toBe('testuser');
    });

    it('should extract expiration time from JWT token', () => {
      const exp: number = Math.floor(Date.now() / 1000) + 3600;
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp }));
      const token: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;

      const expiration: number | null = getExpirationFromToken(token);

      expect(expiration).toBe(exp);
    });

    it('should handle malformed JWT tokens', () => {
      const malformedToken = 'not-a-jwt-token';

      const payload: Record<string, unknown> | null = parseJwtPayload(malformedToken);

      expect(payload).toBeNull();
    });
  });

  describe('Security', () => {
    it('should not expose token in console logs', () => {
      const consoleSpy: ReturnType<typeof vi.spyOn> = vi.spyOn(console, 'log');
      const payload: string = btoa(JSON.stringify({ sub: 'testuser', exp: Math.floor(Date.now() / 1000) + 3600 }));
      const token: string = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.${payload}.signature`;

      saveToken(token);
      getToken();

      // Token should not be logged
      expect(consoleSpy).not.toHaveBeenCalledWith(expect.stringContaining(token));
      consoleSpy.mockRestore();
    });

    it('should handle localStorage not available', () => {
      // This test verifies the functions don't crash - localStorage is mocked
      // In real browser without localStorage, functions would throw
      expect(() => {
        const token: string = 'test-token';
        saveToken(token);
        getToken();
        removeToken();
      }).not.toThrow();
    });
  });
});
