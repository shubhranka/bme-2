import { useState, useEffect } from "react";
import { runTest, generateAndRunTest, listTests, listRuns } from "./api";
import { GeneratedCode } from "./components/GeneratedCode";

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
  const [url, setUrl] = useState("");
  const [testName, setTestName] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);
  const [useAI, setUseAI] = useState(true);
  const [savedTests, setSavedTests] = useState<SavedTest[]>([]);
  const [recentRuns, setRecentRuns] = useState<TestRun[]>([]);

  // Load test history on mount
  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const [tests, runs] = await Promise.all([listTests(), listRuns()]);
      setSavedTests(tests);
      setRecentRuns(runs);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    setResult(null);

    try {
      const response = useAI
        ? await generateAndRunTest(url, testName || undefined)
        : await runTest(url);
      setResult(response);
      // Reload history after test run
      loadHistory();
    } catch (err) {
      setResult({ success: false, error: "Failed to run test" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "20px", fontFamily: "system-ui" }}>
      <h1>E2E Test Engineer</h1>
      <p>Enter a URL to run an AI-generated Playwright test.</p>

      <form onSubmit={handleSubmit} style={{ marginBottom: "20px" }}>
        <div style={{ marginBottom: "15px" }}>
          <label style={{ marginRight: "15px" }}>
            <input
              type="radio"
              checked={useAI}
              onChange={() => setUseAI(true)}
              style={{ marginRight: "5px" }}
            />
            AI-Generated Test
          </label>
          <label>
            <input
              type="radio"
              checked={!useAI}
              onChange={() => setUseAI(false)}
              style={{ marginRight: "5px" }}
            />
            Simple Test
          </label>
        </div>

        {useAI && (
          <input
            type="text"
            value={testName}
            onChange={(e) => setTestName(e.target.value)}
            placeholder="Test name (optional - saves to database)"
            disabled={loading}
            style={{
              padding: "10px",
              fontSize: "16px",
              width: "60%",
              marginRight: "10px",
              marginBottom: "10px",
              display: "block",
            }}
          />
        )}

        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          disabled={loading}
          style={{
            padding: "10px",
            fontSize: "16px",
            width: "60%",
            marginRight: "10px",
          }}
        />
        <button
          type="submit"
          disabled={loading || !url}
          style={{
            padding: "10px 20px",
            fontSize: "16px",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Running..." : useAI ? "Generate & Run" : "Run Test"}
        </button>
      </form>

      {/* Test History */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "30px" }}>
        {/* Saved Tests */}
        <div>
          <h3>Saved Tests ({savedTests.length})</h3>
          {savedTests.length === 0 ? (
            <p style={{ color: "#666" }}>No saved tests yet</p>
          ) : (
            <div style={{ backgroundColor: "#f8f8f8", padding: "15px", borderRadius: "8px" }}>
              {savedTests.map((test) => (
                <div
                  key={test.id}
                  style={{
                    padding: "10px",
                    borderBottom: "1px solid #ddd",
                  }}
                >
                  <div style={{ fontWeight: "bold" }}>{test.name}</div>
                  <div style={{ fontSize: "14px", color: "#666" }}>{test.target_url}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Runs */}
        <div>
          <h3>Recent Runs ({recentRuns.length})</h3>
          {recentRuns.length === 0 ? (
            <p style={{ color: "#666" }}>No test runs yet</p>
          ) : (
            <div style={{ backgroundColor: "#f8f8f8", padding: "15px", borderRadius: "8px" }}>
              {recentRuns.map((run) => (
                <div
                  key={run.id}
                  style={{
                    padding: "10px",
                    borderBottom: "1px solid #ddd",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "4px",
                        fontSize: "12px",
                        backgroundColor: run.status === "passed" ? "#d4edda" : run.status === "failed" ? "#f8d7da" : "#fff3cd",
                        color: run.status === "passed" ? "#155724" : run.status === "failed" ? "#721c24" : "#856404",
                      }}
                    >
                      {run.status}
                    </span>
                    <span style={{ fontWeight: "bold" }}>{run.page_title || "Unknown Page"}</span>
                  </div>
                  <div style={{ fontSize: "14px", color: "#666" }}>{run.page_url}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {result && (
        <div style={{ marginTop: "20px" }}>
          {result.success ? (
            <>
              <h2>Test Passed!</h2>
              <p>
                <strong>Title:</strong> {result.title}
              </p>
              <p>
                <strong>URL:</strong> {result.url}
              </p>

              {result.test && <GeneratedCode test={result.test} />}

              {result.steps && result.steps.length > 0 && (
                <div style={{ marginTop: "20px" }}>
                  <h3>Execution Steps:</h3>
                  <div
                    style={{
                      backgroundColor: "#f8f8f8",
                      padding: "15px",
                      borderRadius: "8px",
                    }}
                  >
                    {result.steps.map((step, index) => (
                      <div
                        key={index}
                        style={{
                          marginBottom: "10px",
                          paddingBottom: "10px",
                          borderBottom: index < result.steps!.length - 1 ? "1px solid #ddd" : "none",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span style={{ fontWeight: "bold" }}>{index + 1}.</span>
                          <code
                            style={{
                              backgroundColor: step.status === "failed" ? "#f8d7da" : "#d4edda",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              color: step.status === "failed" ? "#721c24" : "#155724",
                            }}
                          >
                            {step.action}
                          </code>
                          <span style={{ color: "#666", fontSize: "14px" }}>{step.selector}</span>
                          {step.error && (
                            <span style={{ color: "red", fontSize: "14px" }}>
                              Error: {step.error}
                            </span>
                          )}
                        </div>
                        {step.screenshot && (
                          <img
                            src={step.screenshot}
                            alt={`Step ${index + 1}`}
                            style={{
                              maxWidth: "200px",
                              marginTop: "10px",
                              border: "1px solid #ddd",
                              borderRadius: "4px",
                            }}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.screenshot && (
                <div style={{ marginTop: "20px" }}>
                  <h3>Final Screenshot:</h3>
                  <img
                    src={result.screenshot}
                    alt="Screenshot"
                    style={{ maxWidth: "100%", border: "1px solid #ccc", borderRadius: "4px" }}
                  />
                </div>
              )}
            </>
          ) : (
            <div style={{ color: "red" }}>
              <h2>Test Failed</h2>
              <p>{result.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
