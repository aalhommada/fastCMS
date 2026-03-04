/**
 * Files service — upload, download, list, delete, and protect files.
 */
import { FastCMS } from '../client';

export interface FileRecord {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  size: number;
  storage_path: string;
  storage_type: string;
  collection_name?: string;
  record_id?: string;
  field_name?: string;
  user_id?: string;
  is_thumbnail: boolean;
  protected: boolean;
  parent_file_id?: string;
  created: string;
  updated: string;
  url?: string;
}

export interface FileListResponse {
  items: FileRecord[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface FileUploadOptions {
  collectionName?: string;
  recordId?: string;
  fieldName?: string;
}

export class FilesService {
  constructor(private client: FastCMS) {}

  /**
   * Upload a file.
   */
  async upload(file: File | Blob, options: FileUploadOptions = {}): Promise<FileRecord> {
    const form = new FormData();
    form.append('file', file);
    if (options.collectionName) form.append('collection_name', options.collectionName);
    if (options.recordId) form.append('record_id', options.recordId);
    if (options.fieldName) form.append('field_name', options.fieldName);

    const response = await this.client.getAxios().post('/api/v1/files', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  /**
   * List files with optional filters.
   */
  async list(options: {
    page?: number;
    perPage?: number;
    collectionName?: string;
    recordId?: string;
  } = {}): Promise<FileListResponse> {
    const params: Record<string, any> = {};
    if (options.page) params.page = options.page;
    if (options.perPage) params.per_page = options.perPage;
    if (options.collectionName) params.collection_name = options.collectionName;
    if (options.recordId) params.record_id = options.recordId;

    const response = await this.client.getAxios().get('/api/v1/files', { params });
    return response.data;
  }

  /**
   * Get file metadata by ID.
   */
  async getOne(fileId: string): Promise<FileRecord> {
    const response = await this.client.getAxios().get(`/api/v1/files/${fileId}`);
    return response.data;
  }

  /**
   * Build a download URL for a file.
   * Pass a thumb spec (e.g. "300x200", "300x200f") for on-demand thumbnails.
   */
  getDownloadUrl(fileId: string, thumb?: string, token?: string): string {
    const base = this.client.getConfig().baseUrl;
    let url = `${base}/api/v1/files/${fileId}/download`;
    const params: string[] = [];
    if (thumb) params.push(`thumb=${encodeURIComponent(thumb)}`);
    if (token) params.push(`token=${encodeURIComponent(token)}`);
    if (params.length) url += '?' + params.join('&');
    return url;
  }

  /**
   * Generate a short-lived access token for a protected file.
   */
  async getToken(fileId: string): Promise<{ token: string; expires_in: number }> {
    const response = await this.client.getAxios().post(`/api/v1/files/${fileId}/token`);
    return response.data;
  }

  /**
   * Set or unset the protected flag on a file.
   */
  async setProtected(fileId: string, protected_: boolean): Promise<FileRecord> {
    const response = await this.client.getAxios().patch(
      `/api/v1/files/${fileId}/protected`,
      null,
      { params: { protected: protected_ } }
    );
    return response.data;
  }

  /**
   * Delete a file.
   */
  async delete(fileId: string): Promise<void> {
    await this.client.getAxios().delete(`/api/v1/files/${fileId}`);
  }
}
