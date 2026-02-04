/**
 * Authentication Context
 * Provides global authentication state and actions throughout the app
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import * as authService from '../services/auth';
import * as authStorage from '../services/auth-storage';
import type { User, AuthContextValue } from '../types';

// Create context with undefined default (will throw error if used outside provider)
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * AuthProvider component
 * Wraps the app to provide authentication state and actions
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const navigate = useNavigate();

  /**
   * Load user from stored token on mount
   */
  useEffect(() => {
    const loadUser = async (): Promise<void> => {
      const token: string | null = authStorage.getToken();

      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser: User = await authService.getCurrentUser();
        setUser(currentUser);
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Failed to load user from token:', error);
        authStorage.removeToken();
        setUser(null);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    void loadUser();
  }, []);

  /**
   * Login with username
   * @param username User's username
   */
  const login = async (username: string): Promise<void> => {
    setIsLoading(true);

    try {
      const authToken = await authService.login(username);
      authStorage.saveToken(authToken.access_token);

      const currentUser: User = await authService.getCurrentUser();
      setUser(currentUser);
      setIsAuthenticated(true);

      // Redirect to dashboard after successful login
      navigate('/');
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout and clear authentication state
   */
  const logout = (): void => {
    authStorage.removeToken();
    setUser(null);
    setIsAuthenticated(false);

    // Redirect to login page
    navigate('/login');
  };

  const value: AuthContextValue = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * useAuth hook
 * Access authentication state and actions from any component
 * @throws {Error} If used outside AuthProvider
 */
export const useAuth = (): AuthContextValue => {
  const context: AuthContextValue | undefined = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
};

/**
 * ProtectedRoute component
 * Redirects to login if user is not authenticated
 */
interface ProtectedRouteProps {
  children: ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, isLoading, navigate]);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
};
