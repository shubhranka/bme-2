"""API endpoints for agentic exploration."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.test import ExplorationSession, AgentDecision, DiscoveredPage
from ..exploration import ExplorationManager, ExplorationConfig
from ..workers.agentic_tasks import run_exploration_task


router = APIRouter()


@router.post("/start")
async def start_exploration(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a new agentic exploration session."""
    start_url = request.get("url")
    if not start_url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Create exploration config
    config = ExplorationConfig(
        max_iterations=request.get("max_iterations", 50),
        coverage_threshold=request.get("coverage_threshold", 0.80),
        follow_links=request.get("follow_links", True),
        max_pages=request.get("max_pages", 20)
    )

    # Create exploration session
    session_id = await ExplorationManager.create_session(
        user_id=current_user.id,
        start_url=start_url,
        config=config
    )

    # Enqueue exploration task
    task = run_exploration_task.apply_async(
        args=[session_id, current_user.id, start_url, config.__dict__],
        task_id=session_id
    )

    return {
        "session_id": session_id,
        "task_id": task.id,
        "status": "running",
        "message": "Exploration started"
    }


@router.get("/{session_id}")
async def get_exploration_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get exploration session status."""
    result = await db.execute(
        select(ExplorationSession).where(
            (ExplorationSession.id == session_id) &
            (ExplorationSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Exploration session not found")

    # Get coverage metrics
    coverage = await ExplorationManager.calculate_coverage(session_id)

    return {
        "id": session.id,
        "status": session.status,
        "start_url": session.start_url,
        "max_iterations": session.max_iterations,
        "coverage_threshold": session.coverage_threshold,
        "current_iteration": session.current_iteration,
        "coverage": coverage.__dict__,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None
    }


@router.post("/{session_id}/stop")
async def stop_exploration(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Stop an exploration session."""
    result = await db.execute(
        select(ExplorationSession).where(
            (ExplorationSession.id == session_id) &
            (ExplorationSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Exploration session not found")

    if session.status != "running":
        raise HTTPException(status_code=400, detail="Session is not running")

    # Revoke the Celery task
    from ..celery_app import celery_app
    celery_app.control.revoke(session_id, terminate=True)

    # Mark session as stopped
    await ExplorationManager.stop_session(session_id)

    return {"message": "Exploration stopped"}


@router.get("/{session_id}/coverage")
async def get_exploration_coverage(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed coverage metrics."""
    # Verify ownership
    result = await db.execute(
        select(ExplorationSession).where(
            (ExplorationSession.id == session_id) &
            (ExplorationSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Exploration session not found")

    coverage = await ExplorationManager.calculate_coverage(session_id)

    # Get discovered pages and elements
    pages = await ExplorationManager.get_discovered_pages(session_id)
    decisions = await ExplorationManager.get_agent_decisions(session_id)

    return {
        "coverage": coverage.__dict__,
        "pages": [
            {
                "id": p.id,
                "url": p.url,
                "title": p.title,
                "tested": p.tested,
                "test_count": p.test_count
            }
            for p in pages
        ],
        "recent_decisions": [
            {
                "iteration": d.iteration,
                "decision": d.decision_type,
                "reasoning": d.reasoning,
                "target_id": d.target_id
            }
            for d in decisions[-10:]  # Last 10 decisions
        ]
    }


@router.get("/{session_id}/pages")
async def get_exploration_pages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all discovered pages for an exploration session."""
    # Verify ownership
    result = await db.execute(
        select(ExplorationSession).where(
            (ExplorationSession.id == session_id) &
            (ExplorationSession.user_id == current_user.id)
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Exploration session not found")

    pages = await ExplorationManager.get_discovered_pages(session_id)

    return [
        {
            "id": p.id,
            "url": p.url,
            "title": p.title,
            "page_type": p.page_type,
            "tested": p.tested,
            "test_count": p.test_count,
            "discovered_from": p.discovered_from,
            "discovered_at": p.discovered_at.isoformat() if p.discovered_at else None
        }
        for p in pages
    ]


@router.get("/sessions")
async def list_exploration_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all exploration sessions for the current user."""
    result = await db.execute(
        select(ExplorationSession)
        .where(ExplorationSession.user_id == current_user.id)
        .order_by(ExplorationSession.created_at.desc())
        .limit(20)
    )
    sessions = result.scalars().all()

    return [
        {
            "id": s.id,
            "start_url": s.start_url,
            "status": s.status,
            "coverage_percentage": s.coverage_percentage,
            "current_iteration": s.current_iteration,
            "max_iterations": s.max_iterations,
            "created_at": s.created_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None
        }
        for s in sessions
    ]
