"""Exploration state management for agentic testing."""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session
from .models.test import (
    ExplorationSession, DiscoveredPage, DiscoveredElement,
    AgentDecision, Test
)
try:
    from .discovery import discover_page_structure, DOMElement
except ImportError:
    # If discovery module doesn't exist yet, we'll define fallback
    pass


class ExplorationConfig:
    """Configuration for exploration sessions."""
    def __init__(
        self,
        max_iterations: int = 50,
        coverage_threshold: float = 0.80,
        follow_links: bool = True,
        max_pages: int = 20,
        timeout: int = 30000
    ):
        self.max_iterations = max_iterations
        self.coverage_threshold = coverage_threshold
        self.follow_links = follow_links
        self.max_pages = max_pages
        self.timeout = timeout


class CoverageMetrics:
    """Coverage metrics for an exploration session."""
    def __init__(
        self,
        page_coverage: float,
        element_coverage: float,
        total_pages: int,
        tested_pages: int,
        total_elements: int,
        tested_elements: int
    ):
        self.page_coverage = page_coverage
        self.element_coverage = element_coverage
        self.total_pages = total_pages
        self.tested_pages = tested_pages
        self.total_elements = total_elements
        self.tested_elements = tested_elements
        self.overall_coverage = (page_coverage + element_coverage) / 2


class NextAction:
    """Next action for the agent to take."""
    def __init__(
        self,
        action_type: str,  # test_element, explore_page, stop
        target_id: Optional[str] = None,
        reasoning: str = ""
    ):
        self.action_type = action_type
        self.target_id = target_id
        self.reasoning = reasoning


class ExplorationManager:
    """Manages exploration session state and coverage tracking."""

    @staticmethod
    async def create_session(
        user_id: str,
        start_url: str,
        config: ExplorationConfig
    ) -> str:
        """Create a new exploration session."""
        async with async_session() as db:
            session_id = str(uuid.uuid4())
            exploration_session = ExplorationSession(
                id=session_id,
                user_id=user_id,
                start_url=start_url,
                status="running",
                max_iterations=config.max_iterations,
                coverage_threshold=config.coverage_threshold
            )
            db.add(exploration_session)
            await db.commit()
            await db.refresh(exploration_session)
            return session_id

    @staticmethod
    async def get_session(session_id: str) -> Optional[ExplorationSession]:
        """Get exploration session by ID."""
        async with async_session() as db:
            result = await db.execute(
                select(ExplorationSession).where(ExplorationSession.id == session_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def discover_page(url: str, session_id: str) -> DiscoveredPage:
        """Discover a page and record its elements."""
        # First, discover page structure using existing discovery
        page_structure = await discover_page_structure(url)

        async with async_session() as db:
            # Check if page already discovered
            existing = await db.execute(
                select(DiscoveredPage).where(
                    (DiscoveredPage.session_id == session_id) &
                    (DiscoveredPage.url == url)
                )
            )
            existing_page = existing.scalar_one_or_none()

            if existing_page:
                return existing_page

            # Create new discovered page
            page_id = str(uuid.uuid4())
            discovered_page = DiscoveredPage(
                id=page_id,
                session_id=session_id,
                url=url,
                title=page_structure.title,
                discovered_at=datetime.utcnow()
            )
            db.add(discovered_page)
            await db.flush()

            # Record discovered elements
            for element in page_structure.elements:
                discovered_element = DiscoveredElement(
                    id=str(uuid.uuid4()),
                    page_id=page_id,
                    selector=element.selector,
                    element_type=element.tag,
                    text_content=element.text,
                    discovered_at=datetime.utcnow()
                )
                db.add(discovered_element)

            await db.commit()
            await db.refresh(discovered_page)
            return discovered_page

    @staticmethod
    async def record_element_test(
        element_id: str,
        status: str,
        error_message: str = None
    ):
        """Record element test result."""
        async with async_session() as db:
            result = await db.execute(
                select(DiscoveredElement).where(DiscoveredElement.id == element_id)
            )
            element = result.scalar_one_or_none()

            if element:
                element.tested = True
                element.test_status = status
                await db.commit()

    @staticmethod
    async def mark_page_tested(page_id: str):
        """Mark a page as having been tested."""
        async with async_session() as db:
            result = await db.execute(
                select(DiscoveredPage).where(DiscoveredPage.id == page_id)
            )
            page = result.scalar_one_or_none()

            if page:
                page.tested = True
                page.test_count += 1
                await db.commit()

    @staticmethod
    async def calculate_coverage(session_id: str) -> CoverageMetrics:
        """Calculate test coverage metrics."""
        from sqlalchemy import select  # Ensure select is available in this scope

        async with async_session() as db:
            # Get pages
            pages_result = await db.execute(
                select(DiscoveredPage).where(DiscoveredPage.session_id == session_id)
            )
            pages = pages_result.scalars().all()

            # Get elements
            elements_result = await db.execute(
                select(DiscoveredElement).join(
                    DiscoveredPage,
                    DiscoveredElement.page_id == DiscoveredPage.id
                ).where(DiscoveredPage.session_id == session_id)
            )
            elements = elements_result.scalars().all()

            total_pages = len(pages)
            tested_pages = len([p for p in pages if p.tested])
            total_elements = len(elements)
            tested_elements = len([e for e in elements if e.tested])

            page_coverage = tested_pages / total_pages if total_pages > 0 else 0
            element_coverage = tested_elements / total_elements if total_elements > 0 else 0

            return CoverageMetrics(
                page_coverage=page_coverage,
                element_coverage=element_coverage,
                total_pages=total_pages,
                tested_pages=tested_pages,
                total_elements=total_elements,
                tested_elements=tested_elements
            )

    @staticmethod
    async def get_next_action(session_id: str, config: ExplorationConfig) -> NextAction:
        """Determine the next action for the agent."""
        from sqlalchemy import select  # Ensure select is available in this scope

        coverage = await ExplorationManager.calculate_coverage(session_id)
        session = await ExplorationManager.get_session(session_id)

        if not session:
            return NextAction("stop", reasoning="Session not found")

        # Check if we should stop
        if coverage.overall_coverage >= session.coverage_threshold:
            return NextAction(
                "stop",
                reasoning=f"Coverage threshold reached: {coverage.overall_coverage:.1%} >= {session.coverage_threshold:.1%}"
            )

        if session.current_iteration >= session.max_iterations:
            return NextAction(
                "stop",
                reasoning=f"Max iterations reached: {session.current_iteration}/{session.max_iterations}"
            )

        # Get untested elements
        async with async_session() as db:
            elements_result = await db.execute(
                select(DiscoveredElement).join(
                    DiscoveredPage,
                    DiscoveredElement.page_id == DiscoveredPage.id
                ).where(
                    (DiscoveredPage.session_id == session_id) &
                    (DiscoveredElement.tested == False)
                ).limit(10)
            )
            untested_elements = elements_result.scalars().all()

            if untested_elements:
                # Prioritize testing untested elements
                return NextAction(
                    "test_element",
                    target_id=untested_elements[0].id,
                    reasoning=f"Found {len(untested_elements)} untested elements, testing {untested_elements[0].element_type}"
                )

        # If current page coverage is high, explore new pages
        if coverage.element_coverage >= 0.7 and config.follow_links:
            async with async_session() as db:
                pages_result = await db.execute(
                    select(DiscoveredPage).where(
                        (DiscoveredPage.session_id == session_id) &
                        (DiscoveredPage.tested == False)
                    ).limit(1)
                )
                untested_pages = pages_result.scalars().all()

                if untested_pages:
                    return NextAction(
                        "explore_page",
                        target_id=untested_pages[0].id,
                        reasoning=f"Element coverage {coverage.element_coverage:.1%} >= 70%, exploring new page: {untested_pages[0].title}"
                    )

        # No more valuable actions
        return NextAction("stop", reasoning="No more valuable actions to take")

    @staticmethod
    async def log_decision(
        session_id: str,
        iteration: int,
        decision_type: str,
        reasoning: str,
        target_id: str = None,
        confidence: float = None
    ):
        """Log an agent decision."""
        async with async_session() as db:
            decision = AgentDecision(
                id=str(uuid.uuid4()),
                session_id=session_id,
                iteration=iteration,
                decision_type=decision_type,
                reasoning=reasoning,
                target_id=target_id,
                confidence=confidence,
                made_at=datetime.utcnow()
            )
            db.add(decision)
            await db.commit()

    @staticmethod
    async def update_iteration(session_id: str, iteration: int):
        """Update the current iteration count."""
        async with async_session() as db:
            result = await db.execute(
                select(ExplorationSession).where(ExplorationSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session:
                session.current_iteration = iteration
                await db.commit()

    @staticmethod
    async def complete_session(session_id: str):
        """Mark an exploration session as completed."""
        async with async_session() as db:
            result = await db.execute(
                select(ExplorationSession).where(ExplorationSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session:
                session.status = "completed"
                session.completed_at = datetime.utcnow()
                coverage = await ExplorationManager.calculate_coverage(session_id)
                session.coverage_percentage = coverage.overall_coverage
                await db.commit()

    @staticmethod
    async def stop_session(session_id: str):
        """Stop an exploration session."""
        async with async_session() as db:
            result = await db.execute(
                select(ExplorationSession).where(ExplorationSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session:
                session.status = "stopped"
                session.completed_at = datetime.utcnow()
                coverage = await ExplorationManager.calculate_coverage(session_id)
                session.coverage_percentage = coverage.overall_coverage
                await db.commit()

    @staticmethod
    async def get_discovered_pages(session_id: str) -> List[DiscoveredPage]:
        """Get all discovered pages for a session."""
        async with async_session() as db:
            result = await db.execute(
                select(DiscoveredPage).where(
                    DiscoveredPage.session_id == session_id
                ).order_by(DiscoveredPage.discovered_at)
            )
            return list(result.scalars().all())

    @staticmethod
    async def get_agent_decisions(session_id: str) -> List[AgentDecision]:
        """Get all agent decisions for a session."""
        async with async_session() as db:
            result = await db.execute(
                select(AgentDecision).where(
                    AgentDecision.session_id == session_id
                ).order_by(AgentDecision.made_at)
            )
            return list(result.scalars().all())
