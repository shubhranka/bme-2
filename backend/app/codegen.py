"""Playwright code generation for test export."""
import os
import zipfile
from typing import List, Dict, Any, Optional
from datetime import datetime


class PlaywrightCodeGenerator:
    """Converts internal test format to runnable Playwright Python."""

    def generate_test_file(
        self,
        test: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate complete test file with imports and fixtures."""
        description = test.get("description", "Test")
        steps = test.get("steps", [])

        # Generate imports
        imports = [
            "import pytest",
            "from playwright.async_api import Page, async_playwright, expect"
        ]

        # Generate docstring
        docstring = f'"""{description}"""' if description else '"""Test"""'

        # Generate test steps
        step_lines = []
        for i, step in enumerate(steps):
            step_code = self._generate_step_code(step, i + 1)
            step_lines.append("        " + step_code)

        steps_code = "\n".join(step_lines)

        # Full test file
        test_file = f"""{'\\n'.join(imports)}

@pytest.mark.asyncio
async def test_{self._sanitize_name(test.get('name', 'test'))}(page: Page):
    {docstring}

{steps_code}
"""
        return test_file

    def _generate_step_code(self, step: Dict[str, Any], step_num: int) -> str:
        """Generate Python code for a single test step."""
        action_type = step.get("action_type")
        selector = step.get("selector", "")
        value = step.get("value", "")
        description = step.get("description", "")

        code = ""

        if action_type == "navigate":
            code = f'await page.goto("{selector}")'
            if description:
                code = code + f"  # {description}"

        elif action_type == "click":
            code = f'await page.click("{selector}")'
            if description:
                code = code + f"  # {description}"

        elif action_type == "fill":
            code = f'await page.fill("{selector}", "{value}")'
            if description:
                code = code + f"  # {description}"

        elif action_type == "wait":
            code = f'await page.wait_for_selector("{selector}")'
            if description:
                code = code + f"  # {description}"

        elif action_type == "assert":
            visibility = step.get("value", "visible")
            if visibility == "visible":
                code = f'await expect(page.locator("{selector}")).to_be_visible()'
            else:
                code = f'await expect(page.locator("{selector}")).to_be_visible()'
            if description:
                code = code + f"  # {description}"

        else:
            code = f"# Unknown action: {action_type}"

        return code

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use in Python function names."""
        # Remove or replace invalid characters
        sanitized = name.lower()
        sanitized = ''.join(
            c if c.isalnum() or c == '_' else '_'
            for c in sanitized
        )
        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = 'test_' + sanitized
        return sanitized or "test"

    def generate_conftest(self) -> str:
        """Generate conftest.py with shared fixtures."""
        return '''import pytest
from playwright.async_api import async_playwright, Page


@pytest.fixture
async def page() -> Page:
    """Shared browser page fixture."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        yield page

        await context.close()
        await browser.close()
'''

    def generate_requirements(self) -> str:
        """Generate requirements.txt for exported tests."""
        return '''playwright==1.40.0
pytest==7.4.3
pytest-asyncio==0.21.1
'''

    def generate_readme(self, tests: List[Dict[str, Any]]) -> str:
        """Generate README.md for exported test suite."""
        test_count = len(tests)
        test_names = "\n".join([
            f"- {t.get('name', 'test')}: {t.get('description', '')}"
            for t in tests[:5]
        ])

        return f"""# E2E Test Suite

Auto-generated Playwright tests exported from E2E Test Engineer Platform.

## Test Count
{test_count} tests

## Tests
{test_names if test_names else '- All tests'}

## Running Tests

Install dependencies:
```bash
pip install -r requirements.txt
```

Run tests:
```bash
pytest tests/ -v
```

Run headless:
```bash
pytest tests/ -v --headed
```

## Requirements
- Python 3.8+
- Playwright browser: `npx playwright install chromium`

Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

    def generate_test_suite(
        self,
        tests: List[Dict[str, Any]],
        session_name: str = "test_suite"
    ) -> Dict[str, str]:
        """Generate a complete test suite with all files."""
        files = {}

        # Generate individual test files
        test_files = {}
        for i, test in enumerate(tests):
            test_name = self._sanitize_name(test.get('name', f'test_{i}'))
            test_files[f"test_{test_name}.py"] = self.generate_test_file(test)

        # Add supporting files
        files.update(test_files)
        files["conftest.py"] = self.generate_conftest()
        files["requirements.txt"] = self.generate_requirements()
        files["README.md"] = self.generate_readme(tests)

        return files

    def create_zip_archive(
        self,
        files: Dict[str, str],
        output_path: str
    ) -> str:
        """Create a ZIP archive of the test suite."""
        zip_path = os.path.join(output_path, "test_suite.zip")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path, content in files.items():
                zip_file.writestr(file_path, content)

        return zip_path

    def generate_action(self, action: Dict[str, Any]) -> str:
        """Convert action to Playwright Python code."""
        action_type = action.get("action_type")
        selector = action.get("selector", "")
        value = action.get("value", "")

        conversions = {
            "navigate": f'await page.goto("{selector}")',
            "click": f'await page.click("{selector}")',
            "fill": f'await page.fill("{selector}", "{value}")',
            "wait": f'await page.wait_for_selector("{selector}")',
            "assert": f'await expect(page.locator("{selector}")).to_be_visible()'
        }

        return conversions.get(action_type, f"# Unknown action: {action_type}")
