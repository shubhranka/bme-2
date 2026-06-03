from datetime import datetime
import uuid
import json
from pathlib import Path
from playwright.async_api import async_playwright

from ..celery_app import celery_app
from ..discovery import discover_page_structure
from ..llm import generate_test_from_structure
from ..schemas import GeneratedTest

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


@celery_app.task(bind=True, name="app.workers.tasks.run_simple_test_task")
def run_simple_test_task(self, url: str) -> dict:
    """Run a simple Playwright test (Celery wrapper)."""
    import asyncio

    result = asyncio.run(_run_simple_test(url))
    return result


async def _run_simple_test(url: str) -> dict:
    """Async implementation of simple test."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot_path = ARTIFACTS_DIR / f"simple_{uuid.uuid4()}.png"
            await page.screenshot(path=str(screenshot_path))

            title = await page.title()
            url_final = page.url

            return {
                "success": True,
                "title": title,
                "url": url_final,
                "screenshot": f"/artifacts/{screenshot_path.name}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await browser.close()


@celery_app.task(bind=True, name="app.workers.tasks.generate_and_run_task")
def generate_and_run_task(self, url: str, name: str | None = None) -> dict:
    """Generate and run an AI test (Celery wrapper)."""
    import asyncio

    result = asyncio.run(_generate_and_run(url, name, self.request.id))
    return result


async def _generate_and_run(url: str, name: str | None, task_id: str) -> dict:
    """Async implementation of generate and run."""
    run_id = task_id or str(uuid.uuid4())
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(exist_ok=True)

    try:
        # Step 1: Discover page structure
        page_structure = await discover_page_structure(url)

        # Step 2: Generate test using LLM
        generated_test = generate_test_from_structure(page_structure)

        # Step 3: Run the generated test
        result = await _run_generated_test(url, generated_test, run_dir)

        # Add metadata
        result["run_id"] = run_id
        result["title"] = page_structure.title
        result["url"] = page_structure.url
        result["test"] = {
            "description": generated_test.description,
            "steps": [
                {
                    "action_type": step.action_type,
                    "selector": step.selector,
                    "description": step.description,
                }
                for step in generated_test.steps
            ],
        }

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id
        }


async def _run_generated_test(url: str, test: GeneratedTest, run_dir: Path) -> dict:
    """Run a generated test with screenshots."""
    steps_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            for i, step in enumerate(test.steps):
                step_result = {"action": step.action_type, "selector": step.selector}

                try:
                    if step.action_type == "navigate":
                        await page.goto(step.selector, wait_until="networkidle", timeout=30000)
                        step_result["status"] = "success"

                    elif step.action_type == "click":
                        await page.click(step.selector, timeout=10000)
                        step_result["status"] = "success"

                    elif step.action_type == "fill":
                        await page.fill(step.selector, step.value or "")
                        step_result["status"] = "success"

                    elif step.action_type == "wait":
                        await page.wait_for_selector(step.selector, timeout=10000)
                        step_result["status"] = "success"

                    elif step.action_type == "assert":
                        if step.value == "visible":
                            await page.wait_for_selector(step.selector, state="visible", timeout=5000)
                        step_result["status"] = "success"

                    # Take screenshot after each step
                    screenshot_path = run_dir / f"step_{i+1}.png"
                    await page.screenshot(path=str(screenshot_path))
                    step_result["screenshot"] = f"/artifacts/{run_dir.name}/step_{i+1}.png"

                except Exception as e:
                    step_result["status"] = "failed"
                    step_result["error"] = str(e)
                    screenshot_path = run_dir / f"step_{i+1}_error.png"
                    await page.screenshot(path=str(screenshot_path))
                    step_result["screenshot"] = f"/artifacts/{run_dir.name}/step_{i+1}_error.png"
                    break

                steps_results.append(step_result)

            # Final screenshot
            final_screenshot = run_dir / "final.png"
            await page.screenshot(path=str(final_screenshot))

            return {
                "success": True,
                "steps": steps_results,
                "final_screenshot": f"/artifacts/{run_dir.name}/final.png",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await browser.close()
