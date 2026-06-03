import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .runner import run_simple_test, run_generated_test
from .discovery import discover_page_structure
from .llm import generate_test_from_structure
from .db import get_db, init_db
from .models.test import Test, TestRun, Screenshot
from .models.user import User
from .api import auth
from .api.deps import get_current_user, get_optional_user

app = FastAPI(title="E2E Test Engineer")

# Include auth router
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


# Pydantic models for API requests/responses
class TestRequest(BaseModel):
    url: str
    name: str | None = None


class TestResponse(BaseModel):
    id: str
    name: str
    target_url: str
    generated_code: str | None = None
    created_at: str
    updated_at: str


class RunResponse(BaseModel):
    id: str
    test_id: str | None
    status: str
    started_at: str | None
    completed_at: str | None
    page_title: str | None
    page_url: str | None
    error_message: str | None
    created_at: str


class UserResponse(BaseModel):
    id: str
    email: str


# Startup event - initialize database
@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse(id=current_user.id, email=current_user.email)


@app.post("/api/run")
async def run_test(request: TestRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Run a simple test against the given URL (requires auth)."""
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Create test run record
    run_id = str(uuid.uuid4())
    test_run = TestRun(
        id=run_id,
        test_id=None,
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(test_run)
    await db.commit()

    try:
        # Run the test
        result = await run_simple_test(request.url)

        # Update test run with results
        test_run.status = "passed" if result["success"] else "failed"
        test_run.completed_at = datetime.utcnow()
        test_run.page_title = result.get("title")
        test_run.page_url = result.get("url")
        await db.commit()

        # Add run ID to result
        result["run_id"] = run_id
        return result

    except Exception as e:
        test_run.status = "failed"
        test_run.completed_at = datetime.utcnow()
        test_run.error_message = str(e)
        await db.commit()
        raise


@app.post("/api/generate-and-run")
async def generate_and_run(request: TestRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Generate a test using AI and run it (requires auth)."""
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Create test run record
    run_id = str(uuid.uuid4())
    test_run = TestRun(
        id=run_id,
        test_id=None,
        status="running",
        started_at=datetime.utcnow()
    )
    db.add(test_run)
    await db.commit()

    try:
        # Step 1: Discover page structure
        page_structure = await discover_page_structure(request.url)

        # Step 2: Generate test using LLM
        generated_test = generate_test_from_structure(page_structure)

        # Save test configuration if name provided
        test_id = None
        if request.name:
            test_id = str(uuid.uuid4())
            test = Test(
                id=test_id,
                name=request.name,
                target_url=request.url,
                generated_code=str(generated_test.model_dump_json())
            )
            db.add(test)
            await db.commit()

            # Link test run to test
            test_run.test_id = test_id
            await db.commit()

        # Step 3: Run the generated test
        result = await run_generated_test(request.url, generated_test)

        # Step 4: Save screenshots to database
        if result.get("steps"):
            for i, step in enumerate(result["steps"]):
                if step.get("screenshot"):
                    screenshot = Screenshot(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        image_path=step["screenshot"],
                        description=f"Step {i+1}: {step.get('action', '')}",
                        step_index=i
                    )
                    db.add(screenshot)

        # Update test run with results
        test_run.status = "passed" if result.get("success") else "failed"
        test_run.completed_at = datetime.utcnow()
        test_run.page_title = page_structure.title
        test_run.page_url = page_structure.url
        test_run.video_path = result.get("final_screenshot")
        await db.commit()

        # Add the generated test info to result
        result["run_id"] = run_id
        result["test_id"] = test_id
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
        test_run.status = "failed"
        test_run.completed_at = datetime.utcnow()
        test_run.error_message = str(e)
        await db.commit()
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id
        }


@app.get("/api/tests", response_model=list[TestResponse])
async def list_tests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List all saved tests for the current user."""
    # For now, list all tests (we'll add user_id to Test model later)
    result = await db.execute(select(Test).order_by(Test.created_at.desc()))
    tests = result.scalars().all()

    return [
        TestResponse(
            id=test.id,
            name=test.name,
            target_url=test.target_url,
            generated_code=test.generated_code,
            created_at=test.created_at.isoformat(),
            updated_at=test.updated_at.isoformat()
        )
        for test in tests
    ]


@app.get("/api/tests/{test_id}", response_model=TestResponse)
async def get_test(test_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific test."""
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    return TestResponse(
        id=test.id,
        name=test.name,
        target_url=test.target_url,
        generated_code=test.generated_code,
        created_at=test.created_at.isoformat(),
        updated_at=test.updated_at.isoformat()
    )


@app.get("/api/runs", response_model=list[RunResponse])
async def list_runs(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List all test runs."""
    result = await db.execute(select(TestRun).order_by(TestRun.created_at.desc()).limit(50))
    runs = result.scalars().all()

    return [
        RunResponse(
            id=run.id,
            test_id=run.test_id,
            status=run.status,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            page_title=run.page_title,
            page_url=run.page_url,
            error_message=run.error_message,
            created_at=run.created_at.isoformat()
        )
        for run in runs
    ]


@app.get("/api/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get a specific test run."""
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        id=run.id,
        test_id=run.test_id,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        page_title=run.page_title,
        page_url=run.page_url,
        error_message=run.error_message,
        created_at=run.created_at.isoformat()
    )


@app.get("/artifacts/{file_name}")
async def get_artifact(file_name: str):
    """Serve screenshot files."""
    from pathlib import Path

    artifact_path = Path(__file__).parent.parent / "artifacts" / file_name
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(artifact_path)


@app.get("/artifacts/{run_id}/{file_name}")
async def get_run_artifact(run_id: str, file_name: str):
    """Serve screenshot files from a specific run."""
    from pathlib import Path

    artifact_path = Path(__file__).parent.parent / "artifacts" / run_id / file_name
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(artifact_path)


@app.get("/health")
async def health():
    return {"status": "ok"}
