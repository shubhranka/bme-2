import { useState, useEffect } from "react";
import { runTest, generateAndRunTest, getTaskStatus, listTests, listRuns } from "./api";
import { GeneratedCode } from "./components/GeneratedCode";
import { LoginForm } from "./components/auth/LoginForm";
import { RegisterForm } from "./components/auth/RegisterForm";
import { useAuth } from "./hooks/useAuth";

interface TestStep {
  action_type: string;
  selector: string;
  description: string | null;
}

interface GeneratedTest {
  description: string;
  steps: TestStep[];
}

interface TestResult {
  success: boolean;
  title?: string;
  url?: string;
  screenshot?: string;
  error?: string;
  test?: GeneratedTest;
  steps?: Array<{
    action: string;
    selector: string;
    status: string;
    error?: string;
    screenshot?: string;
  }>;
}

interface SavedTest {
  id: string;
  name: string;
  target_url: string;
  created_at: string;
}

interface TestRun {
  id: string;
  test_id: string | null;
  status: string;
  page_title: string | null;
  page_url: string | null;
  created_at: string;
}

function App() {
  const { user, loading, logout, refreshAuth } = useAuth();
  const [showLogin, setShowLogin] = useState(true);
  const [url, setUrl] = useState("");
  const [testName, setTestName] = useState("");
  const [testLoading, setTestLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [useAI, setUseAI] = useState(true);
  const [savedTests, setSavedTests] = useState<SavedTest[]>([]);
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([]);

  // Load test history on mount or when user changes
  useEffect(() => {
    if (user) {
      loadHistory();
    }
  }, [user]);

  const loadHistory = async () => {
    try {
      const [tests, runs] = await Promise.all([listTests(), listRuns()]);
      setSavedTests(tests);
      setRecentRuns(runs);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const handleAuthSuccess = () => {
    refreshAuth();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setTestLoading(true);
    setResult(null);

    try {
      // Submit task
      const response = useAI
        ? await generateAndRunTest(url, testName || undefined)
        : await runTest(url);

      // Poll for task completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await getTaskStatus(response.task_id);

          if (status.status === "completed" && status.result) {
            clearInterval(pollInterval);
            setResult(status.result);
            setTestLoading(false);
            loadHistory();
          } else if (status.status === "failed") {
            clearInterval(pollInterval);
            setResult({ success: false, error: status.error || "Task failed" });
            setTestLoading(false);
          }
        } catch (err) {
          clearInterval(pollInterval);
          setResult({ success: false, error: "Failed to check task status" });
          setTestLoading(false);
        }
      }, 2000); // Poll every 2 seconds

      // Store interval for cleanup
      return () => clearInterval(pollInterval);

    } catch (err: any) {
      setResult({ success: false, error: err.message || "Failed to queue test" });
      setTestLoading(false);
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  // Show auth forms if not authenticated
  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        {showLogin ? (
          <LoginForm
            onSuccess={handleAuthSuccess}
          />
        ) : (
          <RegisterForm
            onSuccess={handleAuthSuccess}
            onSwitchToLogin={() => setShowLogin(true)}
          />
        )}
        <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2">
          <button
            onClick={() => setShowLogin(!showLogin)}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            {showLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    );
  }

  // Show main app if authenticated
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">E2E Test Engineer</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">{user.email}</span>
            <button
              onClick={logout}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-all"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <p className="text-gray-600 mb-8">Enter a URL to run an AI-generated Playwright test.</p>

        {/* Test Form */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
          <form onSubmit={handleSubmit}>
            <div className="flex gap-4 mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={useAI}
                  onChange={() => setUseAI(true)}
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-gray-700">AI-Generated Test</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={!useAI}
                  onChange={() => setUseAI(false)}
                  className="w-4 h-4 text-blue-600"
                />
                <span className="text-gray-700">Simple Test</span>
              </label>
            </div>

            {useAI && (
              <input
                type="text"
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                placeholder="Test name (optional - saves to database)"
                disabled={testLoading}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
              />
            )}

            <div className="flex gap-4">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                disabled={testLoading}
                className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={testLoading || !url}
                className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {testLoading ? "Running..." : useAI ? "Generate & Run" : "Run Test"}
              </button>
            </div>
          </form>
        </div>

        {/* Test History */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Saved Tests */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Saved Tests ({savedTests.length})</h3>
            {savedTests.length === 0 ? (
              <p className="text-gray-500">No saved tests yet</p>
            ) : (
              <div className="space-y-3">
                {savedTests.map((test) => (
                  <div key={test.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="font-medium text-gray-900">{test.name}</div>
                    <div className="text-sm text-gray-600">{test.target_url}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Runs */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Runs ({recentRuns.length})</h3>
            {recentRuns.length === 0 ? (
              <p className="text-gray-500">No test runs yet</p>
            ) : (
              <div className="space-y-3">
                {recentRuns.map((run) => (
                  <div key={run.id} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          run.status === "passed"
                            ? "bg-green-100 text-green-800"
                            : run.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                        }`}
                      >
                        {run.status}
                      </span>
                      <span className="font-medium text-gray-900">{run.page_title || "Unknown Page"}</span>
                    </div>
                    <div className="text-sm text-gray-600">{run.page_url}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Test Result */}
        {result && (
          <div className="bg-white rounded-xl shadow-sm p-6">
            {result.success ? (
              <>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">Test Passed!</h2>
                <div className="space-y-2 mb-6">
                  <p className="text-gray-700"><strong>Title:</strong> {result.title}</p>
                  <p className="text-gray-700"><strong>URL:</strong> {result.url}</p>
                </div>

                {result.test && <GeneratedCode test={result.test} />}

                {result.steps && result.steps.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Execution Steps:</h3>
                    <div className="space-y-3">
                      {result.steps.map((step, index) => (
                        <div
                          key={index}
                          className={`p-4 rounded-lg border ${
                            step.status === "failed" ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50"
                          }`}
                        >
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-bold text-gray-700">{index + 1}.</span>
                            <code className={`px-2 py-1 rounded text-sm font-mono ${
                              step.status === "failed" ? "bg-red-200 text-red-800" : "bg-green-200 text-green-800"
                            }`}>
                              {step.action}
                            </code>
                            <span className="text-gray-600 text-sm">{step.selector}</span>
                            {step.error && (
                              <span className="text-red-600 text-sm">Error: {step.error}</span>
                            )}
                          </div>
                          {step.screenshot && (
                            <img
                              src={step.screenshot}
                              alt={`Step ${index + 1}`}
                              className="max-w-xs mt-2 rounded border border-gray-300"
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {result.screenshot && (
                  <div className="mt-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Final Screenshot:</h3>
                    <img
                      src={result.screenshot}
                      alt="Screenshot"
                      className="max-w-full rounded-lg border border-gray-300"
                    />
                  </div>
                )}
              </>
            ) : (
              <div className="text-red-600">
                <h2 className="text-2xl font-bold mb-2">Test Failed</h2>
                <p>{result.error}</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
