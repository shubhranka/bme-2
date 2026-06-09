"""Agentic decision engine for autonomous testing."""
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session
from .models.test import DiscoveredPage, DiscoveredElement, ExplorationSession
from .llm import generate_with_llm
from .config import settings


class AgentDecision:
    """Represents an agent's decision."""
    def __init__(
        self,
        decision_type: str,  # test_element, explore_page, stop
        target_id: Optional[str] = None,
        reasoning: str = "",
        confidence: float = 0.8
    ):
        self.decision_type = decision_type
        self.target_id = target_id
        self.reasoning = reasoning
        self.confidence = confidence


class TestAgent:
    """LLM-powered agent that decides what to test next."""

    @staticmethod
    async def decide_next_action(session_id: str, iteration: int) -> AgentDecision:
        """Decide the next action using LLM."""
        async with async_session() as db:
            # Get session info
            session_result = await db.execute(
                select(ExplorationSession).where(ExplorationSession.id == session_id)
            )
            session = session_result.scalar_one_or_none()

            if not session:
                return AgentDecision("stop", reasoning="Session not found")

            # Get discovered pages and elements
            pages_result = await db.execute(
                select(DiscoveredPage).where(
                    DiscoveredPage.session_id == session_id
                ).order_by(DiscoveredPage.discovered_at)
            )
            pages = list(pages_result.scalars().all())

            elements_result = await db.execute(
                select(DiscoveredElement).join(
                    DiscoveredPage,
                    DiscoveredElement.page_id == DiscoveredPage.id
                ).where(DiscoveredPage.session_id == session_id)
            )
            elements = list(elements_result.scalars().all())

            # Calculate coverage
            total_pages = len(pages)
            tested_pages = len([p for p in pages if p.tested])
            total_elements = len(elements)
            tested_elements = len([e for e in elements if e.tested])
            page_coverage = tested_pages / total_pages if total_pages > 0 else 0
            element_coverage = tested_elements / total_elements if total_elements > 0 else 0
            overall_coverage = (page_coverage + element_coverage) / 2

            # Get untested elements and pages
            untested_elements = [e for e in elements if not e.tested][:5]
            untested_pages = [p for p in pages if not p.tested][:3]

            # Optimized decision flow: Try rule-based first, only use LLM for complex cases
            # Rule 1: Stop if coverage threshold reached
            if overall_coverage >= session.coverage_threshold:
                return AgentDecision(
                    "stop",
                    target_id=None,
                    reasoning=f"Coverage threshold {session.coverage_threshold:.1%} reached",
                    confidence=1.0
                )

            # Rule 2: Stop if max iterations reached
            if iteration >= session.max_iterations:
                return AgentDecision(
                    "stop",
                    target_id=None,
                    reasoning=f"Max iterations ({session.max_iterations}) reached",
                    confidence=1.0
                )

            # Rule 3: Test untested elements first (simple rule-based)
            if untested_elements and iteration % 3 != 0:  # Every 3rd iteration goes to LLM
                priority_element = untested_elements[0]
                return AgentDecision(
                    "test_element",
                    target_id=priority_element.id,
                    reasoning=f"Testing element: {priority_element.selector} (rule-based)",
                    confidence=0.8
                )

            # Rule 4: Explore pages if element coverage is high (simple rule-based)
            if element_coverage >= 0.7 and untested_pages and iteration % 3 != 0:
                target = untested_pages[0]
                return AgentDecision(
                    "explore_page",
                    target_id=target.id,
                    reasoning=f"Element coverage {element_coverage:.1%} >= 70%, exploring page (rule-based)",
                    confidence=0.8
                )

            # Build LLM prompt for complex cases (every 3rd iteration or when rules don't apply)
            prompt = TestAgent._build_decision_prompt(
                session=session,
                pages=pages,
                untested_elements=untested_elements,
                untested_pages=untested_pages,
                page_coverage=page_coverage,
                element_coverage=element_coverage,
                overall_coverage=overall_coverage,
                iteration=iteration,
                total_elements=total_elements,  # Pass pre-calculated values
                tested_elements=tested_elements
            )

            # Call LLM with rate limiting
            try:
                # Add small delay to avoid excessive API calls
                import asyncio
                await asyncio.sleep(1)  # 1 second delay between LLM calls

                response = await generate_with_llm(
                    prompt=prompt,
                    response_format="json"
                )

                # Parse response
                import json
                decision_data = json.loads(response)

                decision_type = decision_data.get("decision", "stop")
                target_id = decision_data.get("target_id")
                reasoning = decision_data.get("reasoning", "")
                confidence = decision_data.get("confidence", 0.8)

                # Validate decision type
                if decision_type not in ["test_element", "explore_page", "stop"]:
                    decision_type = "stop"
                    reasoning = f"Invalid decision type: {decision_type}"

                return AgentDecision(decision_type, target_id, reasoning, confidence)

            except Exception as e:
                # Fallback to rule-based decision
                return TestAgent._fallback_decision(
                    untested_elements=untested_elements,
                    untested_pages=untested_pages,
                    element_coverage=element_coverage,
                    session=session
                )

    @staticmethod
    def _build_decision_prompt(
        session: ExplorationSession,
        pages: List[DiscoveredPage],
        untested_elements: List[DiscoveredElement],
        untested_pages: List[DiscoveredPage],
        page_coverage: float,
        element_coverage: float,
        overall_coverage: float,
        iteration: int,
        total_elements: int = 0,
        tested_elements: int = 0
    ) -> str:
        """Build the LLM prompt for decision making."""
        untested_elem_summary = "\n".join([
            f"- {e.element_type}: {e.selector} ({e.text_content[:30] if e.text_content else ''})"
            for e in untested_elements[:3]
        ])

        untested_page_summary = "\n".join([
            f"- {p.title or p.url}: {p.url}"
            for p in untested_pages[:2]
        ])

        return f"""You are an autonomous testing agent. Decide what to do next.

**Current State:**
- Iteration: {iteration}/{session.max_iterations}
- Coverage threshold: {session.coverage_threshold:.1%}
- Pages: {len(pages)} total ({sum(1 for p in pages if p.tested)} tested)
- Elements: {total_elements} total ({tested_elements} tested)
- Page coverage: {page_coverage:.1%}
- Element coverage: {element_coverage:.1%}
- Overall coverage: {overall_coverage:.1%}

**Untested Elements (first 3):**
{untested_elem_summary if untested_elem_summary else "None"}

**Pages to Explore (first 2):**
{untested_page_summary if untested_page_summary else "None"}

**Decision Options:**
1. "test_element" - Test an untested element (high priority)
2. "explore_page" - Navigate to and explore a new page (if current page coverage > 70%)
3. "stop" - Stop exploration (if coverage >= threshold or no valuable actions)

**Your Decision:**
Provide a JSON response with this exact format:
{{
    "decision": "test_element" | "explore_page" | "stop",
    "target_id": "<id of element or page to test/explore>",
    "reasoning": "<clear explanation of why this action>",
    "confidence": 0.0-1.0
}}

Guidelines:
- Prioritize testing critical elements (forms, buttons with CTA text)
- Explore new pages when current page coverage exceeds 70%
- Stop when coverage threshold is reached or no valuable actions remain
- Be conservative - it's better to stop early than to waste resources"""

    @staticmethod
    def _fallback_decision(
        untested_elements: List[DiscoveredElement],
        untested_pages: List[DiscoveredPage],
        element_coverage: float,
        session: ExplorationSession
    ) -> AgentDecision:
        """Fallback rule-based decision if LLM fails."""
        # Rule 1: Test untested elements first
        if untested_elements:
            # Prioritize buttons and forms
            priority_elements = [
                e for e in untested_elements
                if e.element_type in ["button", "input", "form"]
            ]
            target = priority_elements[0] if priority_elements else untested_elements[0]

            return AgentDecision(
                "test_element",
                target_id=target.id,
                reasoning=f"Testing {target.element_type}: {target.selector} (fallback to rule-based decision)"
            )

        # Rule 2: Explore new pages if element coverage is high
        if element_coverage >= 0.7 and untested_pages:
            target = untested_pages[0]
            return AgentDecision(
                "explore_page",
                target_id=target.id,
                reasoning=f"Element coverage {element_coverage:.1%} >= 70%, exploring page: {target.title}"
            )

        # Rule 3: Stop if coverage threshold reached
        if element_coverage >= session.coverage_threshold:
            return AgentDecision(
                "stop",
                reasoning=f"Coverage threshold reached: {element_coverage:.1%} >= {session.coverage_threshold:.1%}"
            )

        # Default: stop
        return AgentDecision("stop", reasoning="No more valuable actions (fallback)")

    @staticmethod
    async def prioritize_elements(
        session_id: str,
        page_id: Optional[str] = None
    ) -> List[DiscoveredElement]:
        """Prioritize elements for testing."""
        async with async_session() as db:
            query = select(DiscoveredElement).join(
                DiscoveredPage,
                DiscoveredElement.page_id == DiscoveredPage.id
            ).where(DiscoveredPage.session_id == session_id)

            if page_id:
                query = query.where(DiscoveredElement.page_id == page_id)

            query = query.where(DiscoveredElement.tested == False)

            result = await db.execute(query)
            elements = list(result.scalars().all())

            # Priority scoring
            def priority_score(element: DiscoveredElement) -> int:
                score = 0
                if element.element_type == "button":
                    score += 10
                elif element.element_type == "input":
                    score += 8
                elif element.element_type == "form":
                    score += 7
                elif element.element_type == "link":
                    score += 5

                if element.text_content:
                    text_lower = element.text_content.lower()
                    if any(word in text_lower for word in ["submit", "login", "sign in", "register", "buy", "checkout"]):
                        score += 5
                    elif any(word in text_lower for word in ["cancel", "close", "back"]):
                        score -= 3

                return score

            return sorted(elements, key=priority_score, reverse=True)

    @staticmethod
    def should_stop_exploration(session: ExplorationSession, coverage: float) -> bool:
        """Determine if exploration should stop."""
        if coverage >= session.coverage_threshold:
            return True

        if session.current_iteration >= session.max_iterations:
            return True

        return False
