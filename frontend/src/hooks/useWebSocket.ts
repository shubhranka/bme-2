import { useEffect, useRef, useState, useCallback } from "react";

interface LogEntry {
  type: string;
  message: string;
  step_number?: number;
  action?: string;
  selector?: string;
  status?: string;
}

interface UseWebSocketOptions {
  onLog?: (log: LogEntry) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
}

interface UseWebSocketReturn {
  connected: boolean;
  logs: LogEntry[];
  error: string | null;
  connect: (runId: string) => void;
  disconnect: () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const runIdRef = useRef<string | null>(null);

  const connect = useCallback((runId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }

    const wsUrl = `ws://localhost:8000/api/ws/logs/${runId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as LogEntry;
        setLogs((prev) => [...prev, log]);
        if (options.onLog) {
          options.onLog(log);
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = (event) => {
      setError("WebSocket connection error");
      if (options.onError) {
        options.onError(event);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (options.onClose) {
        options.onClose();
      }
    };

    wsRef.current = ws;
    runIdRef.current = runId;
  }, [options]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
    runIdRef.current = null;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    connected,
    logs,
    error,
    connect,
    disconnect,
  };
}
