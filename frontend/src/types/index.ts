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
  uploaded_at: string;
}

export interface DatasetList {
  datasets: Dataset[];
  total_count: number;
  page: number;
  page_size: number;
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

export interface QueryResponse {
  query_id: string;
  id: string;
  html_content: string;
  plain_text: string;
  confidence_score: number;
  generated_at: string;
  data_snapshot?: unknown;
}

export interface TimelineEntry {
  elapsed_ms: number;
  message: string;
}

export interface Query {
  id: string;
  query_text: string;
  status: QueryStatus;
  dataset_ids?: string[];
  submitted_at: string;
  completed_at?: string;
  execution_time_ms?: number;
  result_count?: number;
  error_message?: string;
  generated_sql?: string | null;
  response?: QueryResponse;
  progress_message?: string | null;
  progress_timeline?: TimelineEntry[] | null;
  agent_logs?: string | null;
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
// Dataset Inspector Types
// ============================================================================

export interface DatasetRowsResponse {
  dataset_id: string;
  table_name: string;
  columns: string[];
  column_types: Record<string, string>;
  rows: (string | number | boolean | null)[][];
  total_row_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
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
