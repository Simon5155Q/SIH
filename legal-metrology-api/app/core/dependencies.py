"""
Reusable FastAPI dependencies:
  - get_current_user:      decodes the access JWT, loads & validates the User
  - get_current_active_verified_user: adds is_active / is_verified checks
  - has_role([...]):       dependency factory for RBAC route guarding
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import InvalidTokenError, TokenType, decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError:
        raise credentials_exception

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    # Defense-in-depth: if the user's role was changed after the token was
    # issued (e.g. deactivated as GATC), reject the stale token's claim.
    if user.role.value != payload.role:
        raise credentials_exception

    return user


async def get_current_active_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending verification by the regulator",
        )
    return current_user


def has_role(allowed_roles: list[UserRole]):
    """
    Dependency factory for RBAC route guarding.

    Usage:
        @router.post("/instruments", dependencies=[Depends(has_role([UserRole.LMO, UserRole.ADMIN]))])
    or to also access the user object:
        async def endpoint(user: User = Depends(has_role([UserRole.ADMIN]))): ...
    """

    async def _role_checker(
        current_user: User = Depends(get_current_active_verified_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' is not permitted to perform "
                    f"this action. Required: {[r.value for r in allowed_roles]}"
                ),
            )
        return current_user

    return _role_checker
