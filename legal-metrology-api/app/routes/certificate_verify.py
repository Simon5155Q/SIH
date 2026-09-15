from fastapi import APIRouter, HTTPException, Query, status
from app.utils.qr_signing import verify_certificate_payload

router = APIRouter(prefix="/certificates", tags=["certificates"])

@router.get("/verify/{token}")
async def verify_certificate_token(token: str):
    """Public endpoint to verify QR code authenticity without database lookups."""
    payload = verify_certificate_payload(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or tampered certificate signature"
        )
    return {
        "verified": True,
        "certificate_id": payload["cid"],
        "instrument_serial": payload["sn"],
        "issued_at_utc": payload["ts"]
    }


@router.get("/verify-token")
async def verify_certificate_query_token(token: str = Query(...)):
    return await verify_certificate_token(token)
