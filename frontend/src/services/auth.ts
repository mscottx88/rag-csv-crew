/**
 * Authentication API service
 * Handles login and user management operations
 */

import api from './api';
import type { AuthToken, User, LoginRequest } from '../types';
import { AxiosResponse, AxiosError } from 'axios';

/**
 * Login with username (no password required per FR-021)
 * @param username User's username
 * @returns AuthToken with access_token and token_type
 * @throws {Error} If username is empty or login fails
 */
export const login = async (username: string): Promise<AuthToken> => {
  if (!username || username.trim() === '') {
    throw new Error('Username is required');
  }

  try {
    const request: LoginRequest = { username: username.trim() };
    const response: AxiosResponse<AuthToken> = await api.post<AuthToken>('/auth/login', request);
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 400) {
        throw new Error(detail || 'Invalid username');
      } else if (status === 500) {
        throw new Error('Server error. Please try again later.');
      } else {
        throw new Error(detail || 'Login failed. Please try again.');
      }
    }
    throw error;
  }
};

/**
 * Get current authenticated user
 * @returns User object with username
 * @throws {Error} If not authenticated or request fails
 */
export const getCurrentUser = async (): Promise<User> => {
  try {
    const response: AxiosResponse<User> = await api.get<User>('/auth/me');
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const status: number | undefined = error.response?.status;
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

      if (status === 401) {
        throw new Error('Not authenticated. Please login.');
      } else if (status === 500) {
        throw new Error('Server error. Please try again later.');
      } else {
        throw new Error(detail || 'Failed to get user information.');
      }
    }
    throw error;
  }
};
