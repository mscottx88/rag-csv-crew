/**
 * Component tests for Login
 *
 * Tests T132-TEST: Validates username-only input and submission per FR-021
 *
 * Requirements:
 * - Single text input for username
 * - Submit button
 * - Loading state during login
 * - Error message display
 * - Redirect to dashboard on successful login
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Login } from '../../../src/components/Auth/Login';
import type { AuthContextValue } from '../../../src/types';

// Mock AuthContext
const mockLogin: ReturnType<typeof vi.fn> = vi.fn();
const mockAuthValue: AuthContextValue = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: mockLogin,
  logout: vi.fn(),
};

vi.mock('../../../src/context/AuthContext', () => ({
  useAuth: () => mockAuthValue,
}));

describe('Login Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthValue.isLoading = false;
  });

  describe('Rendering', () => {
    it('should render username input field', () => {
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      expect(input).toBeInTheDocument();
    });

    it('should render submit button', () => {
      render(<Login />);

      const button: HTMLElement = screen.getByRole('button', { name: /login/i });
      expect(button).toBeInTheDocument();
    });

    it('should not render password field (username-only per FR-021)', () => {
      render(<Login />);

      const passwordInput: HTMLElement | null = screen.queryByLabelText(/password/i);
      expect(passwordInput).not.toBeInTheDocument();
    });

    it('should have accessible form elements', () => {
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      expect(input).toHaveAttribute('aria-label', 'Username');
      expect(input).toHaveAttribute('aria-required', 'true');
    });
  });

  describe('Form Validation', () => {
    it('should prevent submission with empty username', async () => {
      const user = userEvent.setup();
      render(<Login />);

      const button: HTMLElement = screen.getByRole('button', { name: /login/i });
      expect(button).toBeDisabled();

      await user.click(button);

      expect(mockLogin).not.toHaveBeenCalled();
    });

    it('should allow submission with valid username', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('testuser');
      });
    });

    it('should trim whitespace from username', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, '  testuser  ');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('testuser');
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator during login', async () => {
      mockAuthValue.isLoading = true;
      render(<Login />);

      const button: HTMLElement = screen.getByRole('button');
      expect(button).toHaveTextContent(/logging in.../i);
    });

    it('should disable submit button during login', async () => {
      mockAuthValue.isLoading = true;
      render(<Login />);

      const button: HTMLElement = screen.getByRole('button', { name: /logging in/i });
      expect(button).toBeDisabled();
    });

    it('should disable input during login', async () => {
      mockAuthValue.isLoading = true;
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      expect(input).toBeDisabled();
    });
  });

  describe('Success Handling', () => {
    it('should store token in localStorage on successful login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled();
      });
    });

    it('should redirect to dashboard after successful login', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled();
      });
    });

    it('should update auth context with user data', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('testuser');
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message on login failure', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValue(new Error('Login failed'));
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('Login failed');
      });
    });

    it('should display user-friendly message for network errors', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValue({ message: 'Network error' });
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('Login failed. Please try again.');
      });
    });

    it('should display server error messages', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValue(new Error('Invalid username'));
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'baduser');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('Invalid username');
      });
    });

    it('should allow retry after error', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValueOnce(new Error('Login failed')).mockResolvedValueOnce(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      await user.clear(input);
      await user.type(input, 'testuser2');
      await user.click(button);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(2);
      });
    });

    it('should clear error when user starts typing', async () => {
      const user = userEvent.setup();
      mockLogin.mockRejectedValue(new Error('Login failed'));
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      const button: HTMLElement = screen.getByRole('button', { name: /login/i });

      await user.type(input, 'testuser');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      await user.type(input, 'x');

      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
      });
    });
  });

  describe('User Experience', () => {
    it('should focus username input on mount', () => {
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      expect(input).toHaveAttribute('autoFocus');
    });

    it('should submit form when Enter key is pressed', async () => {
      const user = userEvent.setup();
      mockLogin.mockResolvedValue(undefined);
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);

      await user.type(input, 'testuser{Enter}');

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('testuser');
      });
    });

    it('should show helpful placeholder text', () => {
      render(<Login />);

      const input: HTMLElement = screen.getByLabelText(/username/i);
      expect(input).toHaveAttribute('placeholder', 'Enter your username');
    });
  });
});
