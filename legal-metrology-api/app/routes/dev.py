from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_db
from app.dependencies.auth import require_role
from app.models.enums import InstrumentCategory, UserRole
from app.models.enums import ApplicationStatus, PaymentStatus
from app.models.application import Application
from app.models.instrument import Instrument
from app.models.user import User
from app.utils.qr_signing import sign_certificate_payload

router = APIRouter(prefix="/api/v1/dev", tags=["developer sandbox"])


@router.get("/sample-token")
async def sample_token():
    valid = sign_certificate_payload("sandbox-cert", "DEV-SCALE-001", "2026-09-14T00:00:00+00:00")
    return {"valid_token": valid, "tampered_token": valid[:-8] + "INVALID0"}


@router.post("/seed")
async def seed_test_data(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    created_officers = 0
    created_scales = 0

    for index in range(1, 4):
        email = f"test-officer-{index}@example.com"
        officer = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if officer is None:
            db.add(
                User(
                    id=uuid.uuid4(),
                    full_name=f"Sandbox Officer {index}",
                    email=email,
                    phone=f"91000000{index:02d}",
                    hashed_password=hash_password("Demo@123"),
                    role=UserRole.LMO,
                    state="Tamil Nadu",
                    district="Chennai",
                    is_active=True,
                    is_verified=True,
                )
            )
            created_officers += 1

    first_instrument = None
    for index in range(1, 11):
        serial = f"DEV-SCALE-{index:03d}"
        existing = (
            await db.execute(select(Instrument).where(Instrument.serial_number == serial))
        ).scalar_one_or_none()
        if existing is not None:
            if first_instrument is None:
                first_instrument = existing
            continue
        shop = (index - 1) % 5 + 1
        instrument = Instrument(
                id=uuid.uuid4(),
                owner_id=current_user.id,
                model_name=f"Sandbox Scale {index}",
                manufacturer="e-Verify Test Lab",
                serial_number=serial,
                category=InstrumentCategory.WEIGHING_SCALE,
                capacity=200,
                capacity_unit="kg",
                precision_class="Class III",
                address_line=f"Sandbox Shop {shop}",
                state="Tamil Nadu",
                district="Chennai",
                pincode="600001",
                latitude=13.0827 + ((shop - 1) * 0.001),
                longitude=80.2707 + ((shop - 1) * 0.001),
            )
        db.add(instrument)
        if first_instrument is None:
            first_instrument = instrument
        created_scales += 1

    await db.flush()
    existing_application = None
    if first_instrument is not None:
        existing_application = (
            await db.execute(
                select(Application).where(Application.instrument_id == first_instrument.id)
            )
        ).scalar_one_or_none()
    if existing_application is None and first_instrument is not None:
        db.add(
            Application(
                instrument_id=first_instrument.id,
                applicant_id=current_user.id,
                assigned_officer_id=current_user.id,
                status=ApplicationStatus.SCHEDULED,
                payment_status=PaymentStatus.PAID,
                fee_amount=500,
            )
        )
    await db.commit()
    return {
        "message": "Developer seed complete",
        "shops": 5,
        "officers": 3,
        "verified_scales": 10,
        "created_officers": created_officers,
        "created_scales": created_scales,
    }
