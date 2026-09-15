from __future__ import annotations

import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger("legal_metrology.auth")
router = APIRouter(tags=["authentication"])
_otp_store: dict[str, tuple[str, datetime]] = {}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


def _auth_role(role: str) -> str:
    return role


def _user_response(user: User) -> dict[str, str]:
    return {
        "id": str(user.id),
        "name": user.full_name,
        "email": user.email,
        "role": user.role.value,
        "auth_role": _auth_role(user.role.value),
    }


def _tokens_for(user: User) -> dict:
    return {
        "access_token": create_access_token(
            user.id,
            _auth_role(user.role.value),
            legacy_role=user.role.value,
        ),
        "token_type": "bearer",
        "user": _user_response(user),
    }


def _deliver_otp(email: str, otp: str) -> bool:
    if not all((settings.SMTP_SERVER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD)):
        logger.warning("SMTP credentials missing. OTP for %s: %s", email, otp)
        return False

    message = EmailMessage()
    message["Subject"] = "Legal Metrology verification code"
    message["From"] = settings.SMTP_USERNAME
    message["To"] = email
    message.set_content(f"Your e-Verify OTP is {otp}. It expires in 10 minutes.")
    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)
    return True


@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        email = str(form.get("username") or form.get("email") or "").strip()
        password = str(form.get("password") or "")
    else:
        body = await request.json()
        payload = LoginRequest.model_validate(body)
        email = payload.email
        password = payload.password
    user = (
        await db.execute(select(User).where(User.email.ilike(email)))
    ).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is deactivated")
    return _tokens_for(user)


@router.post("/send-otp")
async def send_otp(payload: OtpRequest, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(User).where(User.email.ilike(payload.email)))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account exists for this email")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    _otp_store[payload.email.lower()] = (
        otp,
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    try:
        delivered = _deliver_otp(payload.email, otp)
    except (OSError, smtplib.SMTPException):
        logger.exception("Unable to deliver OTP email")
        delivered = False

    response = {
        "message": "OTP sent" if delivered else "SMTP unavailable; OTP logged to the backend console"
    }
    if not delivered and settings.APP_ENV != "production":
        response["dev_otp"] = otp
    return response


@router.post("/verify-otp")
async def verify_otp(payload: OtpVerifyRequest, db: AsyncSession = Depends(get_db)):
    saved = _otp_store.get(payload.email.lower())
    if (
        saved is None
        or saved[1] < datetime.now(timezone.utc)
        or not hmac.compare_digest(saved[0], payload.otp)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired OTP")

    user = (
        await db.execute(select(User).where(User.email.ilike(payload.email)))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    _otp_store.pop(payload.email.lower(), None)
    return _tokens_for(user)
