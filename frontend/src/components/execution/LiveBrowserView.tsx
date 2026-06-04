import { useState, useEffect, useRef } from "react";

interface LiveBrowserViewProps {
  runId: string | null;
  onComplete?: () => void;
  isComplete: boolean;
}

export function LiveBrowserView({ runId, onComplete, isComplete }: LiveBrowserViewProps) {
  const [currentView, setCurrentView] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId || isComplete) return;

    const wsUrl = `ws://localhost:8000/api/ws/logs/${runId}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data);
        console.log("LiveBrowserView received:", log);

        // Listen for page_view events
        if (log.type === "page_view") {
          console.log("Setting current view to:", log.image_path);
          setCurrentView(log.image_path);
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
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [runId, isComplete, onComplete]);

  // Hide if complete (will show screenshot timeline instead)
  if (isComplete) {
    return null;
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-gray-100 font-semibold">Live Browser View</h4>
        {connected && (
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-green-400 text-xs">Live</span>
          </span>
        )}
      </div>

      <div className="relative bg-gray-800 rounded-lg overflow-hidden" style={{ minHeight: "400px" }}>
        {currentView ? (
          <img
            src={currentView}
            alt="Live browser view"
            className="w-full"
            style={{ minHeight: "400px", objectFit: "contain" }}
          />
        ) : (
          <div className="flex items-center justify-center h-96">
            <div className="text-center">
              {connected ? (
                <>
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
                  <p className="text-gray-400">Launching browser...</p>
                </>
              ) : (
                <p className="text-gray-500">Connecting...</p>
              )}
            </div>
          </div>
        )}
      </div>
      <p className="text-gray-500 text-xs mt-2 text-center">
        Real-time view of the browser during test execution
      </p>
    </div>
  );
}
