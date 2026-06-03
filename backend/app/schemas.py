from pydantic import BaseModel
from typing import Literal


class TestAction(BaseModel):
    """A single test action (click, fill, navigate, assert)."""
    action_type: Literal["navigate", "click", "fill", "assert", "wait"]
    selector: str
    value: str | None = None
    description: str | None = None


class GeneratedTest(BaseModel):
    """A complete generated test with steps."""
    description: str
    steps: list[TestAction]


class LLMRequest(BaseModel):
    """Request to LLM for test generation."""
    page_url: str
    page_title: str
    dom_elements: list[dict]


class LLMResponse(BaseModel):
    """Response from LLM with generated test."""
    test: GeneratedTest
