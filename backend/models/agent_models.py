from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

if TYPE_CHECKING:
    from .user_models import User

AGENT_STATUS_VALUES = ("idle", "running", "error", "stopped")
AGENT_TYPE_VALUES = (
    "customer_service",
    "sales_research",
    "content_creation",
    "data_analysis",
    "project_management",
)


class Agent(Base):
    """Registered agent runtime record persisted for status and configuration tracking."""

    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(
            f"status IN {AGENT_STATUS_VALUES}",
            name="ck_agents_status_valid",
        ),
        CheckConstraint(
            f"type IN {AGENT_TYPE_VALUES}",
            name="ck_agents_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="idle",
        server_default="idle",
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
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

    creator: Mapped["User | None"] = relationship(
        "User", back_populates="created_agents", foreign_keys=[created_by]
    )
    user: Mapped["User | None"] = relationship(
        "User", back_populates="agents", foreign_keys=[user_id]
    )
