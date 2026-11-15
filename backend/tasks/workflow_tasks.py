from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from ..core import database
from ..core.celery_app import celery_app
from ..services import job_service

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base Celery task that manages job status in PostgreSQL."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("Celery task %s failed: %s", task_id, exc)
        try:
            job_service.update_job_status(
                job_id=task_id,
                status="failed",
                error=str(exc),
            )
        except Exception:
            logger.exception("Failed to mark job %s as failed in DB", task_id)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("Celery task %s retrying due to: %s", task_id, exc)
        try:
            db = database.SessionLocal()
            try:
                job = job_service.get_job(db, task_id)
                current_retries = (job.retry_count + 1) if job else self.request.retries
                job_service.update_job_status(
                    job_id=task_id,
                    status="retrying",
                    error=str(exc),
                    retry_count=current_retries,
                    db=db,
                )
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to mark job %s as retrying in DB", task_id)


@celery_app.task(
    base=DatabaseTask,
    bind=True,
    name="backend.tasks.workflow_tasks.execute_workflow_async",
    max_retries=3,
    default_retry_delay=5,
)
def execute_workflow_async(
    self,
    workflow_name: str,
    start_node: str,
    user_id: int,
    initial_context: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Celery task that executes a multi-step workflow asynchronously.
    Updates the database with execution status, instance_id, and final outputs.
    """
    job_id = getattr(self.request, "id", None) or "local-job-id"
    logger.info("Starting async workflow execution job_id=%s, workflow=%s, user_id=%s", job_id, workflow_name, user_id)

    job_service.update_job_status(job_id=job_id, status="running")

    from ..services.workflow_service import get_workflow_service

    service = get_workflow_service()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            service.run_and_wait(
                workflow_name=workflow_name,
                start_node=start_node,
                initial_context=initial_context,
                metadata=metadata,
                timeout=timeout,
                user_id=user_id,
            )
        )
        job_service.update_job_status(
            job_id=job_id,
            status="completed",
            result=result,
        )
        return result
    except Exception as exc:
        logger.exception("Error executing workflow %s in background job %s", workflow_name, job_id)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        job_service.update_job_status(
            job_id=job_id,
            status="failed",
            error=str(exc),
        )
        raise exc
    finally:
        loop.close()
