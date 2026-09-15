"""
Password hashing and JWT access/refresh token issuance & verification.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str            # user id (UUID as string)
    role: str
    type: TokenType
    jti: str             # unique token id, enables future revocation/blacklisting
    exp: datetime
    iat: datetime


class InvalidTokenError(Exception):
    """Raised for any malformed, expired, or wrong-type token."""


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --------------------------------------------------------------------------
# Token creation
# --------------------------------------------------------------------------
def _create_token(
    subject: str,
    role: str,
    token_type: TokenType,
    expires_delta: timedelta,
    legacy_role: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "legacy_role": legacy_role or role,
        "type": token_type.value,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str, legacy_role: str | None = None) -> str:
    return _create_token(
        subject=str(user_id),
        role=role,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        legacy_role=legacy_role,
    )


def create_refresh_token(user_id: uuid.UUID, role: str) -> str:
    return _create_token(
        subject=str(user_id),
        role=role,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# --------------------------------------------------------------------------
# Token verification
# --------------------------------------------------------------------------
def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    try:
        raw: dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token is invalid or expired") from exc

    try:
        payload = TokenPayload(**raw)
    except Exception as exc:
        raise InvalidTokenError("Token payload is malformed") from exc

    if payload.type != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type.value} token, got {payload.type.value}")

    return payload
