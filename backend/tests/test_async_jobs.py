import os
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.models.user_models import User
from backend.models.job_models import BackgroundJob
from backend.services import job_service
from backend.tasks.workflow_tasks import execute_workflow_async
from backend.tasks.agent_tasks import run_agent_async
from backend.schemas import orchestration_schemas as schemas


TEST_DB_URL = "sqlite:////tmp/test_jobs.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    # Seed test users
    if not db.query(User).filter_by(id=101).first():
        u1 = User(id=101, email="tenant1@example.com", password="hash1", name="Tenant One")
        db.add(u1)
    if not db.query(User).filter_by(id=102).first():
        u2 = User(id=102, email="tenant2@example.com", password="hash2", name="Tenant Two")
        db.add(u2)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("/tmp/test_jobs.db"):
        try:
            os.remove("/tmp/test_jobs.db")
        except Exception:
            pass


@pytest.fixture
def test_db_session(monkeypatch):
    monkeypatch.setattr("backend.core.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("backend.services.job_service.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("backend.tasks.workflow_tasks.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("backend.tasks.agent_tasks.database.SessionLocal", TestingSessionLocal)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_job_service_lifecycle_and_tenant_isolation(test_db_session):
    """Verify background job creation, updating, and strict tenant isolation."""
    job_id = "job-test-101"
    job = job_service.create_job(
        db=test_db_session,
        job_id=job_id,
        user_id=101,
        job_type="workflow_execution",
        resource_id="sample_workflow",
        payload={"start_node": "step_1"},
    )
    assert job.id == job_id
    assert job.user_id == 101
    assert job.status == "queued"

    # User 101 retrieves the job
    retrieved = job_service.get_job(test_db_session, job_id=job_id, user_id=101)
    assert retrieved is not None
    assert retrieved.id == job_id

    # User 102 CANNOT access User 101's job
    denied = job_service.get_job(test_db_session, job_id=job_id, user_id=102)
    assert denied is None, "Security violation: Cross-tenant job leak!"

    # Update job status to running
    updated = job_service.update_job_status(
        job_id=job_id,
        status="running",
        db=test_db_session,
    )
    assert updated.status == "running"
    assert updated.started_at is not None

    # Complete the job with result
    completed = job_service.update_job_status(
        job_id=job_id,
        status="completed",
        result={"output": "success", "steps": 3},
        db=test_db_session,
    )
    assert completed.status == "completed"
    assert completed.result == {"output": "success", "steps": 3}
    assert completed.completed_at is not None


def test_job_service_list_filtering(test_db_session):
    """Verify list_jobs filters by user_id, job_type, and status."""
    j1 = job_service.create_job(
        db=test_db_session,
        job_id="job-list-1",
        user_id=101,
        job_type="workflow_execution",
        payload={},
    )
    j2 = job_service.create_job(
        db=test_db_session,
        job_id="job-list-2",
        user_id=101,
        job_type="agent_run",
        payload={},
    )
    j3 = job_service.create_job(
        db=test_db_session,
        job_id="job-list-3",
        user_id=102,
        job_type="workflow_execution",
        payload={},
    )

    # Tenant 101 list should only contain j1 and j2
    tenant1_jobs = job_service.list_jobs(test_db_session, user_id=101)
    ids = [j.id for j in tenant1_jobs]
    assert "job-list-1" in ids
    assert "job-list-2" in ids
    assert "job-list-3" not in ids

    # Filter by job_type
    filtered = job_service.list_jobs(test_db_session, user_id=101, job_type="agent_run")
    assert len(filtered) == 1
    assert filtered[0].id == "job-list-2"


def test_workflow_async_task_execution(test_db_session, monkeypatch):
    """Verify execute_workflow_async task executes and updates the DB job record."""
    job_id = "job-wf-exec-1"
    job_service.create_job(
        db=test_db_session,
        job_id=job_id,
        user_id=101,
        job_type="workflow_execution",
        resource_id="test_wf",
        payload={},
    )

    async def mock_run_and_wait(self, workflow_name, start_node, initial_context=None, metadata=None, timeout=None, user_id=None):
        return {"workflow_name": workflow_name, "state": "finished", "context": {"step_1": "done"}}

    from backend.services.workflow_service import WorkflowService
    monkeypatch.setattr(WorkflowService, "run_and_wait", mock_run_and_wait)

    # Execute Celery task directly using apply
    res = execute_workflow_async.apply(
        args=["test_wf", "start", 101],
        task_id=job_id,
    ).get()

    assert res["state"] == "finished"
    job = job_service.get_job(test_db_session, job_id=job_id, user_id=101)
    assert job.status == "completed"
    assert job.result["state"] == "finished"


def test_agent_async_task_execution(test_db_session, monkeypatch):
    """Verify run_agent_async task executes and updates the DB job record."""
    job_id = "job-agent-exec-1"
    job_service.create_job(
        db=test_db_session,
        job_id=job_id,
        user_id=101,
        job_type="agent_run",
        resource_id="customer_service",
        payload={},
    )

    async def mock_run_agent(self, agent_type, input_text, user_id, context=None):
        return {"success": True, "output": f"Processed: {input_text}"}

    from backend.services.orchestration_service import OrchestrationService
    monkeypatch.setattr(OrchestrationService, "run_agent", mock_run_agent)

    res = run_agent_async.apply(
        args=["customer_service", "Need refund", 101],
        task_id=job_id,
    ).get()

    assert res["success"] is True
    job = job_service.get_job(test_db_session, job_id=job_id, user_id=101)
    assert job.status == "completed"
    assert job.result["output"] == "Processed: Need refund"


@pytest.mark.asyncio
async def test_workflow_dispatch_async(test_db_session, monkeypatch):
    """Verify workflow_service.dispatch_async registers a job and enqueues Celery task."""
    from backend.services.workflow_service import get_workflow_service
    svc = get_workflow_service()

    # Create dummy workflow in memory for tenant 101
    defn = schemas.WorkflowDefinition(
        name="async_sample",
        agents={"customer_service": {"type": "customer_service"}},
        nodes=[schemas.WorkflowNode(id="start", agent="customer_service")],
        edges=[],
    )
    await svc.create_workflow(defn, user_id=101)

    mock_celery_task = MagicMock()
    mock_celery_task.id = "mock-celery-12345"

    with patch("backend.tasks.workflow_tasks.execute_workflow_async.delay", return_value=mock_celery_task) as mock_delay:
        dispatch_res = await svc.dispatch_async(
            workflow_name="async_sample",
            start_node="start",
            user_id=101,
        )

    assert dispatch_res["job_id"] == "mock-celery-12345"
    assert dispatch_res["status"] == "queued"
    mock_delay.assert_called_once()

    # Verify job is recorded in the DB
    job = job_service.get_job(test_db_session, job_id="mock-celery-12345", user_id=101)
    assert job is not None
    assert job.job_type == "workflow_execution"
    assert job.resource_id == "async_sample"
