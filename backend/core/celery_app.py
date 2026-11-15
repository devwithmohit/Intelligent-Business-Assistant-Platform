from __future__ import annotations

import logging
import os
from celery import Celery

logger = logging.getLogger(__name__)

# Resolve Redis URL / Celery Broker & Backend from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

celery_app = Celery(
    "iba_worker",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "backend.tasks.workflow_tasks",
        "backend.tasks.agent_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,       # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 min soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=86400,       # Keep task results in backend for 24 hours
)

logger.info(
    "Celery app initialized with broker=%s and backend=%s",
    BROKER_URL,
    RESULT_BACKEND,
)
