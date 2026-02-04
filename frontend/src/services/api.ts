/**
 * Axios API client with authentication interceptors
 * Centralized HTTP client for all API requests
 */

import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { getToken, removeToken } from './auth-storage';
import type { ApiError } from '../types';

// Base URL from environment variable or default
const BASE_URL: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create Axios instance with default configuration
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor: Add Bearer token to all requests
 */
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const token: string | null = getToken();

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error: AxiosError): Promise<AxiosError> => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor: Handle common errors
 */
api.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => {
    return response;
  },
  (error: AxiosError<ApiError>): Promise<AxiosError> => {
    if (error.response) {
      const status: number = error.response.status;

      switch (status) {
        case 401:
          // Unauthorized: Remove token and redirect to login
          removeToken();
          window.location.href = '/login';
          break;

        case 403:
          // Forbidden: User doesn't have permission
          console.error('Access forbidden:', error.response.data?.detail);
          break;

        case 500:
          // Internal Server Error
          console.error('Server error:', error.response.data?.detail);
          break;

        default:
          // Other errors
          console.error('API error:', error.response.data?.detail);
      }
    } else if (error.request) {
      // Network error: No response received
      console.error('Network error: No response from server');
    } else {
      // Other errors
      console.error('Request error:', error.message);
    }

    return Promise.reject(error);
  }
);

export default api;
