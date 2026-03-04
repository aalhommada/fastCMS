/**
 * Main FastCMS client
 */
import axios, { AxiosInstance } from 'axios';
import { FastCMSConfig, AuthTokens } from './types';
import { AuthService } from './services/auth';
import { CollectionClient } from './services/collection';
import { FilesService } from './services/files';
import { StorageService } from './services/storage';
import { SearchService } from './services/search';
import { RealtimeService } from './services/realtime';
import { BatchService } from './services/batch';

export class FastCMS {
  private axiosInstance: AxiosInstance;
  private _tokens: AuthTokens | null = null;

  public auth: AuthService;
  public files: FilesService;
  public storage: StorageService;
  public search: SearchService;
  public realtime: RealtimeService;
  public batch: BatchService;

  constructor(private config: FastCMSConfig) {
    this.axiosInstance = axios.create({
      baseURL: config.baseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include auth token
    this.axiosInstance.interceptors.request.use((config) => {
      if (this._tokens?.accessToken) {
        config.headers.Authorization = `Bearer ${this._tokens.accessToken}`;
      } else if (this.config.apiKey) {
        config.headers['X-API-Key'] = this.config.apiKey;
      }
      return config;
    });

    // Add response interceptor to handle token refresh
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // If 401 and we have a refresh token, try to refresh
        if (error.response?.status === 401 && this._tokens?.refreshToken && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const response = await axios.post(
              `${this.config.baseUrl}/api/v1/auth/refresh`,
              { refresh_token: this._tokens.refreshToken }
            );

            this._tokens = {
              accessToken: response.data.access_token,
              refreshToken: response.data.refresh_token,
            };

            originalRequest.headers.Authorization = `Bearer ${this._tokens.accessToken}`;
            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            this._tokens = null;
            throw refreshError;
          }
        }

        throw error;
      }
    );

    this.auth = new AuthService(this);
    this.files = new FilesService(this);
    this.storage = new StorageService(this);
    this.search = new SearchService(this);
    this.realtime = new RealtimeService(this);
    this.batch = new BatchService(this);
  }

  /**
   * Get a type-safe collection client
   */
  collection<T = any>(name: string): CollectionClient<T> {
    return new CollectionClient<T>(this, name);
  }

  /**
   * Get axios instance for custom requests
   */
  getAxios(): AxiosInstance {
    return this.axiosInstance;
  }

  /**
   * Get client configuration
   */
  getConfig(): FastCMSConfig {
    return this.config;
  }

  /**
   * Set authentication tokens
   */
  setTokens(tokens: AuthTokens): void {
    this._tokens = tokens;
  }

  /**
   * Get current tokens
   */
  getTokens(): AuthTokens | null {
    return this._tokens;
  }

  /**
   * Clear authentication
   */
  clearAuth(): void {
    this._tokens = null;
  }
}
