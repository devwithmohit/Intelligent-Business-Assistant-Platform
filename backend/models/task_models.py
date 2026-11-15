from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .agent_models import AGENT_TYPE_VALUES

if TYPE_CHECKING:
    from .user_models import User

TASK_STATUS_VALUES = ("pending", "in_progress", "done", "cancelled")
TASK_PRIORITY_VALUES = ("low", "medium", "high", "urgent")


class Task(Base):
    """Business task record with optional user assignment and agent linkage."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            f"status IN {TASK_STATUS_VALUES}",
            name="ck_tasks_status_valid",
        ),
        CheckConstraint(
            f"priority IN {TASK_PRIORITY_VALUES}",
            name="ck_tasks_priority_valid",
        ),
        CheckConstraint(
            f"agent_type IS NULL OR agent_type IN {AGENT_TYPE_VALUES}",
            name="ck_tasks_agent_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        default=1,
        server_default="1",
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_instance_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    assignee: Mapped["User | None"] = relationship(
        back_populates="assigned_tasks",
        foreign_keys=[assigned_to],
    )
    creator: Mapped["User"] = relationship(
        back_populates="created_tasks",
        foreign_keys=[created_by],
    )
