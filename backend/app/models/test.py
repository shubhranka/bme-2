from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base


class Test(Base):
    """Test configuration model."""
    __tablename__ = "tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    target_url: Mapped[str] = mapped_column(Text)
    generated_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TestRun(Base):
    """Test run history model."""
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    test_id: Mapped[str] = mapped_column(String(36), nullable=True)  # Nullable for one-off runs
    status: Mapped[str] = mapped_column(String(50))  # pending, running, passed, failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    video_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Screenshot(Base):
    """Screenshot model for test runs."""
    __tablename__ = "screenshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36))
    image_path: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_index: Mapped[int] = mapped_column(Integer, default=0)


class ExplorationSession(Base):
    """Agentic exploration session model."""
    __tablename__ = "exploration_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    start_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50))  # running, completed, stopped
    max_iterations: Mapped[int] = mapped_column(Integer, default=50)
    coverage_threshold: Mapped[float] = mapped_column(Numeric(3, 2), default=0.80)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0)
    coverage_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    pages = relationship("DiscoveredPage", back_populates="session", cascade="all, delete-orphan")
    decisions = relationship("AgentDecision", back_populates="session", cascade="all, delete-orphan")
    test_suites = relationship("TestSuite", back_populates="session", cascade="all, delete-orphan")


class DiscoveredPage(Base):
    """Discovered page during exploration."""
    __tablename__ = "discovered_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("exploration_sessions.id"))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # login, dashboard, form, etc.
    tested: Mapped[bool] = mapped_column(Integer, default=0)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    discovered_from: Mapped[str | None] = mapped_column(String(36), ForeignKey("discovered_pages.id"), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ExplorationSession", back_populates="pages")
    elements = relationship("DiscoveredElement", back_populates="page", cascade="all, delete-orphan")
    parent_page = relationship("DiscoveredPage", remote_side="DiscoveredPage.id")


class DiscoveredElement(Base):
    """Discovered interactive element."""
    __tablename__ = "discovered_elements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    page_id: Mapped[str] = mapped_column(String(36), ForeignKey("discovered_pages.id"))
    selector: Mapped[str] = mapped_column(Text)
    element_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # button, input, link, etc.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tested: Mapped[bool] = mapped_column(Integer, default=0)
    test_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # passed, failed, skipped
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    page = relationship("DiscoveredPage", back_populates="elements")


class AgentDecision(Base):
    """Agent decision log for transparency."""
    __tablename__ = "agent_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("exploration_sessions.id"))
    iteration: Mapped[int] = mapped_column(Integer)
    decision_type: Mapped[str] = mapped_column(String(50))  # test_element, explore_page, stop
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # element_id or page_id
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    made_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ExplorationSession", back_populates="decisions")


class TestSuite(Base):
    """Test suite for export."""
    __tablename__ = "test_suites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("exploration_sessions.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_count: Mapped[int] = mapped_column(Integer, default=0)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("ExplorationSession", back_populates="test_suites")
