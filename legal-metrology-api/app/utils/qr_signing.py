import hmac
import hashlib
import json
import base64
from app.core.config import settings


def sign_application_payload(application_id: str, instrument_serial: str, expiry_date: str) -> tuple[str, str]:
    payload = f"{application_id}:{instrument_serial}:{expiry_date}"
    signature = hmac.new(settings.CERTIFICATE_HMAC_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return payload, signature


def verify_application_payload(payload: str, signature: str) -> bool:
    expected = hmac.new(settings.CERTIFICATE_HMAC_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

def sign_certificate_payload(certificate_id: int, instrument_serial: str, issued_at_iso: str) -> str:
    """Generates a tamper-proof HMAC-SHA256 signed token for certificate QR codes."""
    secret = settings.CERTIFICATE_HMAC_SECRET.encode("utf-8")
    payload_data = f"{certificate_id}:{instrument_serial}:{issued_at_iso}"
    signature = hmac.new(secret, payload_data.encode("utf-8"), hashlib.sha256).hexdigest()
    
    token_structure = {
        "cid": certificate_id,
        "sn": instrument_serial,
        "ts": issued_at_iso,
        "sig": signature
    }
    
    raw_json = json.dumps(token_structure)
    return base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")

def verify_certificate_payload(token: str) -> dict | None:
    """Verifies the HMAC signature of a QR certificate token."""
    try:
        decoded_json = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        data = json.loads(decoded_json)
        
        secret = settings.CERTIFICATE_HMAC_SECRET.encode("utf-8")
        
        cid = data["cid"]
        sn = data["sn"]
        ts = data["ts"]
        payload_data = f"{cid}:{sn}:{ts}"
        
        expected_sig = hmac.new(secret, payload_data.encode("utf-8"), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(data["sig"], expected_sig):
            return data
        return None
    except Exception:
        return None