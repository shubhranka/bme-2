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
    <div
      style={{
        marginTop: "20px",
        padding: "15px",
        backgroundColor: "#f5f5f5",
        borderRadius: "8px",
        border: "1px solid #ddd",
      }}
    >
      <h3>Generated Test Plan</h3>
      <p style={{ fontStyle: "italic" }}>{test.description}</p>

      <h4>Steps:</h4>
      <ol style={{ paddingLeft: "20px" }}>
        {test.steps.map((step, index) => (
          <li key={index} style={{ marginBottom: "8px" }}>
            <code
              style={{
                backgroundColor: "#e8e8e8",
                padding: "2px 6px",
                borderRadius: "4px",
                color: "#d63384",
              }}
            >
              {step.action_type}
            </code>
            <span style={{ marginLeft: "8px" }}>
              {step.description || `on "${step.selector}"`}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
