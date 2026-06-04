from datetime import datetime
import uuid
import json
from pathlib import Path
from playwright.async_api import async_playwright
import redis
import asyncio

from ..celery_app import celery_app
from ..discovery import discover_page_structure
from ..llm import generate_test_from_structure
from ..schemas import GeneratedTest
from ..db import async_session
from ..models.test import Screenshot

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)


async def save_screenshot_to_db(run_id: str, image_path: str, step_index: int, description: str = None):
    """Save a screenshot record to the database."""
    async with async_session() as db:
        screenshot = Screenshot(
            id=str(uuid.uuid4()),
            run_id=run_id,
            image_path=image_path,
            timestamp=datetime.utcnow(),
            description=description,
            step_index=step_index
        )
        db.add(screenshot)
        await db.commit()


async def update_run_status(run_id: str, status: str, page_title: str = None, page_url: str = None, error_message: str = None):
    """Update test run status in the database."""
    from sqlalchemy import select, update
    from ..models.test import TestRun

    print(f"update_run_status called: run_id={run_id}, status={status}")

    async with async_session() as db:
        result = await db.execute(select(TestRun).where(TestRun.id == run_id))
        test_run = result.scalar_one_or_none()

        if test_run:
            print(f"Found test_run, updating status to {status}")
            test_run.status = status
            if page_title:
                test_run.page_title = page_title
            if page_url:
                test_run.page_url = page_url
            if error_message:
                test_run.error_message = error_message
            if status in ["passed", "failed"]:
                test_run.completed_at = datetime.utcnow()

            await db.commit()
            print(f"Database updated successfully")
        else:
            print(f"Test run not found: {run_id}")


def publish_log(run_id: str, message: dict):
    """Publish a log message to Redis pub/sub."""
    try:
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.publish(f"logs:{run_id}", json.dumps(message))
    except Exception as e:
        print(f"Failed to publish log: {e}")


@celery_app.task(bind=True, name="app.workers.tasks.run_simple_test_task")
def run_simple_test_task(self, url: str) -> dict:
    """Run a simple Playwright test (Celery wrapper)."""
    import asyncio

    # Get task ID as run_id
    run_id = self.request.id

    # Publish start message
    publish_log(run_id, {
        "type": "start",
        "message": f"Starting test for {url}"
    })

    result = asyncio.run(_run_simple_test(url, run_id))

    # Update database status
    asyncio.run(update_run_status(
        run_id=run_id,
        status="passed" if result.get("success") else "failed",
        page_title=result.get("title"),
        page_url=result.get("url"),
        error_message=result.get("error")
    ))

    # Publish completion message
    publish_log(run_id, {
        "type": "complete",
        "message": "Test completed",
        "success": result.get("success")
    })

    return result


async def _run_simple_test(url: str, run_id: str) -> dict:
    """Async implementation of simple test."""
    publish_log(run_id, {
        "type": "info",
        "message": "Launching browser"
    })

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            publish_log(run_id, {
                "type": "info",
                "message": f"Navigating to {url}"
            })

            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot_path = ARTIFACTS_DIR / f"simple_{uuid.uuid4()}.png"
            await page.screenshot(path=str(screenshot_path))
            image_url = f"/artifacts/{screenshot_path.name}"

            # Save screenshot to database
            await save_screenshot_to_db(
                run_id=run_id,
                image_path=image_url,
                step_index=0,
                description="Initial page load"
            )

            title = await page.title()
            url_final = page.url

            publish_log(run_id, {
                "type": "success",
                "message": f"Page loaded: {title}"
            })

            return {
                "success": True,
                "title": title,
                "url": url_final,
                "screenshot": image_url,
            }
        except Exception as e:
            publish_log(run_id, {
                "type": "error",
                "message": f"Test failed: {str(e)}"
            })
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await browser.close()
            publish_log(run_id, {
                "type": "info",
                "message": "Browser closed"
            })


@celery_app.task(bind=True, name="app.workers.tasks.generate_and_run_task")
def generate_and_run_task(self, url: str, name: str | None = None) -> dict:
    """Generate and run an AI test (Celery wrapper)."""
    import asyncio

    run_id = self.request.id

    publish_log(run_id, {
        "type": "start",
        "message": f"Starting AI-generated test for {url}"
    })

    result = asyncio.run(_generate_and_run(url, name, run_id))

    # Update database status
    asyncio.run(update_run_status(
        run_id=run_id,
        status="passed" if result.get("success") else "failed",
        page_title=result.get("title"),
        page_url=result.get("url"),
        error_message=result.get("error")
    ))

    publish_log(run_id, {
        "type": "complete",
        "message": "Test generation and execution completed",
        "success": result.get("success")
    })

    return result


async def _generate_and_run(url: str, name: str | None, run_id: str) -> dict:
    """Async implementation of generate and run."""
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(exist_ok=True)

    try:
        # Step 1: Discover page structure
        publish_log(run_id, {
            "type": "info",
            "message": "Discovering page structure..."
        })

        page_structure = await discover_page_structure(url)

        publish_log(run_id, {
            "type": "info",
            "message": f"Found {len(page_structure.elements)} interactive elements"
        })

        # Step 2: Generate test using LLM
        publish_log(run_id, {
            "type": "info",
            "message": "Generating test with AI..."
        })

        generated_test = generate_test_from_structure(page_structure)

        publish_log(run_id, {
            "type": "info",
            "message": f"Generated test with {len(generated_test.steps)} steps"
        })

        # Step 3: Run the generated test
        result = await _run_generated_test(url, generated_test, run_dir, run_id)

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
        publish_log(run_id, {
            "type": "error",
            "message": f"Test failed: {str(e)}"
        })
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id
        }


async def _run_generated_test(url: str, test: GeneratedTest, run_dir: Path, run_id: str) -> dict:
    """Run a generated test with screenshots."""
    steps_results = []

    publish_log(run_id, {
        "type": "info",
        "message": "Starting test execution"
    })

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            for i, step in enumerate(test.steps):
                step_result = {"action": step.action_type, "selector": step.selector}

                publish_log(run_id, {
                    "type": "step_start",
                    "step_number": i + 1,
                    "action": step.action_type,
                    "selector": step.selector,
                    "message": f"Step {i+1}: {step.action_type} on {step.selector}"
                })

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
                    image_url = f"/artifacts/{run_dir.name}/step_{i+1}.png"
                    step_result["screenshot"] = image_url

                    # Save to database
                    await save_screenshot_to_db(
                        run_id=run_id,
                        image_path=image_url,
                        step_index=i,
                        description=f"Step {i+1}: {step.action_type}"
                    )

                    # Publish screenshot event for real-time updates
                    publish_log(run_id, {
                        "type": "screenshot",
                        "step_number": i + 1,
                        "image_path": image_url,
                        "description": f"Step {i+1}: {step.action_type}",
                        "step_index": i
                    })

                    publish_log(run_id, {
                        "type": "step_complete",
                        "step_number": i + 1,
                        "status": "success",
                        "message": f"Step {i+1} completed"
                    })

                except Exception as e:
                    step_result["status"] = "failed"
                    step_result["error"] = str(e)
                    screenshot_path = run_dir / f"step_{i+1}_error.png"
                    await page.screenshot(path=str(screenshot_path))
                    image_url = f"/artifacts/{run_dir.name}/step_{i+1}_error.png"
                    step_result["screenshot"] = image_url

                    # Save error screenshot to database
                    await save_screenshot_to_db(
                        run_id=run_id,
                        image_path=image_url,
                        step_index=i,
                        description=f"Step {i+1} error: {str(e)}"
                    )

                    publish_log(run_id, {
                        "type": "step_complete",
                        "step_number": i + 1,
                        "status": "failed",
                        "message": f"Step {i+1} failed: {str(e)}"
                    })

                    break

                steps_results.append(step_result)

            # Final screenshot
            final_screenshot = run_dir / "final.png"
            await page.screenshot(path=str(final_screenshot))
            final_image_url = f"/artifacts/{run_dir.name}/final.png"

            # Save final screenshot to database
            await save_screenshot_to_db(
                run_id=run_id,
                image_path=final_image_url,
                step_index=len(test.steps),
                description="Final state"
            )

            publish_log(run_id, {
                "type": "info",
                "message": "Test execution completed"
            })

            return {
                "success": True,
                "steps": steps_results,
                "final_screenshot": final_image_url,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            await browser.close()
