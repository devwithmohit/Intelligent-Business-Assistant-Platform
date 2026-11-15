from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from ..core import database
from ..core.encryption import decrypt_integration_config, encrypt_integration_config
from ..integrations.calendar.calendar_service import get_calendar_service
from ..integrations.crm.crm_sync_service import get_crm_sync_service
from ..integrations.email.email_service import get_email_service
from ..integrations.messaging.notification_service import get_notification_service
from ..integrations.storage.storage_service import get_storage_service
from ..models.integration_models import Integration
from ..services.kb_manager import get_kb_manager

logger = logging.getLogger(__name__)


class IntegrationManagerError(Exception):
    pass


class TenantConfigDict(dict):
    """
    Dictionary that supports (user_id, name) compound keys while offering
    graceful lookup and pop fallback by integration name for backwards compatibility.
    """

    def pop(self, key: Any, default: Any = None) -> Any:
        if super().__contains__(key):
            return super().pop(key)
        if isinstance(key, str):
            for k in list(self.keys()):
                if isinstance(k, tuple) and len(k) == 2 and k[1] == key:
                    return super().pop(k)
        return default

    def __contains__(self, key: Any) -> bool:
        if super().__contains__(key):
            return True
        if isinstance(key, str):
            return any(
                isinstance(k, tuple) and len(k) == 2 and k[1] == key
                for k in self.keys()
            )
        return False

    def __getitem__(self, key: Any) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        if isinstance(key, str):
            for k, v in self.items():
                if isinstance(k, tuple) and len(k) == 2 and k[1] == key:
                    return v
        raise KeyError(key)


class IntegrationManager:
    """
    Central registry for third-party integrations with multi-tenant isolation
    and encrypted credential storage.
    """

    def __init__(self) -> None:
        # Keyed by (user_id, integration_name)
        self._cfg: TenantConfigDict = TenantConfigDict()
        self._lock = asyncio.Lock()
        self._load_from_db()

    def _load_from_db(self) -> None:
        db = database.SessionLocal()
        try:
            integrations = db.query(Integration).all()
            for integration in integrations:
                # Decrypt stored configuration envelope
                payload = decrypt_integration_config(integration.config)
                payload.setdefault("name", integration.name)
                payload.setdefault("type", integration.type)
                payload.setdefault("enabled", integration.enabled)
                payload.setdefault("user_id", integration.user_id)
                self._cfg[(integration.user_id, integration.name)] = payload
        except Exception:
            logger.exception("Failed to load integrations from database")
        finally:
            db.close()

    def _persist_integration(self, name: str, cfg: Dict[str, Any], user_id: int) -> None:
        db = database.SessionLocal()
        try:
            # Encrypt sensitive configuration before database insertion / update
            encrypted_config = encrypt_integration_config(cfg)
            record = (
                db.query(Integration)
                .filter(Integration.name == name, Integration.user_id == user_id)
                .first()
            )
            if record is None:
                record = Integration(
                    user_id=user_id,
                    name=name,
                    type=(cfg or {}).get("type", "custom"),
                    enabled=(cfg or {}).get("enabled", True),
                    config=encrypted_config,
                )
                db.add(record)
            else:
                record.type = (cfg or {}).get("type", record.type)
                record.enabled = (cfg or {}).get("enabled", record.enabled)
                record.config = encrypted_config
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _delete_persisted_integration(self, name: str, user_id: int) -> None:
        db = database.SessionLocal()
        try:
            record = (
                db.query(Integration)
                .filter(Integration.name == name, Integration.user_id == user_id)
                .first()
            )
            if record is not None:
                db.delete(record)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def register_integration(
        self, name: str, cfg: Dict[str, Any], user_id: int = 1
    ) -> None:
        """
        Register or update a tenant-scoped integration config with credential encryption.
        """
        async with self._lock:
            stored_cfg = dict(cfg or {})
            stored_cfg["name"] = name
            stored_cfg["user_id"] = user_id
            self._cfg[(user_id, name)] = stored_cfg

            try:
                await asyncio.to_thread(
                    self._persist_integration, name, stored_cfg, user_id
                )
            except Exception as exc:
                logger.exception(
                    "Failed to persist integration %s for user %s", name, user_id
                )
                raise IntegrationManagerError(str(exc)) from exc

            provider = (cfg or {}).get("type", "").lower()
            try:
                if provider == "gmail" or provider in ("outlook", "exchange", "ews"):
                    svc = get_email_service()
                    await svc.register_integration(name, cfg)
                elif provider in ("google", "calendar", "google_calendar"):
                    svc = get_calendar_service()
                    await svc.register_integration(name, cfg)
                elif provider in (
                    "google_drive",
                    "onedrive",
                    "storage",
                    "gdrive",
                    "microsoft",
                ):
                    svc = get_storage_service()
                    await svc.register_integration(name, cfg)
                elif provider in ("salesforce", "hubspot", "crm"):
                    svc = get_crm_sync_service()
                    await svc.register_integration(name, cfg)
                elif provider in ("slack", "teams", "msteams", "messaging"):
                    svc = get_notification_service()
                    await svc.register_integration(name, cfg)
                elif provider in ("kb", "chroma", "vector_db"):
                    pass
                else:
                    logger.debug(
                        "register_integration: stored custom provider type=%s name=%s",
                        provider,
                        name,
                    )
            except Exception as exc:
                logger.exception("register_integration hook failed for %s", name)
                raise IntegrationManagerError(str(exc)) from exc

    async def get_config(
        self, name: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve decrypted configuration for an integration, scoped to a tenant user.
        """
        async with self._lock:
            if user_id is not None:
                return self._cfg.get((user_id, name))

            # System fallback search across all tenants
            for (uid, n), cfg in self._cfg.items():
                if n == name:
                    return cfg
            return None

    async def list_integrations(
        self, user_id: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        List integrations scoped to a tenant user.
        """
        async with self._lock:
            if user_id is not None:
                return {
                    name: dict(cfg)
                    for (uid, name), cfg in self._cfg.items()
                    if uid == user_id
                }
            return {name: dict(cfg) for (uid, name), cfg in self._cfg.items()}

    async def delete_integration(self, name: str, user_id: int = 1) -> bool:
        """
        Delete a tenant-owned integration.
        """
        async with self._lock:
            existing = self._cfg.pop((user_id, name), None)
            if existing is None:
                return False
            try:
                await asyncio.to_thread(
                    self._delete_persisted_integration, name, user_id
                )
            except Exception as exc:
                logger.exception("Failed to delete integration %s", name)
                raise IntegrationManagerError(str(exc)) from exc
            return True

    async def get_handler(self, name: str, user_id: Optional[int] = None) -> Any:
        cfg = await self.get_config(name, user_id=user_id)
        if not cfg:
            raise IntegrationManagerError(f"integration not found: {name}")
        provider = (cfg or {}).get("type", "").lower()
        if provider in ("gmail", "outlook", "exchange", "ews"):
            return get_email_service()
        if provider in ("google", "calendar", "google_calendar"):
            return get_calendar_service()
        if provider in ("google_drive", "onedrive", "storage", "gdrive", "microsoft"):
            return get_storage_service()
        if provider in ("salesforce", "hubspot", "crm"):
            return get_crm_sync_service()
        if provider in ("slack", "teams", "msteams", "messaging"):
            return get_notification_service()
        if provider in ("kb", "chroma", "vector_db"):
            return get_kb_manager()
        return cfg


_default_integration_manager: Optional[IntegrationManager] = None


def get_integration_manager() -> IntegrationManager:
    global _default_integration_manager
    if _default_integration_manager is None:
        _default_integration_manager = IntegrationManager()
    return _default_integration_manager


async def register_integration(
    name: str, cfg: Dict[str, Any], user_id: int = 1
) -> None:
    await get_integration_manager().register_integration(name, cfg, user_id=user_id)


async def get_integration_handler(name: str, user_id: Optional[int] = None) -> Any:
    return await get_integration_manager().get_handler(name, user_id=user_id)
