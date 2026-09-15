import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies.auth import require_role
from app.models.application import Application
from app.models.certificate import Certificate
from app.models.enums import ApplicationStatus, CertificateStatus, UserRole
from app.models.instrument import Instrument
from app.models.user import User
from app.services.certificate_pdf_service import generate_certificate_pdf
from app.core.config import settings
from app.utils.qr import generate_verification_qr
from app.utils.qr_signing import sign_application_payload

router = APIRouter(prefix="/certificates", tags=["certificates"])


class IssueCertificateRequest(BaseModel):
    application_id: uuid.UUID


@router.post("/issue")
async def issue_certificate(payload: IssueCertificateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role(UserRole.LMO, UserRole.ADMIN))):
    row = (await db.execute(select(Application, Instrument, User).join(Instrument, Instrument.id == Application.instrument_id).join(User, User.id == Application.applicant_id).where(Application.id == payload.application_id))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    application, instrument, owner = row
    if application.status == ApplicationStatus.REJECTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Rejected applications cannot be certified")
    existing = (await db.execute(select(Certificate).where(Certificate.application_id == application.id))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expiry = existing.expiry_date if existing else now + timedelta(days=365)
    certificate_number = existing.certificate_number if existing else f"CERT-{now.year}-{uuid.uuid4().hex[:4].upper()}"
    expiry_iso = expiry.isoformat()
    payload_string, signature = sign_application_payload(str(application.id), instrument.serial_number, expiry_iso)
    verification_url = f"http://localhost:8000/verify?payload={quote(payload_string, safe='')}&sig={signature}"
    qr_stream = generate_verification_qr(verification_url)
    qr_base64 = base64.b64encode(qr_stream.read()).decode("ascii")
    if existing is None:
        certificate = Certificate(application_id=application.id, issued_by_id=current_user.id, certificate_number=certificate_number, certificate_hash=payload_string, hmac_signature=signature, issue_date=now, expiry_date=expiry, status=CertificateStatus.ACTIVE, pdf_path="memory://certificate.pdf", qr_code_path="memory://certificate.png")
        db.add(certificate)
    application.status = ApplicationStatus.CERTIFICATE_ISSUED
    await db.commit()
    return {"status": "SUCCESS", "certificate_id": certificate_number, "qr_base64": qr_base64, "verification_url": verification_url, "pdf_download_url": f"/api/v1/certificates/{certificate_number}/download"}


@router.get("/{certificate_ref}/download")
async def download_issued_certificate(certificate_ref: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_role(UserRole.LMO, UserRole.ADMIN, UserRole.TRADER))):
    row = (await db.execute(select(Certificate, Application, Instrument, User).join(Application, Application.id == Certificate.application_id).join(Instrument, Instrument.id == Application.instrument_id).join(User, User.id == Application.applicant_id).where(Certificate.certificate_number == certificate_ref))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    certificate, application, instrument, owner = row
    payload_string, signature = sign_application_payload(str(application.id), instrument.serial_number, certificate.expiry_date.isoformat())
    verification_url = f"http://localhost:8000/verify?payload={quote(payload_string, safe='')}&sig={signature}"
    pdf_bytes = generate_certificate_pdf(certificate_id=certificate.certificate_number, instrument_serial=instrument.serial_number, instrument_type=instrument.model_name, owner_name=owner.full_name, inspection_date=certificate.issue_date.date().isoformat(), verification_status="VERIFIED", verify_base_url="http://localhost:8000", verification_url=verification_url)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{certificate.certificate_number}.pdf"'})

@router.get("/{certificate_id}/pdf")
async def download_certificate_pdf(
    certificate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("GATC", "ADMIN", "TRADER")),
):
    pdf_bytes = generate_certificate_pdf(
        certificate_id=certificate_id,
        instrument_serial="INSTR-SERIAL-PLACEHOLDER",
        instrument_type="Electronic Weighing Scale",
        owner_name="Owner Name Placeholder",
        inspection_date="2026-09-07",
        verification_status="VERIFIED",
        verify_base_url=settings.PUBLIC_API_BASE_URL,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate_{certificate_id}.pdf"'},
    )
