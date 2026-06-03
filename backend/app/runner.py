import asyncio
import uuid
from pathlib import Path
from playwright.async_api import async_playwright
from .schemas import GeneratedTest

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


async def run_simple_test(url: str) -> dict:
    """Run a simple Playwright test: navigate and take screenshot."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot_path = ARTIFACTS_DIR / "screenshot.png"
            await page.screenshot(path=str(screenshot_path), full_page=False)

            title = await page.title()
            url_final = page.url

            return {
                "success": True,
                "title": title,
                "url": url_final,
                "screenshot": f"/artifacts/screenshot.png",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await browser.close()


async def run_generated_test(url: str, test: GeneratedTest) -> dict:
    """Run a generated test with screenshots after each step."""
    run_id = str(uuid.uuid4())
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(exist_ok=True)

    steps_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720}
        )
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
                    step_result["screenshot"] = f"/artifacts/{run_id}/step_{i+1}.png"

                except Exception as e:
                    step_result["status"] = "failed"
                    step_result["error"] = str(e)
                    # Screenshot on failure
                    screenshot_path = run_dir / f"step_{i+1}_error.png"
                    await page.screenshot(path=str(screenshot_path))
                    step_result["screenshot"] = f"/artifacts/{run_id}/step_{i+1}_error.png"
                    break

                steps_results.append(step_result)

            # Final screenshot
            final_screenshot = run_dir / "final.png"
            await page.screenshot(path=str(final_screenshot))

            return {
                "success": True,
                "run_id": run_id,
                "description": test.description,
                "steps": steps_results,
                "final_screenshot": f"/artifacts/{run_id}/final.png",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "run_id": run_id,
            }
        finally:
            await browser.close()
