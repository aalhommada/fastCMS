/**
 * Batch operations service — multi-record create/upsert/delete in a single request.
 */
import { FastCMS } from '../client';

export interface BatchRequest {
  method: 'POST' | 'PATCH' | 'DELETE';
  url: string;
  body?: Record<string, any>;
}

export interface BatchResponse {
  results: Array<{
    status: number;
    body: any;
  }>;
}

export class BatchService {
  constructor(private client: FastCMS) {}

  /**
   * Execute a raw batch of HTTP requests in a single round-trip.
   */
  async execute(requests: BatchRequest[]): Promise<BatchResponse> {
    const response = await this.client.getAxios().post('/api/v1/batch', { requests });
    return response.data;
  }

  /**
   * Create multiple records in a collection at once.
   */
  async createMany<T = any>(collectionName: string, records: Partial<T>[]): Promise<T[]> {
    const response = await this.client.getAxios().post(
      `/api/v1/${collectionName}/records/batch`,
      { records }
    );
    return response.data.records ?? response.data;
  }

  /**
   * Upsert multiple records (insert or update based on unique fields).
   * @param collectionName  Target collection
   * @param records         Records to upsert
   * @param upsertBy        Field(s) used to match existing records (default: ["id"])
   */
  async upsertMany<T = any>(
    collectionName: string,
    records: Partial<T>[],
    upsertBy: string[] = ['id']
  ): Promise<{ created: T[]; updated: T[] }> {
    const response = await this.client.getAxios().post(
      `/api/v1/${collectionName}/records/batch-upsert`,
      { records, upsert_by: upsertBy }
    );
    return response.data;
  }

  /**
   * Delete multiple records by ID in a single request.
   */
  async deleteMany(collectionName: string, ids: string[]): Promise<{ deleted: number }> {
    const response = await this.client.getAxios().delete(
      `/api/v1/${collectionName}/records/batch`,
      { data: { ids } }
    );
    return response.data;
  }
}
