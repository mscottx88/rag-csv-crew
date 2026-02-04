/**
 * TypeScript type definitions for the RAG CSV Crew frontend
 */

// ============================================================================
// Authentication Types
// ============================================================================

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface User {
  username: string;
}

export interface LoginRequest {
  username: string;
}

// ============================================================================
// Dataset Types
// ============================================================================

export interface Dataset {
  id: string;
  filename: string;
  row_count: number;
  column_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetList {
  datasets: Dataset[];
  total: number;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface ConflictResolution {
  action: 'replace' | 'keep_both' | 'cancel';
  filename?: string;
}

// ============================================================================
// Query Types
// ============================================================================

export type QueryStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface Query {
  id: string;
  query_text: string;
  status: QueryStatus;
  created_at: string;
  updated_at: string;
  execution_time_ms?: number;
  row_count?: number;
  error_message?: string;
  result_html?: string;
  confidence_score?: number;
}

export interface QueryCreate {
  query_text: string;
  dataset_ids?: string[];
}

export interface QueryHistory {
  queries: Query[];
  total: number;
  page: number;
  page_size: number;
}

export interface QueryExample {
  id: string;
  text: string;
  description: string;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface PaginationParams {
  page?: number;
  page_size?: number;
  status?: QueryStatus;
}

// ============================================================================
// UI Component Props
// ============================================================================

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string) => Promise<void>;
  logout: () => void;
}
