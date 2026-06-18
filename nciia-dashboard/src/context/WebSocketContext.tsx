/**
 * WebSocket React Context
 *
 * Wraps the singleton wsManager, initialises the connection once at app
 * startup, and exposes a typed hook for any component to use.
 *
 * Usage:
 *   const { status, subscribe } = useWebSocket();
 *   useEffect(() => subscribe('threat_update', handler), []);
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react';

import { wsManager, type ConnectionStatus, type WsHandler, type WsMessage } from '../lib/websocket';

// ─────────────────────────────────────────────────────────────────────────────
// Context shape
// ─────────────────────────────────────────────────────────────────────────────

interface WebSocketContextValue {
  /** Current connection status of the singleton WS connection. */
  status: ConnectionStatus;
  /** Subscribe to a WS event type. Returns an unsubscribe function. */
  subscribe: (topic: string, handler: WsHandler) => () => void;
  /** Send a raw message to the server (fire-and-forget). */
  send: (msg: Record<string, unknown>) => void;
  /** Last message received (any topic). */
  lastMessage: WsMessage | null;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>(wsManager.status);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);

  useEffect(() => {
    // Start the single connection
    wsManager.connect();

    // Track status changes
    const unsubStatus = wsManager.onStatusChange(setStatus);

    // Track all incoming messages for lastMessage
    const unsubMsg = wsManager.subscribe('*', setLastMessage);

    return () => {
      unsubStatus();
      unsubMsg();
      // Do NOT disconnect here — the manager outlives individual renders.
      // Disconnect only when the entire app unmounts.
    };
  }, []);

  const subscribe = useCallback(
    (topic: string, handler: WsHandler) => wsManager.subscribe(topic, handler),
    [],
  );

  const send = useCallback(
    (msg: Record<string, unknown>) => wsManager.send(msg),
    [],
  );

  return (
    <WebSocketContext.Provider value={{ status, subscribe, send, lastMessage }}>
      {children}
    </WebSocketContext.Provider>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook
// ─────────────────────────────────────────────────────────────────────────────

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error('useWebSocket must be used inside <WebSocketProvider>');
  }
  return ctx;
}
