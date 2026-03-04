/**
 * Type definitions for FastCMS SDK
 */

export interface FastCMSConfig {
  baseUrl: string;
  apiKey?: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export interface User {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  role: string;
  verified: boolean;
  created: string;
  updated: string;
}

export interface QueryOptions {
  filter?: string;
  sort?: string;
  page?: number;
  perPage?: number;
  expand?: string;
}

export interface ListResult<T> {
  items: T[];
  page: number;
  perPage: number;
  totalItems: number;
  totalPages: number;
}

export interface RealtimeEvent<T> {
  action: 'create' | 'update' | 'delete';
  record: T;
}

export type UnsubscribeFn = () => void;

export interface FileUploadOptions {
  collection?: string;
  record?: string;
  field?: string;
}

export interface FileMetadata {
  id: string;
  filename: string;
  originalFilename: string;
  mimeType: string;
  size: number;
  storagePath: string;
  collectionName?: string;
  recordId?: string;
  fieldName?: string;
  created: string;
}

export interface SearchOptions {
  limit?: number;
  offset?: number;
}

export interface SearchResult<T> {
  items: T[];
  query: string;
  count: number;
}

// ─── Error types ─────────────────────────────────────────────────────────────

export class FastCMSError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly data?: any
  ) {
    super(message);
    this.name = 'FastCMSError';
  }
}

export class AuthError extends FastCMSError {
  constructor(message: string, status?: number, data?: any) {
    super(message, status, data);
    this.name = 'AuthError';
  }
}

export class ValidationError extends FastCMSError {
  constructor(
    message: string,
    public readonly fields?: Record<string, string[]>,
    status?: number
  ) {
    super(message, status ?? 422, fields);
    this.name = 'ValidationError';
  }
}

export class NetworkError extends FastCMSError {
  constructor(message: string) {
    super(message);
    this.name = 'NetworkError';
  }
}
