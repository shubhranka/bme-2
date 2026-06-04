from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
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
