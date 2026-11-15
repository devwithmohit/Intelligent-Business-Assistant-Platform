import typing as t
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..core import config
from ..core import jwt as jwt_core
from ..core import security as security_core
from ..schemas import auth_schemas, user_schemas
from . import user_service

SETTINGS = config.settings

pwd_context = security_core.pwd_context
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthError(Exception):
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return security_core.verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return security_core.get_password_hash(password)


def _create_access_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    expires_minutes = (
        int(expires_delta.total_seconds() / 60)
        if expires_delta is not None
        else SETTINGS.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt_core.create_access_token(
        subject=str(subject), expires_minutes=expires_minutes
    )


def _create_refresh_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    expires_days = (
        int(expires_delta.total_seconds() / 86400)
        if expires_delta is not None
        else getattr(SETTINGS, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    )
    return jwt_core.create_refresh_token(
        subject=str(subject), expires_days=expires_days
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt_core.decode_token(token)
    except jwt_core.TokenError as e:
        raise AuthError(str(e)) from e


async def _create_token_response_for_user(user: t.Any) -> dict:
    """
    Returns dict compatible with TokenResponse schema.
    `user` can be ORM model or dict; Pydantic TokenResponse.user uses UserRead with orm_mode.
    """
    subject = getattr(user, "id", None) or getattr(user, "email", None)
    if subject is None:
        raise AuthError("Cannot create token for user without id/email")

    access_token = _create_access_token(subject=str(subject))
    refresh_token = _create_refresh_token(subject=str(subject))

    # compute expiry seconds
    expires_in = int(SETTINGS.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "user": user,
    }


async def login(email: str, password: str) -> auth_schemas.TokenResponse:
    user = await user_service.get_user_by_email(email)
    if not user:
        raise AuthError("Invalid credentials")

    hashed = getattr(user, "password", None)
    if not hashed or not verify_password(password, hashed):
        raise AuthError("Invalid credentials")

    if getattr(user, "is_active", True) is False:
        raise AuthError("User is inactive")

    token_obj = await _create_token_response_for_user(user)
    return auth_schemas.TokenResponse(**token_obj)


async def register(payload: auth_schemas.RegisterRequest) -> auth_schemas.TokenResponse:
    # Ensure email not already used
    existing = await user_service.get_user_by_email(payload.email)
    if existing:
        raise AuthError("Email already registered")

    user_in = user_schemas.UserCreate(
        name=payload.name,
        email=payload.email,
        password=get_password_hash(payload.password),
    )
    created = await user_service.create_user(user_in)
    token_obj = await _create_token_response_for_user(created)
    return auth_schemas.TokenResponse(**token_obj)


async def refresh_token(refresh_token: str) -> auth_schemas.TokenResponse:
    if not refresh_token:
        raise AuthError("Missing refresh token")

    try:
        # Strictly enforce typ == 'refresh'
        payload = jwt_core.verify_token(refresh_token, require_type="refresh")
    except jwt_core.TokenError as exc:
        raise AuthError(f"Invalid refresh token: {exc}") from exc

    # Explicit check: reject access tokens or tokens lacking the explicit refresh type
    if payload.get("typ") != "refresh":
        raise AuthError("Invalid token type: expected refresh token")

    subject = payload.get("sub")
    if not subject:
        raise AuthError("Invalid token payload: missing sub claim")

    # try to load user (by id or email)
    user = None
    try:
        user = await user_service.get_user_by_id(int(subject))
    except Exception:
        # try by email
        user = await user_service.get_user_by_email(subject)

    if not user:
        raise AuthError("User not found for token")

    if getattr(user, "is_active", True) is False:
        raise AuthError("User is inactive")

    token_obj = await _create_token_response_for_user(user)
    return auth_schemas.TokenResponse(**token_obj)


async def get_user_from_token(token: str) -> t.Any:
    if not token:
        raise AuthError("Missing token")

    try:
        payload = jwt_core.decode_token(token)
    except jwt_core.TokenError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc

    # Reject refresh tokens used as bearer authorization
    typ = payload.get("typ")
    if typ == "refresh":
        raise AuthError("Invalid token type: refresh token cannot be used for authorization")
    if typ is not None and typ != "access":
        raise AuthError(f"Invalid token type: expected access token, got '{typ}'")

    subject = payload.get("sub")
    if not subject:
        raise AuthError("Invalid token payload: missing sub claim")

    user = None
    try:
        user = await user_service.get_user_by_id(int(subject))
    except Exception:
        user = await user_service.get_user_by_email(subject)

    if not user:
        raise AuthError("User not found")
    return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> t.Any:
    """
    Dependency to return current user from access token.
    Raises HTTPException 401 when token invalid or user not found.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        return await get_user_from_token(token)
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
