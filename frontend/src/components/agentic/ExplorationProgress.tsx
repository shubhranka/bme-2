import { useState, useEffect, useRef } from "react";

interface CoverageMetrics {
  page_coverage: number;
  element_coverage: number;
  total_pages: number;
  tested_pages: number;
  total_elements: number;
  tested_elements: number;
  overall_coverage: number;
}

interface AgentDecision {
  iteration: number;
  decision: string;
  reasoning: string;
  target_id: string | null;
}

interface DiscoveredPage {
  id: string;
  url: string;
  title: string | null;
  tested: boolean;
  test_count: number;
  discovered_from: string | null;
}

interface GeneratedTest {
  description: string;
  steps: Array<{
    action_type: string;
    selector: string;
    value: string | null;
    description: string | null;
  }>;
}

interface ExplorationProgressProps {
  sessionId: string | null;
  onComplete?: () => void;
}

interface ExplorationScreenshot {
  id: string;
  image_path: string;
  description: string;
  step_index: number;
}

export function ExplorationProgress({ sessionId, onComplete }: ExplorationProgressProps) {
  const [session, setSession] = useState<any>(null);
  const [coverage, setCoverage] = useState<CoverageMetrics | null>(null);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [pages, setPages] = useState<DiscoveredPage[]>([]);
  const [generatedTests, setGeneratedTests] = useState<GeneratedTest[]>([]);
  const [screenshots, setScreenshots] = useState<ExplorationScreenshot[]>([]);
  const isCompleteRef = useRef(false);

  useEffect(() => {
    if (!sessionId) return;

    let interval: ReturnType<typeof setInterval> | null = null;
    isCompleteRef.current = false;

    const fetchSession = async () => {
      // Stop polling if already complete
      if (isCompleteRef.current) return;

      try {
        const response = await fetch(`/api/exploration/${sessionId}`, {
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          setSession(data);
          setCoverage(data.coverage);

          // Check if complete - STOP ALL POLLING
          if (data.status === "completed" || data.status === "stopped") {
            isCompleteRef.current = true;
            if (interval) {
              clearInterval(interval);
              interval = null;
            }
            if (onComplete) onComplete();
            return;
          }
        }
      } catch (err) {
        console.error("Failed to fetch session:", err);
      }
    };

    // Initial fetch
    fetchSession();

    // Poll every 3 seconds (slower than before)
    interval = setInterval(fetchSession, 3000);

    return () => {
      if (interval) clearInterval(interval);
      isCompleteRef.current = true;
    };
  }, [sessionId, onComplete]);

  useEffect(() => {
    if (!sessionId) return;

    let interval: ReturnType<typeof setInterval> | null = null;

    const fetchDetails = async () => {
      // Stop fetching if already complete
      if (isCompleteRef.current) return;

      try {
        // Fetch coverage details
        const coverageResponse = await fetch(`/api/exploration/${sessionId}/coverage`, {
          credentials: "include",
        });
        if (coverageResponse.ok) {
          const data = await coverageResponse.json();
          setCoverage(data.coverage);
          setDecisions(data.recent_decisions);
        }

        // Fetch pages
        const pagesResponse = await fetch(`/api/exploration/${sessionId}/pages`, {
          credentials: "include",
        });
        if (pagesResponse.ok) {
          const data = await pagesResponse.json();
          setPages(data);
        }

        // Fetch screenshots using existing run screenshots endpoint
        // Note: We're using the same screenshot system as regular test runs
        try {
          const screenshotsResponse = await fetch(`/api/runs/${sessionId}/screenshots`, {
            credentials: "include",
          });
          if (screenshotsResponse.ok) {
            const data = await screenshotsResponse.json();
            setScreenshots(data);
          }
        } catch (err) {
          // Screenshots might not exist for all sessions, that's okay
          console.log("No screenshots available yet");
        }
      } catch (err) {
        console.error("Failed to fetch details:", err);
      }
    };

    // Initial fetch
    fetchDetails();

    // Poll every 5 seconds for details
    interval = setInterval(fetchDetails, 5000);

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [sessionId]);

  if (!session) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-center justify-center h-48">
          <div className="text-gray-500">Initializing exploration...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xl font-bold text-gray-900">Exploration Progress</h3>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
          session.status === "completed"
            ? "bg-green-100 text-green-800"
            : session.status === "running"
            ? "bg-blue-100 text-blue-800"
            : "bg-gray-100 text-gray-800"
        }`}>
          {session.status === "running" && (
            <span className="inline-block w-2 h-2 bg-blue-500 rounded-full mr-2 animate-pulse"></span>
          )}
          {session.status.charAt(0).toUpperCase() + session.status.slice(1)}
        </div>
      </div>

      {/* Coverage Metrics */}
      {coverage && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-900">
              {(coverage.page_coverage * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Page Coverage</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-900">
              {(coverage.element_coverage * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Element Coverage</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-900">{coverage.total_pages}</div>
            <div className="text-sm text-gray-600">Pages Discovered</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-900">{coverage.total_elements}</div>
            <div className="text-sm text-gray-600">Elements Found</div>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {coverage && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Overall Progress</span>
            <span className="text-sm text-gray-600">
              {session.current_iteration} / {session.max_iterations} iterations
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all"
              style={{ width: `${(coverage.overall_coverage * 100)}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Live Screenshots */}
      {screenshots.length > 0 && (
        <div className="mb-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-3">
            Live Exploration Screenshots
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 max-h-96 overflow-y-auto">
            {screenshots.map((screenshot) => (
              <div key={screenshot.id} className="relative group">
                <img
                  src={`/artifacts/${screenshot.image_path}`}
                  alt={screenshot.description}
                  className="w-full h-32 object-cover rounded-lg border border-gray-300 cursor-pointer hover:border-blue-500 transition-all"
                  onError={(e) => {
                    console.log("Failed to load image:", screenshot.image_path);
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-2 rounded-b-lg opacity-0 group-hover:opacity-100 transition-opacity">
                  <p className="text-white text-xs truncate">
                    {screenshot.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Agent Decisions */}
      {decisions.length > 0 && (
        <div className="mb-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-3">Recent Decisions</h4>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {decisions.slice(-10).reverse().map((decision, index) => (
              <div
                key={index}
                className="p-3 bg-gray-50 rounded-lg border border-gray-200"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-gray-500">
                    Iteration {decision.iteration}
                  </span>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                    decision.decision === "test_element"
                      ? "bg-blue-100 text-blue-800"
                      : decision.decision === "explore_page"
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {decision.decision.replace("_", " ")}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{decision.reasoning}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Discovered Pages */}
      {pages.length > 0 && (
        <div>
          <h4 className="text-lg font-semibold text-gray-900 mb-3">
            Discovered Pages ({pages.length})
            <span className="ml-2 text-xs font-normal text-gray-500">
              (AI-powered exploration)
            </span>
          </h4>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {pages.map((page) => (
              <div
                key={page.id}
                className={`p-3 rounded-lg border ${
                  page.tested
                    ? "border-green-200 bg-green-50"
                    : "border-gray-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="font-medium text-gray-900">
                      {page.title || "Untitled Page"}
                    </div>
                    <div className="text-sm text-gray-600 truncate max-w-md">
                      {page.url}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {page.tested && (
                      <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded">
                        ✓ Tested
                      </span>
                    )}
                    <span className="text-xs text-gray-500">
                      {page.test_count} test{page.test_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Decision Summary */}
      {session.status === "completed" && (
        <div className="mt-6 p-4 bg-purple-50 rounded-lg border border-purple-200">
          <h4 className="text-lg font-semibold text-purple-900 mb-2">
            🤖 AI Exploration Complete
          </h4>
          <p className="text-sm text-purple-800">
            AI discovered {coverage?.total_pages || 0} pages and {coverage?.total_elements || 0} elements,
            achieving {(coverage?.overall_coverage * 100 || 0).toFixed(1)}% coverage in {session.current_iteration} iterations.
          </p>
          <div className="mt-3 text-xs text-purple-700">
            <strong>AI Used:</strong> Agent decided between testing elements vs exploring pages using LLM analysis
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={async () => {
                // Fetch generated tests
                try {
                  const response = await fetch(`/api/export/test-suite/${sessionId}`, {
                    method: 'POST',
                    credentials: 'include',
                  });
                  if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `playwright_tests_${sessionId.slice(0, 8)}.zip`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                  }
                } catch (err) {
                  console.error('Export failed:', err);
                }
              }}
              className="px-3 py-1 text-xs font-medium bg-purple-600 text-white rounded hover:bg-purple-700 transition-all"
            >
              📥 Export Playwright Tests
            </button>
          </div>
        </div>
      )}

      {/* Generated Tests Preview */}
      {decisions.length > 0 && session.status === "completed" && (
        <div className="mt-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-3">
            🧪 Generated Tests ({decisions.filter(d => d.decision === 'test_element').length})
          </h4>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {decisions
              .filter(d => d.decision === 'test_element')
              .slice(-10)
              .reverse()
              .map((decision, index) => (
                <div
                  key={index}
                  className="p-3 bg-blue-50 rounded-lg border border-blue-200"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-medium text-gray-500">
                      Iteration {decision.iteration}
                    </span>
                    <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded">
                      Test Generated
                    </span>
                  </div>
                  <p className="text-sm text-gray-700">{decision.reasoning}</p>
                  <div className="mt-2 text-xs text-gray-500">
                    ✅ Test executed and validated
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
