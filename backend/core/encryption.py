"""
Credential Encryption Utility
Uses Fernet (AES-128-CBC + HMAC-SHA256) derived deterministically from the application's
SECRET_KEY to encrypt sensitive integration credentials and configuration before persisting
to database, and decrypt securely upon retrieval.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

logger = logging.getLogger(__name__)

# Common keys containing secret / credential material
SENSITIVE_KEY_PATTERNS = {
    "api_key",
    "apikey",
    "secret",
    "client_secret",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "private_key",
    "service_account",
    "credentials",
    "auth_token",
    "bot_token",
    "signing_secret",
    "webhook_secret",
    "webhook_token",
}


def _get_fernet_cipher() -> Fernet:
    """
    Deterministically derive a 32-byte URL-safe base64-encoded key for Fernet
    from the application's configured SECRET_KEY.
    """
    secret = (getattr(settings, "SECRET_KEY", None) or "change-me-super-secret").encode("utf-8")
    derived_32bytes = hashlib.sha256(secret).digest()
    fernet_key = base64.urlsafe_b64encode(derived_32bytes)
    return Fernet(fernet_key)


def encrypt_payload(data: Any) -> str:
    """
    Encrypt a dictionary, list, or string into an encrypted ciphertext string.
    """
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data)
    else:
        serialized = str(data)

    cipher = _get_fernet_cipher()
    return cipher.encrypt(serialized.encode("utf-8")).decode("utf-8")


def decrypt_payload(ciphertext: str) -> Any:
    """
    Decrypt a Fernet ciphertext token back to its original object.
    Attempts JSON deserialization; if not JSON, returns plain string.
    """
    if not ciphertext:
        return {}
    cipher = _get_fernet_cipher()
    try:
        decrypted_bytes = cipher.decrypt(ciphertext.encode("utf-8"))
        decrypted_str = decrypted_bytes.decode("utf-8")
        try:
            return json.loads(decrypted_str)
        except (json.JSONDecodeError, ValueError):
            return decrypted_str
    except InvalidToken:
        logger.error("Failed to decrypt payload: invalid token or SECRET_KEY mismatch")
        raise ValueError("Invalid encryption token or key mismatch")


def encrypt_integration_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Wraps an integration configuration payload in an encrypted envelope before database storage.
    Envelope format: {"_encrypted": True, "ciphertext": "<fernet_token>"}
    """
    if not isinstance(cfg, dict):
        return cfg

    # Prevent double encryption
    if cfg.get("_encrypted") is True and "ciphertext" in cfg:
        return cfg

    ciphertext = encrypt_payload(cfg)
    return {
        "_encrypted": True,
        "ciphertext": ciphertext,
    }


def decrypt_integration_config(cfg: Any) -> dict[str, Any]:
    """
    Unwraps an encrypted integration configuration envelope.
    If the config is not encrypted (e.g. legacy plain records), returns it as-is.
    """
    if not isinstance(cfg, dict):
        return {} if cfg is None else cfg

    if cfg.get("_encrypted") is True and "ciphertext" in cfg:
        try:
            decrypted = decrypt_payload(cfg["ciphertext"])
            if isinstance(decrypted, dict):
                return decrypted
            return {"data": decrypted}
        except Exception:
            logger.exception("Failed to decrypt integration config envelope")
            return {}

    return dict(cfg)


def redact_sensitive_values(data: Any) -> Any:
    """
    Recursively redact sensitive credential values (API keys, client secrets, passwords)
    from dictionaries or lists before returning them to client API endpoints.
    """
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS):
                redacted[key] = "********" if value else ""
            elif isinstance(value, (dict, list)):
                redacted[key] = redact_sensitive_values(value)
            else:
                redacted[key] = value
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_values(item) for item in data]
    return data
