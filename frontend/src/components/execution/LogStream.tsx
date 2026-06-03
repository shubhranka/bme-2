import { useState, useEffect, useRef } from "react";

interface LogEntry {
  type: string;
  message: string;
  step_number?: number;
  action?: string;
  selector?: string;
  status?: string;
  timestamp?: Date;
}

interface LogStreamProps {
  runId: string | null;
  onComplete?: () => void;
}

export function LogStream({ runId, onComplete }: LogStreamProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!runId) return;

    const wsUrl = `ws://localhost:8000/api/ws/logs/${runId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as LogEntry & { timestamp: Date };
        setLogs((prev) => [...prev, log]);

        // Auto-scroll to bottom
        if (logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }

        // Check for completion
        if (log.type === "complete" && onComplete) {
          onComplete();
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = () => {
      setError("Connection error");
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [runId, onComplete]);

  const getLogColor = (log: LogEntry) => {
    switch (log.type) {
      case "start":
        return "text-blue-600";
      case "info":
        return "text-gray-700";
      case "success":
      case "step_complete":
        return log.status === "success" ? "text-green-600" : "text-red-600";
      case "error":
      case "step_complete":
        return "text-red-600";
      case "complete":
        return "text-purple-600";
      default:
        return "text-gray-600";
    }
  };

  const getLogIcon = (log: LogEntry) => {
    switch (log.type) {
      case "start":
        return "▶";
      case "info":
        return "ℹ";
      case "success":
      case "step_complete":
        return log.status === "success" ? "✓" : "✗";
      case "error":
        return "⚠";
      case "complete":
        return "■";
      case "step_start":
        return "→";
      default:
        return "•";
    }
  };

  return (
    <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-gray-100 font-semibold">Live Logs</h4>
        <div className="flex items-center gap-2">
          {connected && (
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span className="text-green-400 text-xs">Connected</span>
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="text-red-400 mb-4 p-2 bg-red-900/30 rounded">
          {error}
        </div>
      )}

      <div
        ref={logContainerRef}
        className="space-y-1 max-h-96 overflow-y-auto"
        style={{ scrollBehavior: "smooth" }}
      >
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            {connected ? "Waiting for logs..." : "Connecting to log stream..."}
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className={`flex items-start gap-2 py-1 ${
                log.type === "error" ? "text-red-400" : getLogColor(log)
              }`}
            >
              <span className="shrink-0">{getLogIcon(log)}</span>
              <span className="flex-1 break-words">
                {log.step_number && `[Step ${log.step_number}] `}
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
