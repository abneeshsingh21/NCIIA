/**
 * N-CIIA Dashboard — Singleton WebSocket Manager
 *
 * Provides a single, shared WebSocket connection to the nciia-core backend.
 * Features:
 *  - Exponential backoff reconnection (max 30 s)
 *  - Typed topic-based pub/sub so any component can subscribe to events
 *    without knowing about the underlying socket
 *  - Heartbeat / ping-pong detection (server sends heartbeats every 30 s)
 *
 * Usage:
 *   import { wsManager } from './websocket';
 *   const unsub = wsManager.subscribe('threat_update', handler);
 *   // later: unsub();
 */

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type WsEventType =
  | 'connected'
  | 'heartbeat'
  | 'signal_detected'
  | 'threat_update'
  | 'persona_activity'
  | 'error'
  | 'pong'
  | 'subscribed'
  | 'ack'
  | string;   // allow extension

export interface WsMessage {
  type: WsEventType;
  timestamp?: string;
  data?: unknown;
  [key: string]: unknown;
}

export type WsHandler = (msg: WsMessage) => void;

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

type StatusListener = (status: ConnectionStatus) => void;

// ─────────────────────────────────────────────────────────────────────────────
// Manager
// ─────────────────────────────────────────────────────────────────────────────

class WebSocketManager {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, Set<WsHandler>>();
  private statusListeners = new Set<StatusListener>();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;
  private _status: ConnectionStatus = 'disconnected';

  private readonly WS_URL =
    import.meta.env.VITE_WS_URL ?? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;

  // ── Status ──────────────────────────────────────────────────────────────

  get status(): ConnectionStatus {
    return this._status;
  }

  private setStatus(s: ConnectionStatus): void {
    this._status = s;
    this.statusListeners.forEach((l) => l(s));
  }

  onStatusChange(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    // Immediately emit current status
    listener(this._status);
    return () => this.statusListeners.delete(listener);
  }

  // ── Connection ───────────────────────────────────────────────────────────

  connect(): void {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.shouldReconnect = true;
    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(`${this.WS_URL}/ws/live`);

      this.ws.onopen = () => {
        this.reconnectAttempt = 0;
        this.setStatus('connected');
        // Send subscribe message for all topics
        this.send({ type: 'subscribe', topics: ['threat_update', 'signal_detected', 'persona_activity'] });
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WsMessage = JSON.parse(event.data as string);
          this.dispatch(msg);
        } catch {
          // ignore malformed frames
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (this.shouldReconnect) {
          this.scheduleReconnect();
        } else {
          this.setStatus('disconnected');
        }
      };

      this.ws.onerror = () => {
        this.setStatus('error');
        this.ws?.close();
      };
    } catch {
      this.setStatus('error');
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.setStatus('disconnected');
  }

  private scheduleReconnect(): void {
    this.setStatus('disconnected');
    this.reconnectAttempt += 1;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempt, 30_000);
    this.reconnectTimer = setTimeout(() => {
      if (this.shouldReconnect) this.connect();
    }, delay);
  }

  // ── Messaging ────────────────────────────────────────────────────────────

  send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private dispatch(msg: WsMessage): void {
    // Dispatch to wildcard handlers
    this.handlers.get('*')?.forEach((h) => h(msg));
    // Dispatch to topic-specific handlers
    if (msg.type) {
      this.handlers.get(msg.type)?.forEach((h) => h(msg));
    }
  }

  // ── Pub/Sub ──────────────────────────────────────────────────────────────

  /**
   * Subscribe to a specific WS event type (or '*' for all events).
   * Returns an unsubscribe function.
   */
  subscribe(topic: string, handler: WsHandler): () => void {
    if (!this.handlers.has(topic)) {
      this.handlers.set(topic, new Set());
    }
    this.handlers.get(topic)!.add(handler);
    return () => this.handlers.get(topic)?.delete(handler);
  }
}

// Export singleton
export const wsManager = new WebSocketManager();
