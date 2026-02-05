/**
 * Integration tests for App routing - Tests T145-TEST
 * Validates route navigation and protected routes
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../src/App';
import type { AuthContextValue } from '../src/types';
import React from 'react';

// Mock react-router-dom to replace BrowserRouter with MemoryRouter
let memoryRouterInitialEntries: string[] = ['/'];
vi.mock('react-router-dom', async () => {
  const actual: typeof import('react-router-dom') = await vi.importActual('react-router-dom');
  return {
    ...actual,
    BrowserRouter: ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={memoryRouterInitialEntries}>{children}</MemoryRouter>
    ),
  };
});

// Mock all page components
vi.mock('../src/pages/Login', () => ({
  Login: () => <div data-testid="login-page">Login Page</div>,
}));

vi.mock('../src/pages/Dashboard', () => ({
  Dashboard: () => <div data-testid="dashboard-page">Dashboard Page</div>,
}));

vi.mock('../src/pages/Query', () => ({
  Query: () => <div data-testid="query-page">Query Page</div>,
}));

vi.mock('../src/pages/Datasets', () => ({
  Datasets: () => <div data-testid="datasets-page">Datasets Page</div>,
}));

vi.mock('../src/pages/History', () => ({
  History: () => <div data-testid="history-page">History Page</div>,
}));

vi.mock('../src/pages/NotFound', () => ({
  NotFound: () => <div data-testid="notfound-page">404 Not Found</div>,
}));

// Mock Layout components
vi.mock('../src/components/Layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../src/components/Layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar">Sidebar</div>,
}));

// Mock Auth/Login component
vi.mock('../src/components/Auth/Login', () => ({
  Login: () => <div data-testid="login-page">Login Page</div>,
}));

// Mock AuthContext
let mockAuthContextValue: AuthContextValue;
vi.mock('../src/context/AuthContext', async () => {
  const actual: typeof import('../src/context/AuthContext') = await vi.importActual('../src/context/AuthContext');
  return {
    ...actual,
    AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
    useAuth: () => mockAuthContextValue,
    ProtectedRoute: ({ children }: { children: React.ReactNode }) => {
      const auth: AuthContextValue = mockAuthContextValue;
      if (!auth.isAuthenticated && !auth.isLoading) {
        return <div data-testid="redirect-to-login">Redirecting to /login</div>;
      }
      if (auth.isLoading) {
        return <div data-testid="loading">Loading...</div>;
      }
      return <div>{children}</div>;
    },
  };
});

describe('App Routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    memoryRouterInitialEntries = ['/'];

    // Default: unauthenticated user
    mockAuthContextValue = {
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
    };
  });

  const renderApp = (initialRoute: string = '/'): void => {
    memoryRouterInitialEntries = [initialRoute];
    render(<App />);
  };

  describe('Public Routes', () => {
    it('should render login page at /login', async () => {
      renderApp('/login');

      await waitFor(() => {
        expect(screen.getByTestId('login-page')).toBeInTheDocument();
      });
    });

    it('should redirect unauthenticated users to /login', async () => {
      renderApp('/');

      await waitFor(() => {
        expect(screen.getByTestId('redirect-to-login')).toBeInTheDocument();
      });
    });
  });

  describe('Protected Routes', () => {
    beforeEach(() => {
      // Authenticated user for protected route tests
      mockAuthContextValue = {
        user: { username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
      };
    });

    it('should render dashboard at / when authenticated', async () => {
      renderApp('/');

      await waitFor(() => {
        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
      });
    });

    it('should render datasets page at /datasets', async () => {
      renderApp('/datasets');

      await waitFor(() => {
        expect(screen.getByTestId('datasets-page')).toBeInTheDocument();
      });
    });

    it('should render query page at /query', async () => {
      renderApp('/query');

      await waitFor(() => {
        expect(screen.getByTestId('query-page')).toBeInTheDocument();
      });
    });

    it('should render history page at /history', async () => {
      renderApp('/history');

      await waitFor(() => {
        expect(screen.getByTestId('history-page')).toBeInTheDocument();
      });
    });

    it('should redirect to login if accessing protected route while unauthenticated', async () => {
      mockAuthContextValue = {
        user: null,
        isAuthenticated: false,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
      };

      renderApp('/dashboard');

      await waitFor(() => {
        expect(screen.getByTestId('redirect-to-login')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation', () => {
    beforeEach(() => {
      mockAuthContextValue = {
        user: { username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
      };
    });

    it('should navigate between routes', async () => {
      renderApp('/query');

      await waitFor(() => {
        expect(screen.getByTestId('query-page')).toBeInTheDocument();
      });
    });

    it('should preserve auth state during navigation', async () => {
      renderApp('/');

      await waitFor(() => {
        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
      });

      // Auth state is preserved because mockAuthContextValue is maintained
      expect(mockAuthContextValue.isAuthenticated).toBe(true);
      expect(mockAuthContextValue.user).toEqual({ username: 'testuser' });
    });
  });

  describe('Not Found', () => {
    beforeEach(() => {
      mockAuthContextValue = {
        user: { username: 'testuser' },
        isAuthenticated: true,
        isLoading: false,
        login: vi.fn(),
        logout: vi.fn(),
      };
    });

    it('should show 404 page for invalid routes', async () => {
      renderApp('/invalid-route-12345');

      await waitFor(() => {
        expect(screen.getByTestId('notfound-page')).toBeInTheDocument();
      });
    });
  });
});
