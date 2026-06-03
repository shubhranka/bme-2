interface TestStep {
  action_type: string;
  selector: string;
  description: string | null;
}

interface GeneratedTest {
  description: string;
  steps: TestStep[];
}

interface GeneratedCodeProps {
  test: GeneratedTest;
}

export function GeneratedCode({ test }: GeneratedCodeProps) {
  return (
    <div className="mt-6 p-6 bg-gray-50 rounded-xl border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-2">Generated Test Plan</h3>
      <p className="text-gray-600 italic mb-6">{test.description}</p>

      <h4 className="text-md font-semibold text-gray-900 mb-4">Steps:</h4>
      <ol className="space-y-3">
        {test.steps.map((step, index) => (
          <li key={index} className="flex items-start gap-3">
            <span className="font-bold text-gray-700">{index + 1}.</span>
            <div className="flex-1">
              <code className="px-2 py-1 bg-pink-100 text-pink-800 rounded text-sm font-mono">
                {step.action_type}
              </code>
              <span className="ml-2 text-gray-700">
                {step.description || `on "${step.selector}"`}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
