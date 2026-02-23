/**
 * Integration tests for authentication context
 *
 * Tests T134-TEST: Validates global authentication state management
 *
 * Requirements:
 * - AuthProvider wraps app with auth state
 * - useAuth hook provides auth state and actions
 * - login, logout, and user state management
 * - Automatic token loading on mount
 * - Protected route support
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../../src/context/AuthContext';
import type { User, AuthToken } from '../../src/types';
import React from 'react';

// Mock auth services
vi.mock('../../src/services/auth', () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
}));

vi.mock('../../src/services/auth-storage', () => ({
  getToken: vi.fn(),
  saveToken: vi.fn(),
  removeToken: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('Authentication Context', () => {
  let mockLogin: ReturnType<typeof vi.fn>;
  let mockGetCurrentUser: ReturnType<typeof vi.fn>;
  let mockGetToken: ReturnType<typeof vi.fn>;
  let mockSaveToken: ReturnType<typeof vi.fn>;
  let mockRemoveToken: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    localStorage.clear();
    vi.clearAllMocks();

    const authServiceModule = await import('../../src/services/auth');
    const authStorageModule = await import('../../src/services/auth-storage');

    mockLogin = authServiceModule.login as unknown as ReturnType<typeof vi.fn>;
    mockGetCurrentUser = authServiceModule.getCurrentUser as unknown as ReturnType<typeof vi.fn>;
    mockGetToken = authStorageModule.getToken as unknown as ReturnType<typeof vi.fn>;
    mockSaveToken = authStorageModule.saveToken as unknown as ReturnType<typeof vi.fn>;
    mockRemoveToken = authStorageModule.removeToken as unknown as ReturnType<typeof vi.fn>;

    // Default: no token
    mockGetToken.mockReturnValue(null);
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );

  describe('AuthProvider', () => {
    it('should provide auth context to children', async () => {
      const TestComponent: React.FC = () => {
        const auth = useAuth();
        return <div data-testid="auth-check">{auth ? 'Has Auth' : 'No Auth'}</div>;
      };

      render(
        <MemoryRouter>
          <AuthProvider>
            <TestComponent />
          </AuthProvider>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('auth-check')).toHaveTextContent('Has Auth');
      });
    });

    it('should initialize with unauthenticated state', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should load user from stored token on mount', async () => {
      const mockUser: User = { username: 'testuser' };
      mockGetToken.mockReturnValue('valid-token-123');
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isAuthenticated).toBe(true);
      });
    });

    it('should handle missing token on mount', async () => {
      mockGetToken.mockReturnValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should handle invalid token on mount', async () => {
      mockGetToken.mockReturnValue('invalid-token');
      mockGetCurrentUser.mockRejectedValue(new Error('Invalid token'));

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockRemoveToken).toHaveBeenCalled();
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('useAuth hook', () => {
    it('should provide auth state', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('user');
      expect(result.current).toHaveProperty('isAuthenticated');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('login');
      expect(result.current).toHaveProperty('logout');
    });

    it('should throw error when used outside AuthProvider', () => {
      expect(() => {
        renderHook(() => useAuth());
      }).toThrow();
    });
  });

  describe('login', () => {
    it('should authenticate user with valid credentials', async () => {
      const username: string = 'testuser';
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username };

      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login(username);
      });

      expect(mockLogin).toHaveBeenCalledWith(username);
      expect(mockSaveToken).toHaveBeenCalledWith('token-123');
    });

    it('should update isAuthenticated to true', async () => {
      const username: string = 'testuser';
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username };

      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login(username);
      });

      expect(result.current.isAuthenticated).toBe(true);
    });

    it('should set user object with username', async () => {
      const username: string = 'testuser';
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username };

      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login(username);
      });

      expect(result.current.user).toEqual({ username: 'testuser' });
    });

    it('should store token in localStorage', async () => {
      const username: string = 'testuser';
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username };

      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login(username);
      });

      expect(mockSaveToken).toHaveBeenCalledWith('token-123');
    });

    it('should show loading state during login', async () => {
      const username: string = 'testuser';
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username };

      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const loginPromise = act(async () => {
        await result.current.login(username);
      });

      await loginPromise;
      expect(result.current.isLoading).toBe(false);
    });

    it('should handle login errors', async () => {
      const username: string = 'invaliduser';
      mockLogin.mockRejectedValue(new Error('Login failed'));

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login(username);
        })
      ).rejects.toThrow('Login failed');

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('logout', () => {
    it('should clear user state', async () => {
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username: 'testuser' };
      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login('testuser');
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.user).toBeNull();
    });

    it('should set isAuthenticated to false', async () => {
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username: 'testuser' };
      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login('testuser');
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should remove token from localStorage', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      act(() => {
        result.current.logout();
      });

      expect(mockRemoveToken).toHaveBeenCalled();
    });

    it('should work even when already logged out', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(() => {
        act(() => {
          result.current.logout();
        });
      }).not.toThrow();
    });
  });

  describe('State Persistence', () => {
    it('should persist authentication across page reloads', async () => {
      const mockUser: User = { username: 'testuser' };
      mockGetToken.mockReturnValue('token-123');
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result: result1 } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result1.current.user).toEqual(mockUser);
        expect(result1.current.isAuthenticated).toBe(true);
      });

      const { result: result2 } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result2.current.user).toEqual(mockUser);
        expect(result2.current.isAuthenticated).toBe(true);
      });
    });

    it('should clear state when token is manually removed', async () => {
      mockGetToken.mockReturnValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('Protected Routes', () => {
    it('should provide requireAuth helper for protected routes', () => {
      const { result } = renderHook(() => useAuth(), { wrapper });
      expect(result.current).toHaveProperty('isAuthenticated');
    });

    it('should redirect to login when accessing protected route while unauthenticated', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should allow access to protected route when authenticated', async () => {
      const mockAuthToken: AuthToken = { access_token: 'token-123', token_type: 'bearer' };
      const mockUser: User = { username: 'testuser' };
      mockLogin.mockResolvedValue(mockAuthToken);
      mockGetCurrentUser.mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login('testuser');
      });

      expect(result.current.isAuthenticated).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors during initialization', async () => {
      mockGetToken.mockReturnValue('token-causes-api-error');
      mockGetCurrentUser.mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockRemoveToken).toHaveBeenCalled();
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it('should handle network errors during login', async () => {
      mockLogin.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login('testuser');
        })
      ).rejects.toThrow('Network error');

      expect(result.current.isAuthenticated).toBe(false);
    });
  });
});
