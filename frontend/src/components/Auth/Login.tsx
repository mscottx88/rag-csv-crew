/**
 * Login Component
 * Username-only login form per FR-021 (no password required)
 */

import React, { useState, FormEvent, ChangeEvent } from 'react';
import { useAuth } from '../../context/AuthContext';
import './Login.css';

export const Login: React.FC = () => {
  const [username, setUsername] = useState<string>('');
  const [error, setError] = useState<string>('');
  const { login, isLoading } = useAuth();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError('');

    if (!username.trim()) {
      setError('Username is required');
      return;
    }

    try {
      await login(username.trim());
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Login failed. Please try again.');
      }
    }
  };

  const handleUsernameChange = (e: ChangeEvent<HTMLInputElement>): void => {
    setUsername(e.target.value);
    setError(''); // Clear error when user types
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter') {
      e.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>RAG CSV Crew</h1>
        <h2>Login</h2>

        <form onSubmit={(e) => void handleSubmit(e)} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={handleUsernameChange}
              onKeyPress={handleKeyPress}
              placeholder="Enter your username"
              disabled={isLoading}
              autoFocus
              aria-label="Username"
              aria-required="true"
              aria-invalid={!!error}
            />
          </div>

          {error && (
            <div className="error-message" role="alert">
              {error}
            </div>
          )}

          <button type="submit" disabled={isLoading || !username.trim()} className="login-button">
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="login-help">
          No password required. Just enter your username to continue.
        </p>
      </div>
    </div>
  );
};
