# Legal Metrology e-Verify System Rules

## Architecture Constraints
- **Backend Stack**: Python 3.11+, FastAPI (async endpoints), Pydantic v2, SQLAlchemy 2.0.
- **Geo-Fencing Rule**: All inspector submissions MUST include `(lat, lon)` vectors. The backend enforces a strict **200-meter Haversine threshold** against registered shop coordinates.
- **Zero-Disk PDF Rule**: Certificates generated via ReportLab MUST stream directly as in-memory binary payloads (`io.BytesIO`). Do NOT write static PDF files to disk.
- **Verification Logic**: QR verification must remain stateless using HMAC-SHA256 hash checking to prevent unnecessary database hits on public scans.

## Coding Style Rules
- Use typed Python models for all request/response schemas.
- Use parameterized SQL queries exclusively to eliminate SQL injection risks.
- Keep frontend components modern, scannable, and styled with dark mode elements.