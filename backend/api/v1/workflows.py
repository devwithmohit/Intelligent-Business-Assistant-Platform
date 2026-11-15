from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...schemas import orchestration_schemas as schemas
from ...services import auth_service
from ...services.workflow_service import (
    WorkflowService,
    WorkflowServiceError,
    get_workflow_service,
)

router = APIRouter(
    prefix="/api/v1/workflows",
    tags=["workflows"],
    dependencies=[Depends(auth_service.get_current_user)],
)


def _svc() -> WorkflowService:
    return get_workflow_service()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_workflows(
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """List workflow definitions owned by the authenticated tenant."""
    return await service.list_workflows(user_id=current_user.id)


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_workflow(
    defn: schemas.WorkflowDefinition,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """Create a workflow definition owned by the authenticated tenant."""
    try:
        return await service.create_workflow(defn, user_id=current_user.id)
    except WorkflowServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/instances", response_model=Dict[str, Any])
async def list_instances(
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """List workflow execution instances scoped to the authenticated tenant."""
    return await service.list_instances(user_id=current_user.id)


@router.get("/instances/{instance_id}", response_model=Optional[schemas.WorkflowInstance])
async def get_instance(
    instance_id: str,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """Retrieve details of a workflow instance owned by the authenticated tenant."""
    inst = await service.get_instance(instance_id, user_id=current_user.id)
    if not inst:
        raise HTTPException(status_code=404, detail="instance not found")
    return inst


@router.post("/instances/{instance_id}/snapshot", response_model=Dict[str, Any])
async def snapshot_instance(
    instance_id: str,
    out_dir: Optional[str] = None,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    inst = await service.get_instance(instance_id, user_id=current_user.id)
    if not inst:
        raise HTTPException(status_code=404, detail="instance not found")
    try:
        path = await service.snapshot_instance(instance_id, out_dir)
        return {"snapshot_path": path}
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{name}", response_model=Dict[str, Any])
async def update_workflow(
    name: str,
    defn: schemas.WorkflowDefinition,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """Update a tenant-owned workflow definition."""
    if defn.name != name:
        raise HTTPException(
            status_code=400, detail="definition.name must match path parameter"
        )
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        return await service.update_workflow(defn, user_id=current_user.id)
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    name: str,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """Delete a workflow owned by the authenticated tenant."""
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        await service.delete_workflow(name, user_id=current_user.id)
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{name}", response_model=schemas.WorkflowDefinition)
async def get_workflow(
    name: str,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """Retrieve a workflow definition owned by the authenticated tenant."""
    defn = await service.get_workflow(name, user_id=current_user.id)
    if not defn:
        raise HTTPException(status_code=404, detail="workflow not found")
    return defn


@router.post("/{name}/start", response_model=Dict[str, Any])
async def start_workflow(
    name: str,
    req: schemas.WorkflowStartRequest,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    if req.workflow_name != name:
        raise HTTPException(
            status_code=400, detail="workflow_name in body must match path"
        )
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        instance_id = await service.start(
            workflow_name=name,
            start_node=req.start_node,
            initial_context=req.initial_context,
            metadata=req.metadata,
            user_id=current_user.id,
        )
        return {"instance_id": instance_id}
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{name}/dispatch", response_model=Dict[str, Any])
async def dispatch_workflow_async(
    name: str,
    req: schemas.WorkflowStartRequest,
    timeout: Optional[float] = Query(
        None, description="Maximum execution timeout in seconds"
    ),
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    """
    Dispatch a workflow execution to Celery background task workers asynchronously.
    Returns the job_id immediately without blocking the HTTP request thread.
    """
    if req.workflow_name != name:
        raise HTTPException(
            status_code=400, detail="workflow_name in body must match path"
        )
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        return await service.dispatch_async(
            workflow_name=name,
            start_node=req.start_node,
            user_id=current_user.id,
            initial_context=req.initial_context,
            metadata=req.metadata,
            timeout=timeout,
        )
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{name}/run", response_model=schemas.WorkflowInstance)
async def run_and_wait(
    name: str,
    req: schemas.WorkflowStartRequest,
    timeout: Optional[float] = Query(
        None, description="Seconds to wait for completion"
    ),
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    if req.workflow_name != name:
        raise HTTPException(
            status_code=400, detail="workflow_name in body must match path"
        )
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        return await service.run_and_wait(
            workflow_name=name,
            start_node=req.start_node,
            initial_context=req.initial_context,
            metadata=req.metadata,
            timeout=timeout,
            user_id=current_user.id,
        )
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/visualize", response_model=Dict[str, str])
async def export_visualization(
    name: str,
    out_dir: Optional[str] = None,
    current_user=Depends(auth_service.get_current_user),
    service: WorkflowService = Depends(_svc),
):
    existing = await service.get_workflow(name, user_id=current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="workflow not found")
    try:
        return await service.export_visualization(
            name, out_dir=out_dir, user_id=current_user.id
        )
    except WorkflowServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
