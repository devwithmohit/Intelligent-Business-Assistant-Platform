from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from celery import Task
from ..core import database
from ..core.celery_app import celery_app
from ..services import job_service

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="backend.tasks.agent_tasks.run_agent_async",
    max_retries=3,
    default_retry_delay=5,
)
def run_agent_async(
    self,
    agent_type: str,
    input_text: str,
    user_id: int,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Celery task that executes an agent task asynchronously.
    Updates the database with execution status, output, and errors.
    """
    job_id = getattr(self.request, "id", None) or "local-job-id"
    logger.info("Starting async agent run job_id=%s, agent_type=%s, user_id=%s", job_id, agent_type, user_id)

    job_service.update_job_status(job_id=job_id, status="running")

    from ..services.orchestration_service import get_orchestration_service

    service = get_orchestration_service()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            service.run_agent(
                agent_type=agent_type,
                input_text=input_text,
                user_id=user_id,
                context=context or {},
            )
        )
        if result.get("success"):
            job_service.update_job_status(
                job_id=job_id,
                status="completed",
                result=result,
            )
        else:
            job_service.update_job_status(
                job_id=job_id,
                status="failed",
                error=result.get("error") or "Agent execution failed",
                result=result,
            )
        return result
    except Exception as exc:
        logger.exception("Error running agent %s in background job %s", agent_type, job_id)
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
