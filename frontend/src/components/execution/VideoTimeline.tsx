import { useState, useEffect, useRef } from "react";

interface Screenshot {
  id: string;
  image_path: string;
  timestamp: string;
  description: string | null;
  step_index: number;
}

interface VideoTimelineProps {
  runId: string | null;
  screenshots?: Screenshot[];
  onScreenshotClick?: (screenshot: Screenshot) => void;
}

export function VideoTimeline({ runId, screenshots: initialScreenshots = [], onScreenshotClick }: VideoTimelineProps) {
  const [selectedScreenshot, setSelectedScreenshot] = useState<Screenshot | null>(null);
  const [screenshots, setScreenshots] = useState<Screenshot[]>(initialScreenshots);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const processedScreenshotIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!runId) return;

    // Fetch initial screenshots from database
    const fetchInitialScreenshots = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/runs/${runId}/screenshots`, {
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          const sorted = data.sort((a: Screenshot, b: Screenshot) => a.step_index - b.step_index);
          setScreenshots(sorted);
          sorted.forEach((s: Screenshot) => processedScreenshotIds.current.add(s.image_path));
        }
      } catch (err) {
        console.error("Failed to fetch screenshots:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchInitialScreenshots();

    // Connect to WebSocket for real-time screenshot updates
    const wsUrl = `ws://localhost:8000/api/ws/logs/${runId}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data);
        console.log("WebSocket message received:", log);

        // Listen for screenshot events
        if (log.type === "screenshot") {
          console.log("Received screenshot via WebSocket:", log);

          // Avoid adding duplicates
          if (!processedScreenshotIds.current.has(log.image_path)) {
            const newScreenshot: Screenshot = {
              id: `temp-${log.step_index}`,
              image_path: log.image_path,
              timestamp: new Date().toISOString(),
              description: log.description,
              step_index: log.step_index
            };

            setScreenshots(prev => {
              const updated = [...prev, newScreenshot].sort((a, b) => a.step_index - b.step_index);
              return updated;
            });

            processedScreenshotIds.current.add(log.image_path);
          }
        }
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = () => {
      console.error("WebSocket error");
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [runId]);

  const handleThumbnailClick = (screenshot: Screenshot) => {
    setSelectedScreenshot(screenshot);
    if (onScreenshotClick) {
      onScreenshotClick(screenshot);
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-4">
        <div className="flex items-center justify-center h-48">
          <div className="text-gray-400">Loading screenshots...</div>
        </div>
      </div>
    );
  }

  if (!runId || screenshots.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-4">
        <div className="flex items-center justify-center h-48">
          <div className="text-gray-500">No screenshots available</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-gray-100 font-semibold">Screenshot Timeline</h4>
        {screenshots.length > 0 && (
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-green-400 text-xs">Live</span>
          </span>
        )}
      </div>

      {/* Selected screenshot preview */}
      {selectedScreenshot && (
        <div className="mb-4">
          <div className="relative bg-gray-800 rounded-lg overflow-hidden">
            <img
              src={selectedScreenshot.image_path}
              alt={selectedScreenshot.description || "Screenshot"}
              className="w-full"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-2">
              <p className="text-white text-sm">
                {selectedScreenshot.description || `Step ${selectedScreenshot.step_index + 1}`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {screenshots.map((screenshot, index) => (
          <div
            key={screenshot.id}
            onClick={() => handleThumbnailClick(screenshot)}
            className={`flex-shrink-0 cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
              selectedScreenshot?.id === screenshot.id
                ? "border-blue-500 ring-2 ring-blue-500 ring-opacity-50"
                : "border-gray-700 hover:border-gray-500"
            }`}
          >
            <img
              src={screenshot.image_path}
              alt={`Step ${screenshot.step_index + 1}`}
              className="w-24 h-16 object-cover"
            />
            <div className="bg-gray-800 px-2 py-1">
              <span className="text-xs text-gray-300">Step {screenshot.step_index + 1}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}