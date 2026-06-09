"""Celery tasks for agentic exploration."""
import asyncio
import json
import uuid
import os
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from typing import Dict, Any
from sqlalchemy import select

from ..celery_app import celery_app
from ..exploration import ExplorationManager, ExplorationConfig
from ..agent import TestAgent
from ..workers.tasks import publish_log
from ..models.user import User
from ..models.test import Screenshot, TestRun
from ..discovery import discover_page_structure
from ..llm import generate_test_from_structure
from ..db import async_session


def publish_log(run_id: str, message: Dict):
    """Publish a log message to Redis pub/sub."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.publish(f"logs:{run_id}", json.dumps(message))
    except Exception as e:
        print(f"Failed to publish log: {e}")


async def save_screenshot(session_id: str, image_path: str, description: str, step_index: int = 0):
    """Save screenshot to database."""
    try:
        async with async_session() as db:
            # Create a TestRun record if it doesn't exist (for screenshot storage)
            result = await db.execute(
                select(TestRun).where(TestRun.id == session_id)
            )
            test_run = result.scalar_one_or_none()

            if not test_run:
                test_run = TestRun(
                    id=session_id,
                    test_id=None,
                    status="running",
                    started_at=datetime.utcnow()
                )
                db.add(test_run)
                await db.commit()

            # Save screenshot
            screenshot = Screenshot(
                id=str(uuid.uuid4()),
                run_id=session_id,
                image_path=image_path,
                description=description,
                step_index=step_index,
                timestamp=datetime.utcnow()
            )
            db.add(screenshot)
            await db.commit()

            return screenshot.id
    except Exception as e:
        print(f"Failed to save screenshot: {e}")
        return None


@celery_app.task(bind=True, name="app.workers.agentic.run_exploration_task")
def run_exploration_task(
    self,
    session_id: str,
    user_id: str,
    start_url: str,
    config: Dict[str, Any]
) -> Dict:
    """Main agentic exploration loop (Celery wrapper)."""
    exploration_config = ExplorationConfig(
        max_iterations=config.get("max_iterations", 50),
        coverage_threshold=config.get("coverage_threshold", 0.80),
        follow_links=config.get("follow_links", True),
        max_pages=config.get("max_pages", 20)
    )

    return asyncio.run(_run_exploration(
        session_id=session_id,
        user_id=user_id,
        start_url=start_url,
        config=exploration_config
    ))


async def _run_exploration(
    session_id: str,
    user_id: str,
    start_url: str,
    config: ExplorationConfig
) -> Dict:
    """Async implementation of agentic exploration."""
    publish_log(session_id, {
        "type": "start",
        "message": f"Starting agentic exploration for {start_url}"
    })

    try:
        # Discover the starting page
        publish_log(session_id, {
            "type": "info",
            "message": "Discovering starting page..."
        })

        start_page = await ExplorationManager.discover_page(start_url, session_id)

        publish_log(session_id, {
            "type": "info",
            "message": f"Discovered {start_page.title} with elements"
        })

        # Main exploration loop
        for iteration in range(1, config.max_iterations + 1):
            # Update iteration count
            await ExplorationManager.update_iteration(session_id, iteration)

            # Get current coverage
            coverage = await ExplorationManager.calculate_coverage(session_id)

            publish_log(session_id, {
                "type": "coverage_update",
                "iteration": iteration,
                "coverage": coverage.overall_coverage,
                "message": f"Iteration {iteration}: Coverage {coverage.overall_coverage:.1%}"
            })

            # Agent decides next action
            decision = await TestAgent.decide_next_action(session_id, iteration)

            # Log the decision
            await ExplorationManager.log_decision(
                session_id=session_id,
                iteration=iteration,
                decision_type=decision.decision_type,
                reasoning=decision.reasoning,
                target_id=decision.target_id,
                confidence=decision.confidence
            )

            publish_log(session_id, {
                "type": "agent_decision",
                "iteration": iteration,
                "decision": decision.decision_type,
                "reasoning": decision.reasoning
            })

            # Execute decision
            if decision.decision_type == "stop":
                publish_log(session_id, {
                    "type": "info",
                    "message": f"Stopping: {decision.reasoning}"
                })
                break

            elif decision.decision_type == "test_element":
                result = await _test_element(session_id, decision.target_id)

                publish_log(session_id, {
                    "type": "element_tested",
                    "target_id": decision.target_id,
                    "result": result
                })

            elif decision.decision_type == "explore_page":
                result = await _explore_page(session_id, decision.target_id, config)

                publish_log(session_id, {
                    "type": "page_explored",
                    "target_id": decision.target_id,
                    "result": result
                })

        # Complete the session
        await ExplorationManager.complete_session(session_id)
        final_coverage = await ExplorationManager.calculate_coverage(session_id)

        publish_log(session_id, {
            "type": "complete",
            "message": f"Exploration complete with {final_coverage.overall_coverage:.1%} coverage",
            "coverage": {
                "page_coverage": final_coverage.page_coverage,
                "element_coverage": final_coverage.element_coverage,
                "total_pages": final_coverage.total_pages,
                "tested_pages": final_coverage.tested_pages
            }
        })

        return {
            "success": True,
            "session_id": session_id,
            "coverage": final_coverage.__dict__,
            "message": f"Exploration completed with {final_coverage.overall_coverage:.1%} coverage"
        }

    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"

        publish_log(session_id, {
            "type": "error",
            "message": f"Exploration failed: {str(e)}"
        })

        await ExplorationManager.stop_session(session_id)

        return {
            "success": False,
            "error": error_detail
        }


async def _test_element(session_id: str, element_id: str) -> Dict:
    """Test a specific element."""
    from ..db import async_session
    from ..models.test import DiscoveredElement
    from sqlalchemy import select  # Add this import

    async with async_session() as db:
        result = await db.execute(
            select(DiscoveredElement).where(DiscoveredElement.id == element_id)
        )
        element = result.scalar_one_or_none()

        if not element:
            return {"success": False, "error": "Element not found"}

    # Get the page this element belongs to
    async with async_session() as db:
        from ..models.test import DiscoveredPage
        page_result = await db.execute(
            select(DiscoveredPage).where(DiscoveredPage.id == element.page_id)
        )
        page = page_result.scalar_one_or_none()

    if not page:
        return {"success": False, "error": "Page not found"}

    # Generate a simple test for this element
    test = {
        "name": f"test_{element.element_type}_{element.id[:8]}",
        "description": f"Test {element.element_type} element",
        "steps": [
            {"action_type": "navigate", "selector": page.url},
            {"action_type": "click", "selector": element.selector}
        ]
    }

    # Execute the test
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page_obj = await context.new_page()

            # Navigate to page and take screenshot
            await page_obj.goto(page.url, wait_until="networkidle", timeout=30000)
            await page_obj.wait_for_timeout(1000)  # Wait for page to stabilize

            # Take initial screenshot
            screenshot_path = f"artifacts/{session_id}/before_click_{element_id[:8]}.png"
            await page_obj.screenshot(path=screenshot_path, full_page=False)

            # Save screenshot to database
            await save_screenshot(session_id, screenshot_path, f"Before clicking {element.selector}", 0)

            # Publish screenshot event
            publish_log(session_id, {
                "type": "screenshot",
                "image_path": screenshot_path,
                "description": f"Before clicking {element.selector}",
                "step_index": 0
            })

            # Click the element
            await page_obj.click(element.selector)

            # Take screenshot after click
            screenshot_path_after = f"artifacts/{session_id}/after_click_{element_id[:8]}.png"
            await page_obj.screenshot(path=screenshot_path_after, full_page=False)

            # Save screenshot to database
            await save_screenshot(session_id, screenshot_path_after, f"After clicking {element.selector}", 1)

            # Publish screenshot event
            publish_log(session_id, {
                "type": "screenshot",
                "image_path": screenshot_path_after,
                "description": f"After clicking {element.selector}",
                "step_index": 1
            })

            await browser.close()

        # Update element status
        await ExplorationManager.record_element_test(
            element_id=element_id,
            status="passed"
        )

        return {"success": True, "element_id": element_id}

    except Exception as e:
        # Update element status with failure
        await ExplorationManager.record_element_test(
            element_id=element_id,
            status="failed"
        )

        return {"success": False, "error": str(e), "element_id": element_id}


async def _explore_page(
    session_id: str,
    page_id: str,
    config: ExplorationConfig
) -> Dict:
    """Explore a new page and discover its elements."""
    from ..db import async_session
    from ..models.test import DiscoveredPage
    from sqlalchemy import select  # Add this import

    async with async_session() as db:
        result = await db.execute(
            select(DiscoveredPage).where(DiscoveredPage.id == page_id)
        )
        page = result.scalar_one_or_none()

    if not page:
        return {"success": False, "error": "Page not found"}

    try:
        # Navigate to page and capture initial screenshot
        from playwright.async_api import async_playwright
        import os

        # Ensure artifacts directory exists
        os.makedirs(f"artifacts/{session_id}", exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page_obj = await context.new_page()

            # Navigate to page
            await page_obj.goto(page.url, wait_until="networkidle", timeout=30000)
            await page_obj.wait_for_timeout(1000)

            # Take screenshot of discovered page
            screenshot_path = f"artifacts/{session_id}/page_{page_id[:8]}.png"
            await page_obj.screenshot(path=screenshot_path, full_page=False)

            # Save screenshot to database
            await save_screenshot(session_id, screenshot_path, f"Discovered page: {page.title or page.url}", 0)

            # Publish screenshot event
            publish_log(session_id, {
                "type": "screenshot",
                "image_path": screenshot_path,
                "description": f"Discovered page: {page.title or page.url}",
                "step_index": 0
            })

            await browser.close()

        # Now discover elements on the page
        discovered_page = await ExplorationManager.discover_page(
            page.url,
            session_id
        )

        # Mark page as tested
        await ExplorationManager.mark_page_tested(page_id)

        return {
            "success": True,
            "page_id": page_id,
            "url": page.url,
            "title": discovered_page.title,
            "element_count": len(discovered_page.elements) if hasattr(discovered_page, 'elements') else 0
        }

    except Exception as e:
        return {"success": False, "error": str(e), "page_id": page_id}
