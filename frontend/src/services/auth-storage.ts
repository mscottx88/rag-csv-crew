/**
 * JWT token storage utilities
 * Handles localStorage operations for authentication tokens
 */

const TOKEN_KEY = 'auth_token';

/**
 * Save JWT token to localStorage
 * @throws {Error} If token is empty or invalid
 */
export const saveToken = (token: string): void => {
  if (!token || token.trim() === '') {
    throw new Error('Token cannot be empty');
  }
  localStorage.setItem(TOKEN_KEY, token);
};

/**
 * Retrieve JWT token from localStorage
 * @returns Token string or null if not found/expired
 */
export const getToken = (): string | null => {
  const token: string | null = localStorage.getItem(TOKEN_KEY);

  if (!token) {
    return null;
  }

  // Optional: Check if token is expired
  if (isTokenExpired(token)) {
    removeToken();
    return null;
  }

  return token;
};

/**
 * Remove JWT token from localStorage
 */
export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

/**
 * Check if a valid token exists in localStorage
 * @returns True if authenticated with valid token
 */
export const isAuthenticated = (): boolean => {
  const token: string | null = getToken();
  return token !== null && token.trim() !== '';
};

/**
 * Parse JWT token payload (without verification)
 * @param token JWT token string
 * @returns Decoded payload or null if invalid
 */
export const parseJwtPayload = (token: string): Record<string, unknown> | null => {
  try {
    const parts: string[] = token.split('.');
    if (parts.length !== 3) {
      return null;
    }

    const payload: string = parts[1]!; // Safe: we checked length === 3
    const decoded: string = atob(payload);
    const parsed: Record<string, unknown> = JSON.parse(decoded);
    return parsed;
  } catch (error) {
    console.error('Failed to parse JWT token:', error);
    return null;
  }
};

/**
 * Extract username from JWT token
 * @param token JWT token string
 * @returns Username or null if not found
 */
export const getUsernameFromToken = (token: string): string | null => {
  const payload: Record<string, unknown> | null = parseJwtPayload(token);
  if (!payload) {
    return null;
  }

  // Check common JWT claims for username
  const username: unknown = payload.sub || payload.username || payload.user;
  return typeof username === 'string' ? username : null;
};

/**
 * Extract expiration timestamp from JWT token
 * @param token JWT token string
 * @returns Expiration timestamp (seconds since epoch) or null
 */
export const getExpirationFromToken = (token: string): number | null => {
  const payload: Record<string, unknown> | null = parseJwtPayload(token);
  if (!payload) {
    return null;
  }

  const exp: unknown = payload.exp;
  return typeof exp === 'number' ? exp : null;
};

/**
 * Check if JWT token is expired
 * @param token JWT token string
 * @returns True if token is expired
 */
export const isTokenExpired = (token: string): boolean => {
  const exp: number | null = getExpirationFromToken(token);
  if (exp === null) {
    return false; // If no expiration, assume valid
  }

  const now: number = Math.floor(Date.now() / 1000); // Current time in seconds
  return now >= exp;
};
