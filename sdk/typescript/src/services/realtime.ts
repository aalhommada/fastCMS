/**
 * Real-time subscriptions service (SSE) with auto-reconnect.
 */
import { FastCMS } from '../client';
import { RealtimeEvent, UnsubscribeFn } from '../types';

interface SubscriptionState {
  eventSource: EventSource;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  closed: boolean;
  reconnectAttempts: number;
}

export interface SubscribeOptions {
  /** Optional filter expression (server-side) */
  filter?: string;
  /** Custom event types to listen for (default: 'message') */
  events?: string[];
  /** Max auto-reconnect attempts (default: 10, 0 = unlimited) */
  maxReconnects?: number;
  /** Initial reconnect delay in ms (doubles on each attempt, default: 1000) */
  reconnectDelay?: number;
}

export class RealtimeService {
  private subscriptions: Map<string, SubscriptionState> = new Map();

  constructor(private client: FastCMS) {}

  /**
   * Subscribe to real-time updates for a collection.
   * Auto-reconnects on connection loss with exponential backoff.
   */
  subscribe<T = any>(
    collectionName: string,
    callback: (event: RealtimeEvent<T>) => void,
    options: SubscribeOptions = {}
  ): UnsubscribeFn {
    const key = `${collectionName}-${Date.now()}-${Math.random()}`;
    const {
      filter,
      events = ['message'],
      maxReconnects = 10,
      reconnectDelay = 1000,
    } = options;

    const state: SubscriptionState = {
      eventSource: null as any,
      reconnectTimer: null,
      closed: false,
      reconnectAttempts: 0,
    };
    this.subscriptions.set(key, state);

    const connect = () => {
      if (state.closed) return;

      const tokens = this.client.getTokens();
      const baseUrl = this.client.getConfig().baseUrl;

      const params = new URLSearchParams();
      if (tokens?.accessToken) params.set('token', tokens.accessToken);
      if (filter) params.set('filter', filter);

      const url = `${baseUrl}/api/v1/realtime/${collectionName}?${params.toString()}`;
      const es = new EventSource(url);
      state.eventSource = es;

      const handleMessage = (e: MessageEvent) => {
        state.reconnectAttempts = 0; // reset on successful message
        try {
          callback(JSON.parse(e.data) as RealtimeEvent<T>);
        } catch {
          // ignore parse errors
        }
      };

      events.forEach((eventType) => {
        if (eventType === 'message') {
          es.onmessage = handleMessage;
        } else {
          es.addEventListener(eventType, handleMessage as EventListener);
        }
      });

      es.onerror = () => {
        es.close();
        if (state.closed) return;

        const canReconnect = maxReconnects === 0 || state.reconnectAttempts < maxReconnects;
        if (canReconnect) {
          const delay = reconnectDelay * Math.pow(2, Math.min(state.reconnectAttempts, 6));
          state.reconnectAttempts++;
          state.reconnectTimer = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      state.closed = true;
      if (state.reconnectTimer !== null) clearTimeout(state.reconnectTimer);
      if (state.eventSource) state.eventSource.close();
      this.subscriptions.delete(key);
    };
  }

  /**
   * Close all active subscriptions.
   */
  closeAll(): void {
    this.subscriptions.forEach((state) => {
      state.closed = true;
      if (state.reconnectTimer !== null) clearTimeout(state.reconnectTimer);
      if (state.eventSource) state.eventSource.close();
    });
    this.subscriptions.clear();
  }
}
