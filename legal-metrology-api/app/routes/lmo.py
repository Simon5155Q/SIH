from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import require_role
from app.models.application import Application
from app.models.enums import ApplicationStatus, InspectionResult, UserRole
from app.models.inspection import InspectionRecord
from app.models.instrument import Instrument
from app.models.user import User
from app.utils.geo import calculate_haversine_distance

router = APIRouter(prefix="/api/v1/lmo", tags=["LMO operations"])


class InspectionSubmission(BaseModel):
    application_id: uuid.UUID
    result: InspectionResult = InspectionResult.PASS_
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    remarks: str = ""
    readings: dict = Field(default_factory=dict)


@router.get("/applications")
async def list_applications(
    current_user: User = Depends(require_role(UserRole.LMO, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    query = select(Application, Instrument).join(Instrument, Instrument.id == Application.instrument_id).order_by(Application.created_at.desc())
    if current_user.role == UserRole.LMO:
        query = query.where(
            Application.status.in_((ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED, ApplicationStatus.INSPECTION_IN_PROGRESS)),
        )
    applications = (await db.execute(query)).all()
    return [
        {
            "id": str(application.id),
            "instrument_serial": instrument.serial_number,
            "shop_name": instrument.address_line,
            "status": application.status.value,
            "latitude": instrument.latitude,
            "longitude": instrument.longitude,
        }
        for application, instrument in applications
    ]


@router.post("/inspections")
async def submit_inspection(
    submission: InspectionSubmission,
    current_user: User = Depends(require_role(UserRole.LMO, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Application, Instrument).join(Instrument, Instrument.id == Application.instrument_id).where(Application.id == submission.application_id))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    application, instrument = row
    if current_user.role == UserRole.LMO and application.assigned_officer_id not in (None, current_user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Application is assigned to another officer")
    if instrument.latitude is None or instrument.longitude is None:
        instrument.latitude = 13.0827
        instrument.longitude = 80.2707
        await db.flush()

    distance = calculate_haversine_distance(
        submission.latitude,
        submission.longitude,
        instrument.latitude,
        instrument.longitude,
    )
    if distance > 200:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Geo-fence exceeded: inspector is {distance:.1f}m from the registered site")

    now = datetime.now(timezone.utc)
    record = InspectionRecord(
        application_id=application.id,
        inspector_id=current_user.id,
        actual_error_readings=submission.readings,
        mpe_value=0.0,
        result=submission.result,
        latitude=submission.latitude,
        longitude=submission.longitude,
        inspected_at=now,
        inspector_signature_path="demo://lmo-portal",
        remarks=submission.remarks,
    )
    application.status = ApplicationStatus.APPROVED if submission.result == InspectionResult.PASS_ else ApplicationStatus.REJECTED
    application.assigned_officer_id = current_user.id
    application.decided_at = now
    db.add(record)
    await db.commit()
    return {
        "inspection_id": str(record.id),
        "application_id": str(application.id),
        "application_status": application.status.value,
        "distance_meters": round(distance, 1),
    }
