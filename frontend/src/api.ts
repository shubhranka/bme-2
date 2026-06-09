interface TestResult {
  success: boolean;
  title?: string;
  url?: string;
  screenshot?: string;
  error?: string;
  run_id?: string;
  test_id?: string;
  task_id?: string;
  test?: {
    description: string;
    steps: Array<{
      action_type: string;
      selector: string;
      description: string | null;
    }>;
  };
  steps?: Array<{
    action: string;
    selector: string;
    status: string;
    error?: string;
    screenshot?: string;
  }>;
}

interface TaskStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  message?: string;
  result?: TestResult;
  error?: string;
}

interface SavedTest {
  id: string;
  name: string;
  target_url: string;
  generated_code: string | null;
  created_at: string;
  updated_at: string;
}

interface TestRun {
  id: string;
  test_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  page_title: string | null;
  page_url: string | null;
  error_message: string | null;
  created_at: string;
}

export async function runTest(url: string): Promise<{ run_id: string; task_id: string; status: string; message: string }> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function generateAndRunTest(url: string, name?: string): Promise<{ run_id: string; task_id: string; status: string; message: string; test_id?: string }> {
  const response = await fetch("/api/generate-and-run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ url, name }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await fetch(`/api/tasks/${taskId}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listTests(): Promise<SavedTest[]> {
  const response = await fetch("/api/tests", {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listRuns(): Promise<TestRun[]> {
  const response = await fetch("/api/runs", {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// Exploration session types
interface ExplorationSession {
  id: string;
  start_url: string;
  status: string;
  max_iterations: number;
  coverage_threshold: number;
  current_iteration: number;
  coverage_percentage: number;
  created_at: string;
  completed_at: string | null;
}

interface CoverageMetrics {
  page_coverage: number;
  element_coverage: number;
  total_pages: number;
  tested_pages: number;
  total_elements: number;
  tested_elements: number;
  overall_coverage: number;
}

interface ExplorationRequest {
  url: string;
  max_iterations?: number;
  coverage_threshold?: number;
  follow_links?: boolean;
  max_pages?: number;
}

export async function startExploration(request: ExplorationRequest): Promise<{ session_id: string; task_id: string; status: string; message: string }> {
  const response = await fetch("/api/exploration/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function getExplorationSession(sessionId: string): Promise<ExplorationSession & { coverage: CoverageMetrics }> {
  const response = await fetch(`/api/exploration/${sessionId}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function stopExploration(sessionId: string): Promise<{ message: string }> {
  const response = await fetch(`/api/exploration/${sessionId}/stop`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listExplorationSessions(): Promise<ExplorationSession[]> {
  const response = await fetch("/api/exploration/sessions", {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}
