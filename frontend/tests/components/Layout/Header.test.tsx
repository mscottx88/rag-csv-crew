/**
 * Component tests for Header - Tests T143-TEST
 * Validates username display and logout functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Header } from '../../../src/components/Layout/Header';
import type { AuthContextValue } from '../../../src/types';

// Mock the AuthContext
vi.mock('../../../src/context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('Header Component', () => {
  let mockLogout: ReturnType<typeof vi.fn>;
  let mockUseAuth: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.clearAllMocks();
    mockLogout = vi.fn();

    const authContextModule: typeof import('../../../src/context/AuthContext') = await import('../../../src/context/AuthContext');
    mockUseAuth = authContextModule.useAuth as unknown as ReturnType<typeof vi.fn>;

    // Default: authenticated user
    mockUseAuth.mockReturnValue({
      user: { username: 'testuser' },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: mockLogout,
    } as AuthContextValue);
  });

  it('should display application title', () => {
    render(<Header />);

    const title: HTMLElement = screen.getByRole('heading', { name: /rag csv crew/i });
    expect(title).toBeInTheDocument();
  });

  it('should display logged-in username', () => {
    render(<Header />);

    const username: HTMLElement = screen.getByText(/welcome, testuser/i);
    expect(username).toBeInTheDocument();
  });

  it('should show logout button', () => {
    render(<Header />);

    const logoutButton: HTMLElement = screen.getByRole('button', { name: /logout/i });
    expect(logoutButton).toBeInTheDocument();
  });

  it('should call logout when button is clicked', async () => {
    const user: ReturnType<typeof userEvent.setup> = userEvent.setup();
    render(<Header />);

    const logoutButton: HTMLElement = screen.getByRole('button', { name: /logout/i });
    await user.click(logoutButton);

    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it('should not display user info when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: mockLogout,
    } as AuthContextValue);

    render(<Header />);

    const usernameText: HTMLElement | null = screen.queryByText(/welcome/i);
    expect(usernameText).not.toBeInTheDocument();

    const logoutButton: HTMLElement | null = screen.queryByRole('button', { name: /logout/i });
    expect(logoutButton).not.toBeInTheDocument();
  });
});
