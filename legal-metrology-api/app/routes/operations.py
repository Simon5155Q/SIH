from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import hash_password
from app.dependencies.auth import require_role
from app.models.application import Application
from app.models.certificate import Certificate
from app.models.enums import ApplicationStatus, InstrumentCategory, PaymentStatus, UserRole
from app.models.inspection import InspectionRecord
from app.models.instrument import Instrument
from app.models.user import User

router = APIRouter(tags=["operations"])
STAFF_ROLES = (UserRole.ADMIN, UserRole.LMO)


def _mock_applications() -> list[dict]:
    return [{"id": "demo-application-001", "trader": "Apex Retailers Pvt Ltd", "instrument": "LM-SCL-00125", "district": "Chennai", "status": "PENDING", "submitted_at": "2026-09-15T09:00:00Z"}]


def _mock_instruments() -> list[dict]:
    return [{"id": "demo-instrument-001", "serial_number": "LM-SCL-00125", "model": "EW-200", "capacity": "200 kg", "district": "Chennai", "last_calibration": "2026-09-01", "qr_status": "ACTIVE"}]


def _mock_officers() -> list[dict]:
    return [{"id": "demo-officer-001", "name": "Demo Field Officer", "designation": "Legal Metrology Officer", "phone": "+91 90000 00003", "district": "Chennai", "field_status": "AVAILABLE"}]


class NewVerificationRequest(BaseModel):
    instrument_type: str
    serial_number: str
    capacity_kg: float
    trade_category: str
    premises_address: str


class LegacyApplicationRequest(BaseModel):
    serial_number: str
    fee_amount: float = 500


def _category(value: str) -> InstrumentCategory:
    normalized = value.upper().replace(" ", "_").replace("/", "_")
    return InstrumentCategory.WEIGHING_SCALE if "WEIGH" in normalized or "SCALE" in normalized else InstrumentCategory.OTHER


@router.post("/applications/create", status_code=status.HTTP_201_CREATED)
async def create_verification_application(payload: NewVerificationRequest, current_user: User = Depends(require_role(UserRole.TRADER, UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(Instrument).where(Instrument.serial_number == payload.serial_number))).scalar_one_or_none()
    if existing is not None and existing.owner_id != current_user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "An instrument with this serial number is already registered")
    instrument = existing or Instrument(owner_id=current_user.id, model_name=payload.instrument_type, manufacturer="Trader supplied", serial_number=payload.serial_number, category=_category(payload.instrument_type), capacity=payload.capacity_kg, capacity_unit="kg", precision_class="Class III", address_line=payload.premises_address, state="Tamil Nadu", district="Chennai", pincode="600001", latitude=13.0827, longitude=80.2707)
    if existing is None:
        db.add(instrument)
        await db.flush()
    elif instrument.latitude is None or instrument.longitude is None:
        instrument.latitude = 13.0827
        instrument.longitude = 80.2707
    application = Application(instrument_id=instrument.id, applicant_id=current_user.id, status=ApplicationStatus.PENDING_INSPECTION, payment_status=PaymentStatus.PENDING, fee_amount=500)
    db.add(application)
    await db.flush()
    reference = f"LMO-APP-{str(application.id).replace('-', '')[-6:].upper()}"
    return {"id": reference, "application_id": str(application.id), "state": "PENDING_ALLOTMENT", "status": "PENDING", "instrument_type": payload.instrument_type, "serial_number": payload.serial_number, "capacity_kg": payload.capacity_kg, "trade_category": payload.trade_category, "premises_address": payload.premises_address, "created_at": application.created_at.isoformat()}


def _pending_payload(application: Application, instrument: Instrument, trader: User) -> dict:
    return {"application_id": str(application.id), "reference": f"LMO-APP-{str(application.id).replace('-', '')[-6:].upper()}", "trader_name": trader.full_name, "instrument_serial": instrument.serial_number, "instrument_type": instrument.model_name, "capacity_kg": instrument.capacity, "premises_address": instrument.address_line, "status": "PENDING_INSPECTION", "latitude": instrument.latitude, "longitude": instrument.longitude, "next_due_date": "2027-09-15"}


@router.get("/applications/pending")
async def pending_applications(current_user: User = Depends(require_role(UserRole.LMO, UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    query = select(Application, Instrument, User).join(Instrument, Instrument.id == Application.instrument_id).join(User, User.id == Application.applicant_id).where(Application.status == ApplicationStatus.PENDING_INSPECTION).order_by(Application.created_at.desc())
    rows = (await db.execute(query)).all()
    if not rows:
        trader = (await db.execute(select(User).where(User.email == "apex@metrology.gov.in"))).scalar_one_or_none()
        if trader is None:
            trader = User(full_name="Apex Retailers Pvt Ltd", email="apex@metrology.gov.in", phone="9000000088", hashed_password=hash_password("Trader@123"), role=UserRole.TRADER, state="Tamil Nadu", district="Chennai", is_active=True, is_verified=True)
            db.add(trader)
            await db.flush()
        instrument = (await db.execute(select(Instrument).where(Instrument.serial_number == "APP-2026-X88"))).scalar_one_or_none()
        if instrument is None:
            instrument = Instrument(owner_id=trader.id, model_name="Weighing Scale / Counter Scale", manufacturer="e-Verify Demo Instruments", serial_number="APP-2026-X88", category=InstrumentCategory.WEIGHING_SCALE, capacity=50, capacity_unit="kg", precision_class="Class III", address_line="District Central, Zone 04", state="Tamil Nadu", district="Chennai", pincode="600001", latitude=13.0827, longitude=80.2707)
            db.add(instrument)
            await db.flush()
        application = Application(instrument_id=instrument.id, applicant_id=trader.id, status=ApplicationStatus.PENDING_INSPECTION, payment_status=PaymentStatus.PENDING, fee_amount=500)
        db.add(application)
        await db.flush()
        await db.commit()
        rows = [(application, instrument, trader)]
    return [_pending_payload(application, instrument, trader) for application, instrument, trader in rows]


@router.post("/applications", status_code=status.HTTP_201_CREATED)
async def create_legacy_application(payload: LegacyApplicationRequest, current_user: User = Depends(require_role(UserRole.TRADER, UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    return await create_verification_application(NewVerificationRequest(instrument_type="Weighing Scale / Counter Scale", serial_number=payload.serial_number, capacity_kg=50, trade_category="Retail", premises_address="District Central, Zone 04"), current_user, db)


@router.get("/applications")
async def trader_applications(current_user: User = Depends(require_role(UserRole.TRADER, UserRole.LMO, UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    query = select(Application, Instrument).join(Instrument, Instrument.id == Application.instrument_id).order_by(Application.created_at.desc())
    if current_user.role == UserRole.TRADER:
        query = query.where(Application.applicant_id == current_user.id)
    else:
        query = query.where(Application.status.in_((ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED, ApplicationStatus.INSPECTION_IN_PROGRESS)))
    rows = (await db.execute(query)).all()
    return [{"id": str(application.id), "reference": f"LMO-APP-{str(application.id).replace('-', '')[-6:].upper()}", "serial_number": instrument.serial_number, "instrument_type": instrument.model_name, "status": "PENDING" if application.status in (ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED) else application.status.value, "created_at": application.created_at.isoformat(), "scheduled_date": application.scheduled_date.isoformat() if application.scheduled_date else None} for application, instrument in rows]


@router.get("/dashboard/stats")
async def dashboard_stats(current_user: User = Depends(require_role(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)):
    verified = await db.scalar(select(func.count(Instrument.id))) or 0
    pending = await db.scalar(select(func.count(Application.id)).where(Application.status.in_((ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED, ApplicationStatus.INSPECTION_IN_PROGRESS)))) or 0
    officers = await db.scalar(select(func.count(User.id)).where(User.role == UserRole.LMO, User.is_active.is_(True))) or 0
    breaches = 0
    return {"total_verified_instruments": verified or len(_mock_instruments()), "pending_inspections": pending or len(_mock_applications()), "active_officers": officers or len(_mock_officers()), "geo_fence_breach_alerts": breaches}


@router.get("/admin/stats")
async def legacy_admin_stats(current_user: User = Depends(require_role(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    stats = await dashboard_stats(current_user, db)
    return {"applications": stats["pending_inspections"], "pending": stats["pending_inspections"], "instruments": stats["total_verified_instruments"], "certificates": 0, "reports": stats["geo_fence_breach_alerts"]}


@router.get("/applications/queue")
async def application_queue(status_filter: str | None = Query(default=None, alias="status"), current_user: User = Depends(require_role(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)):
    query = select(Application, User, Instrument).join(User, User.id == Application.applicant_id).join(Instrument, Instrument.id == Application.instrument_id).order_by(Application.created_at.desc())
    if status_filter:
        normalized = status_filter.upper()
        if normalized == "PENDING":
            query = query.where(Application.status.in_((ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED, ApplicationStatus.INSPECTION_IN_PROGRESS)))
        elif normalized in ApplicationStatus.__members__:
            query = query.where(Application.status == ApplicationStatus[normalized])
    rows = (await db.execute(query)).all()
    if not rows:
        items = _mock_applications()
        return items if not status_filter or status_filter.upper() == "PENDING" else []
    return [{"id": str(application.id), "trader": trader.full_name, "instrument": instrument.serial_number, "district": instrument.district, "status": application.status.value, "submitted_at": application.created_at.isoformat()} for application, trader, instrument in rows]


class AllotmentRequest(BaseModel):
    application_id: uuid.UUID
    officer_id: uuid.UUID


@router.get("/inspectors/allotment")
async def allotment_data(current_user: User = Depends(require_role(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)):
    officers = (await db.execute(select(User).where(User.role == UserRole.LMO, User.is_active.is_(True)).order_by(User.full_name))).scalars().all()
    pending = (await db.execute(select(Application, Instrument).join(Instrument, Instrument.id == Application.instrument_id).where(Application.status.in_((ApplicationStatus.PENDING_INSPECTION, ApplicationStatus.SUBMITTED, ApplicationStatus.PAYMENT_PENDING, ApplicationStatus.SCHEDULED))))).all()
    return {"officers": [{"id": str(officer.id), "name": officer.full_name, "district": officer.district, "zone": officer.zone.value if officer.zone else "CENTRAL", "field_status": "AVAILABLE"} for officer in officers] or _mock_officers(), "pending": [{"id": str(application.id), "instrument": instrument.serial_number, "district": instrument.district, "status": application.status.value} for application, instrument in pending] or _mock_applications()}


@router.post("/inspectors/allotment")
async def allot_inspection(payload: AllotmentRequest, current_user: User = Depends(require_role(UserRole.ADMIN)), db: AsyncSession = Depends(get_db)):
    application = await db.get(Application, payload.application_id)
    officer = await db.get(User, payload.officer_id)
    if application is None or officer is None or officer.role != UserRole.LMO:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application or officer not found")
    application.assigned_officer_id = officer.id
    application.status = ApplicationStatus.SCHEDULED
    application.scheduled_date = datetime.now(timezone.utc)
    await db.commit()
    return {"application_id": str(application.id), "officer_id": str(officer.id), "status": application.status.value}


@router.get("/instruments")
async def registered_instruments(search: str | None = None, current_user: User = Depends(require_role(*STAFF_ROLES, UserRole.TRADER)), db: AsyncSession = Depends(get_db)):
    query = select(Instrument).order_by(Instrument.created_at.desc())
    if current_user.role == UserRole.TRADER:
        query = query.where(Instrument.owner_id == current_user.id)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Instrument.serial_number.ilike(pattern), Instrument.model_name.ilike(pattern)))
    instruments = (await db.execute(query)).scalars().all()
    if not instruments and not search:
        return _mock_instruments()
    return [{"id": str(instrument.id), "serial_number": instrument.serial_number, "model": instrument.model_name, "capacity": f"{instrument.capacity:g} {instrument.capacity_unit}", "district": instrument.district, "last_calibration": instrument.updated_at.date().isoformat(), "qr_status": "ACTIVE"} for instrument in instruments]


@router.get("/officers")
async def officer_directory(current_user: User = Depends(require_role(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)):
    officers = (await db.execute(select(User).where(User.role == UserRole.LMO).order_by(User.full_name))).scalars().all()
    if not officers:
        return _mock_officers()
    return [{"id": str(officer.id), "name": officer.full_name, "designation": "Legal Metrology Officer", "phone": officer.phone, "district": officer.district, "field_status": "ACTIVE" if officer.is_active else "INACTIVE"} for officer in officers]
