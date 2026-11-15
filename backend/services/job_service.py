from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..core import database
from ..models.job_models import BackgroundJob

logger = logging.getLogger(__name__)


def create_job(
    db: Session,
    job_id: str,
    user_id: int,
    job_type: str,
    payload: dict[str, Any],
    resource_id: Optional[str] = None,
    max_retries: int = 3,
) -> BackgroundJob:
    """Register a new background job record in the database."""
    job = BackgroundJob(
        id=job_id,
        user_id=user_id,
        job_type=job_type,
        status="queued",
        resource_id=resource_id,
        payload=payload,
        max_retries=max_retries,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created background job %s (type=%s, user_id=%s)", job_id, job_type, user_id)
    return job


def get_job(db: Session, job_id: str, user_id: Optional[int] = None) -> Optional[BackgroundJob]:
    """Retrieve a background job, enforcing tenant isolation when user_id is provided."""
    query = db.query(BackgroundJob).filter(BackgroundJob.id == job_id)
    if user_id is not None:
        query = query.filter(BackgroundJob.user_id == user_id)
    return query.first()


def list_jobs(
    db: Session,
    user_id: int,
    job_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[BackgroundJob]:
    """List background jobs for a tenant with optional filtering."""
    query = db.query(BackgroundJob).filter(BackgroundJob.user_id == user_id)
    if job_type:
        query = query.filter(BackgroundJob.job_type == job_type)
    if status:
        query = query.filter(BackgroundJob.status == status)
    return query.order_by(BackgroundJob.created_at.desc()).offset(skip).limit(limit).all()


def update_job_status(
    job_id: str,
    status: str,
    result: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
    retry_count: Optional[int] = None,
    db: Optional[Session] = None,
) -> Optional[BackgroundJob]:
    """Update background job status, result, error, and timestamps."""
    own_session = False
    if db is None:
        db = database.SessionLocal()
        own_session = True

    try:
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        if not job:
            logger.warning("Attempted to update non-existent job %s", job_id)
            return None

        job.status = status
        now = datetime.now(timezone.utc)

        if status == "running" and not job.started_at:
            job.started_at = now
        elif status in ("completed", "failed", "cancelled"):
            job.completed_at = now

        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if retry_count is not None:
            job.retry_count = retry_count

        db.commit()
        db.refresh(job)
        logger.info("Updated job %s status to %s", job_id, status)
        return job
    except Exception:
        db.rollback()
        logger.exception("Failed to update status for job %s", job_id)
        raise
    finally:
        if own_session:
            db.close()
