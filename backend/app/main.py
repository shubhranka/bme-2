import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db, init_db
from .models.test import Test, TestRun
from .models.user import User
from .api import auth
from .api.deps import get_current_user
from .workers.tasks import run_simple_test_task, generate_and_run_task
from .celery_app import celery_app
from .api.websocket import manager, subscribe_to_logs

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

    # Enqueue Celery task
    task = run_simple_test_task.apply_async(args=[request.url], task_id=run_id)

    return {
        "run_id": run_id,
        "task_id": task.id,
        "status": "running",
        "message": "Test queued for execution"
    }


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

    # Save test configuration if name provided
    if request.name:
        test_id = str(uuid.uuid4())
        test = Test(
            id=test_id,
            name=request.name,
            target_url=request.url,
            generated_code=None  # Will be updated by worker
        )
        db.add(test)
        test_run.test_id = test_id

    await db.commit()

    # Enqueue Celery task
    task = generate_and_run_task.apply_async(
        args=[request.url, request.name],
        task_id=run_id
    )

    return {
        "run_id": run_id,
        "task_id": task.id,
        "test_id": test_run.test_id,
        "status": "running",
        "message": "Test generation and execution queued"
    }


@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    """Get the status of a Celery task."""
    task = celery_app.AsyncResult(task_id)

    if task.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Task is waiting to be processed"
        }
    elif task.state == "PROGRESS":
        return {
            "task_id": task_id,
            "status": "running",
            "message": "Task is being processed"
        }
    elif task.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "completed",
            "result": task.result
        }
    elif task.state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(task.info)
        }
    else:
        return {
            "task_id": task_id,
            "status": task.state.lower()
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


@app.websocket("/api/ws/logs/{run_id}")
async def websocket_logs(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for streaming test execution logs."""
    connection_id = str(uuid.uuid4())

    try:
        await manager.connect(websocket, run_id, connection_id)

        # Stream logs from Redis pub/sub
        async for log_entry in subscribe_to_logs(run_id):
            await manager.broadcast_to_run(run_id, log_entry)

    except WebSocketDisconnect:
        manager.disconnect(run_id, connection_id)
    except Exception as e:
        # Send error message if connection fails
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
        manager.disconnect(run_id, connection_id)


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
