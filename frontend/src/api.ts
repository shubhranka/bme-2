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
