from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.certificate_pdf_service import generate_certificate_pdf

router = APIRouter(prefix="/api/v1/staging", tags=["staging"])


@router.get("/certificate.pdf")
async def staging_certificate_pdf(current_user: User = Depends(get_current_user)):
    pdf_bytes = generate_certificate_pdf(
        certificate_id="STAGING-001",
        instrument_serial="DEV-SCALE-001",
        instrument_type="Electronic Weighing Scale",
        owner_name=current_user.full_name,
        inspection_date=datetime.now(timezone.utc).date().isoformat(),
        verification_status="STAGING VERIFIED",
        verify_base_url=f"http://127.0.0.1:8000/api/v1",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="staging-certificate.pdf"'},
    )
