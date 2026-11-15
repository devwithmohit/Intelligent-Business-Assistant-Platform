from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from jose import JWTError, jwt
except ImportError:
    import jwt  # type: ignore
    from jwt.exceptions import PyJWTError as JWTError  # type: ignore

from .config import settings


class TokenError(Exception):
    """Base exception for JWT creation, decoding, and verification errors."""
    pass


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Generate a signed JWT access token.
    Explicitly assigns typ='access' claim to prevent token substitution attacks.
    """
    expires = (
        expires_minutes
        if expires_minutes is not None
        else getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)
    )
    exp_ts = _now_ts() + int(expires * 60)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": _now_ts(),
        "exp": exp_ts,
        "typ": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=getattr(settings, "ALGORITHM", "HS256"),
    )


def create_refresh_token(
    subject: str | int,
    expires_days: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Generate a signed JWT refresh token.
    Explicitly assigns typ='refresh' claim.
    """
    days = (
        expires_days
        if expires_days is not None
        else getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    )
    exp_ts = _now_ts() + int(days * 24 * 60 * 60)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": _now_ts(),
        "exp": exp_ts,
        "typ": "refresh",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=getattr(settings, "ALGORITHM", "HS256"),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify JWT signature and standard claims using configured SECRET_KEY.
    Raises TokenError on signature error, expiration, or invalid formatting.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
        return payload
    except JWTError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc


def get_subject(token: str) -> str | None:
    """Extract the subject (sub) claim from a token."""
    payload = decode_token(token)
    return payload.get("sub")


def is_token_expired(token: str) -> bool:
    """Check whether a token is expired."""
    try:
        payload = decode_token(token)
    except TokenError:
        return True
    exp = payload.get("exp")
    if exp is None:
        return False
    return _now_ts() >= int(exp)


def verify_token(token: str, require_type: str | None = None) -> dict[str, Any]:
    """
    Decode and verify a token, enforcing explicit token type verification when require_type is provided.
    Raises TokenError if the token is invalid or if the token type does not match require_type.
    """
    payload = decode_token(token)
    if require_type is not None:
        typ = payload.get("typ")
        if typ != require_type:
            raise TokenError(
                f"Invalid token type: expected '{require_type}', got '{typ}'"
            )
    return payload
