from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.job_schemas import JobRead
from ...services import auth_service, job_service

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(auth_service.get_current_user)],
)


@router.get("/", response_model=List[JobRead])
async def list_jobs(
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    status: Optional[str] = Query(None, description="Filter by status (queued, running, completed, failed)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """List asynchronous background jobs owned by the authenticated tenant."""
    return job_service.list_jobs(
        db=db,
        user_id=current_user.id,
        job_type=job_type,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    current_user=Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve execution status and result of a background job owned by the authenticated tenant."""
    job = job_service.get_job(db=db, job_id=job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or access denied",
        )
    return job
