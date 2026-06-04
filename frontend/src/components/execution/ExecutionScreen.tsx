import { useState, useEffect } from "react";
import { LogStream } from "./LogStream";
import { VideoTimeline } from "./VideoTimeline";
import { LiveBrowserView } from "./LiveBrowserView";

interface ExecutionScreenProps {
  runId: string | null;
  onComplete?: () => void;
}

export function ExecutionScreen({ runId, onComplete }: ExecutionScreenProps) {
  const [selectedScreenshot, setSelectedScreenshot] = useState<{ image_path: string } | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    // Reset completion state when runId changes
    if (runId) {
      setIsComplete(false);
    }
  }, [runId]);

  const handleComplete = () => {
    setIsComplete(true);
    if (onComplete) {
      onComplete();
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Log Stream */}
      <div>
        <LogStream runId={runId} onComplete={handleComplete} />
      </div>

      {/* Right: Live Browser View (while running) or Video Timeline (when complete) */}
      <div>
        {isComplete ? (
          <VideoTimeline runId={runId} onScreenshotClick={(screenshot) => {
            setSelectedScreenshot(screenshot);
          }} />
        ) : (
          <LiveBrowserView runId={runId} onComplete={handleComplete} isComplete={isComplete} />
        )}
      </div>

      {/* Selected screenshot preview */}
      {selectedScreenshot && isComplete && (
        <div className="lg:col-span-2 mt-4">
          <div className="relative rounded-lg overflow-hidden border border-gray-300">
            <img
              src={selectedScreenshot.image_path}
              alt="Screenshot preview"
              className="w-full"
            />
          </div>
        </div>
      )}
    </div>
  );
}
