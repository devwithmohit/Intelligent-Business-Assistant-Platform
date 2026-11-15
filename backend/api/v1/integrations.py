from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ...core.encryption import redact_sensitive_values
from ...schemas.integration_schemas import parse_integration_config
from ...services import auth_service
from ...services.integration_manager import (
    IntegrationManager,
    IntegrationManagerError,
    get_integration_manager,
)

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["integrations"],
    dependencies=[Depends(auth_service.get_current_user)],
)


async def _manager() -> IntegrationManager:
    return get_integration_manager()


@router.get("/", summary="List integrations")
async def list_integrations(
    current_user=Depends(auth_service.get_current_user),
    manager: IntegrationManager = Depends(_manager),
) -> Dict[str, Dict[str, Any]]:
    """List integrations owned by the authenticated tenant, with secrets redacted."""
    raw_integrations = await manager.list_integrations(user_id=current_user.id)
    return {
        name: redact_sensitive_values(cfg)
        for name, cfg in raw_integrations.items()
    }


@router.get("/{name}", summary="Get integration config")
async def get_integration(
    name: str,
    current_user=Depends(auth_service.get_current_user),
    manager: IntegrationManager = Depends(_manager),
) -> Dict[str, Any]:
    """Retrieve integration configuration for the authenticated tenant with credentials redacted."""
    cfg = await manager.get_config(name, user_id=current_user.id)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="integration not found",
        )
    return redact_sensitive_values(cfg)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create or update an integration",
)
async def create_integration(
    payload: Dict[str, Any] = Body(...),
    current_user=Depends(auth_service.get_current_user),
    manager: IntegrationManager = Depends(_manager),
):
    """Register an integration owned by the authenticated tenant, encrypting credentials."""
    try:
        parsed = parse_integration_config(payload)
    except Exception:
        parsed = None

    name = payload.get("name") or (
        getattr(parsed, "name", None) if parsed is not None else None
    )
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="integration 'name' is required in payload",
        )

    cfg = payload.copy()
    cfg["name"] = name

    try:
        await manager.register_integration(name, cfg, user_id=current_user.id)
    except IntegrationManagerError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"name": name, "config": redact_sensitive_values(cfg)}


@router.put("/{name}", summary="Update an existing integration")
async def update_integration(
    name: str,
    payload: Dict[str, Any] = Body(...),
    current_user=Depends(auth_service.get_current_user),
    manager: IntegrationManager = Depends(_manager),
):
    """Update a tenant-owned integration, encrypting credentials."""
    existing = await manager.get_config(name, user_id=current_user.id)
    if not existing and not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="integration not found",
        )

    cfg = payload.copy()
    cfg["name"] = name
    try:
        await manager.register_integration(name, cfg, user_id=current_user.id)
    except IntegrationManagerError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return {"name": name, "config": redact_sensitive_values(cfg)}


@router.delete("/{name}", summary="Delete an integration")
async def delete_integration(
    name: str,
    current_user=Depends(auth_service.get_current_user),
    manager: IntegrationManager = Depends(_manager),
):
    """Delete an integration belonging to the authenticated tenant."""
    try:
        deleted = await manager.delete_integration(name, user_id=current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="integration not found",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return {"deleted": True, "name": name}
