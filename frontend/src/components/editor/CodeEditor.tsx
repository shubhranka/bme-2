import { useState, useEffect } from "react";
import Editor, { Monaco } from "@monaco-editor/react";

interface CodeEditorProps {
  code: string;
  onChange?: (value: string) => void;
  language?: string;
  readOnly?: boolean;
  height?: string;
}

export function CodeEditor({
  code,
  onChange,
  language = "python",
  readOnly = false,
  height = "400px"
}: CodeEditorProps) {
  const [value, setValue] = useState(code);

  useEffect(() => {
    setValue(code);
  }, [code]);

  const handleEditorChange = (value: string | undefined) => {
    const newValue = value || "";
    setValue(newValue);
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    <div className="border border-gray-300 rounded-lg overflow-hidden">
      <Editor
        height={height}
        defaultLanguage={language}
        value={value}
        onChange={handleEditorChange}
        theme="vs-dark"
        options={{
          readOnly,
          minimap: { enabled: true },
          fontSize: 14,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
          wordWrap: "on",
        }}
      />
    </div>
  );
}
