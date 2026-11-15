from __future__ import annotations

import asyncio
from typing import Any

from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import database
from ..models.user_models import User
from ..schemas import user_schemas

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserServiceError(Exception):
    """Raised when a user CRUD operation fails expected business validation."""


def _get_session() -> Session:
    """Return a synchronous SQLAlchemy session."""

    return database.SessionLocal()


def _normalize_password(password: str) -> str:
    """Hash plaintext passwords while leaving existing bcrypt hashes untouched."""

    if _password_context.identify(password):
        return password
    return _password_context.hash(password)


def _sync_get_user_by_email(email: str) -> User | None:
    db = _get_session()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


async def get_user_by_email(email: str) -> User | None:
    return await asyncio.to_thread(_sync_get_user_by_email, email)


def _sync_get_user_by_id(user_id: int) -> User | None:
    db = _get_session()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


async def get_user_by_id(user_id: int) -> User | None:
    return await asyncio.to_thread(_sync_get_user_by_id, user_id)


def _sync_get_users(skip: int = 0, limit: int = 100) -> list[User]:
    db = _get_session()
    try:
        return db.query(User).order_by(User.id).offset(skip).limit(limit).all()
    finally:
        db.close()


async def get_users(skip: int = 0, limit: int = 100) -> list[User]:
    return await asyncio.to_thread(_sync_get_users, skip, limit)


def _sync_create_user(user_in: user_schemas.UserCreate) -> User:
    db = _get_session()
    try:
        payload = user_in.model_dump()
        payload["password"] = _normalize_password(payload["password"])
        user = User(**payload)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise UserServiceError("Email already registered") from exc
    finally:
        db.close()


async def create_user(user_in: user_schemas.UserCreate) -> User:
    return await asyncio.to_thread(_sync_create_user, user_in)


def _sync_update_user(user_id: int, payload: user_schemas.UserUpdate) -> User | None:
    db = _get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        if "password" in update_data and update_data["password"] is not None:
            update_data["password"] = _normalize_password(update_data["password"])

        for field_name, field_value in update_data.items():
            setattr(user, field_name, field_value)

        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise UserServiceError("Email already registered") from exc
    finally:
        db.close()


async def update_user(user_id: int, payload: user_schemas.UserUpdate) -> User | None:
    return await asyncio.to_thread(_sync_update_user, user_id, payload)


def _sync_delete_user(user_id: int) -> bool:
    db = _get_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return False
        db.delete(user)
        db.commit()
        return True
    finally:
        db.close()


async def delete_user(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_delete_user, user_id)
