from __future__ import annotations

from typing import Any

from passlib.context import CryptContext

from . import jwt as jwt_core

# Canonical password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)


# Canonical re-exports for JWT operations across the application
TokenError = jwt_core.TokenError
create_access_token = jwt_core.create_access_token
create_refresh_token = jwt_core.create_refresh_token
decode_token = jwt_core.decode_token
verify_token = jwt_core.verify_token
get_subject = jwt_core.get_subject
is_token_expired = jwt_core.is_token_expired

__all__ = [
    "TokenError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_password_hash",
    "get_subject",
    "is_token_expired",
    "pwd_context",
    "verify_password",
    "verify_token",
]
