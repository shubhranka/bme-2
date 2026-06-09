"""API endpoints for test export."""
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.test import ExplorationSession, DiscoveredPage, DiscoveredElement, Test
from ..codegen import PlaywrightCodeGenerator


router = APIRouter()


@router.post("/test-suite/{session_id}")
async def export_test_suite(
    session_id: str,
    format: str = "zip",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export all tests from an exploration session."""
    # Verify session ownership
    result = await db.execute(
        select(ExplorationSession).where(
            (ExplorationSession.id == session_id) &
            (ExplorationSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Exploration session not found")

    # Generate test files
    generator = PlaywrightCodeGenerator()

    # Collect all tests from the exploration
    # For now, we'll create tests from discovered pages
    tests = await _collect_tests_from_session(session_id, db)

    if format == "zip":
        files = generator.generate_test_suite(tests, f"session_{session_id[:8]}")

        # Create temporary directory for ZIP
        export_dir = f"/tmp/exports/{session_id}"
        os.makedirs(export_dir, exist_ok=True)

        zip_path = generator.create_zip_archive(files, export_dir)

        return FileResponse(
            zip_path,
            filename=f"test_suite_{session_id[:8]}.zip",
            media_type="application/zip"
        )

    elif format == "preview":
        # Return preview of first test
        if tests:
            preview_code = generator.generate_test_file(tests[0])
            return {
                "preview": preview_code,
                "test_count": len(tests)
            }

    raise HTTPException(status_code=400, detail="Invalid export format")


@router.post("/single/{test_id}")
async def export_single_test(
    test_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Export a single test as Python file."""
    result = await db.execute(
        select(Test).where(
            (Test.id == test_id) &
            (Test.user_id == current_user.id)
        )
    )
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    # Parse the generated code
    import json
    try:
        if test.generated_code:
            test_data = json.loads(test.generated_code)
        else:
            test_data = {
                "name": test.name,
                "description": f"Test for {test.target_url}",
                "steps": []
            }
    except:
        test_data = {
            "name": test.name,
            "description": f"Test for {test.target_url}",
            "steps": []
        }

    generator = PlaywrightCodeGenerator()
    code = generator.generate_test_file(test_data)

    from fastapi.responses import Response
    return Response(
        content=code,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=test_{test_id[:8]}.py"
        }
    )


async def _collect_tests_from_session(
    session_id: str,
    db: AsyncSession
) -> list:
    """Collect all tests from an exploration session."""
    tests = []

    # Get all discovered pages
    pages_result = await db.execute(
        select(DiscoveredPage).where(
            DiscoveredPage.session_id == session_id
        )
    )
    pages = pages_result.scalars().all()

    # For each page, create a test
    for page in pages:
        # Get elements for this page
        elements_result = await db.execute(
            select(DiscoveredElement).where(
                DiscoveredElement.page_id == page.id
            )
        )
        elements = elements_result.scalars().all()

        # Create test steps from tested elements
        steps = [
            {
                "action_type": "navigate",
                "selector": page.url,
                "description": f"Navigate to {page.title or page.url}",
                "value": None
            }
        ]

        # Add tested elements as test steps
        for element in elements:
            if element.tested and element.test_status == "passed":
                steps.append({
                    "action_type": "click",
                    "selector": element.selector,
                    "description": f"Click {element.element_type}",
                    "value": None
                })

        if len(steps) > 1:  # At least navigate + one action
            tests.append({
                "name": f"test_{page.title or 'page'}_{page.id[:8]}",
                "description": f"Test coverage for {page.title or page.url}",
                "steps": steps
            })

    return tests
