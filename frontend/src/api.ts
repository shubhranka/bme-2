interface TestResult {
  success: boolean;
  title?: string;
  url?: string;
  screenshot?: string;
  error?: string;
  run_id?: string;
  test_id?: string;
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

export async function runTest(url: string): Promise<TestResult> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function generateAndRunTest(url: string, name?: string): Promise<TestResult> {
  const response = await fetch("/api/generate-and-run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url, name }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listTests(): Promise<SavedTest[]> {
  const response = await fetch("/api/tests");

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listRuns(): Promise<TestRun[]> {
  const response = await fetch("/api/runs");

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}
