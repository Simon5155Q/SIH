import os

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.db.base import Base
from app.db.session import engine
from app.models import application, certificate, inspection, instrument, user
from app.routes import uploads, certificate_generate, certificate_verify, offline_sync, auth, dev, staging, lmo, operations
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.models.instrument import Instrument
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.utils.qr_signing import verify_application_payload

app = FastAPI(
    title="Legal Metrology Online Verification System",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        missing_coordinates = (await session.execute(select(Instrument).where((Instrument.latitude.is_(None)) | (Instrument.longitude.is_(None))))).scalars().all()
        for instrument in missing_coordinates:
            instrument.latitude = 13.0827
            instrument.longitude = 80.2707
        trader = (await session.execute(select(User).where(User.email == "trader@metrology.gov.in"))).scalar_one_or_none()
        if trader is None:
            session.add(User(full_name="Default Trader", email="trader@metrology.gov.in", phone="9000000099", hashed_password=hash_password("Trader@123"), role=UserRole.TRADER, state="Tamil Nadu", district="Chennai", is_active=True, is_verified=True))
            await session.commit()
        elif missing_coordinates:
            await session.commit()

# Enable CORS for browser-based testing (demo.html / Swagger)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Health Route
@app.get("/", tags=["Health"])
async def root():
    return {"status": "healthy", "service": "Legal Metrology API"}

# Include Routers
app.include_router(uploads.router)
app.include_router(certificate_generate.router)
app.include_router(certificate_verify.router)
app.include_router(offline_sync.router)
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(auth.router, prefix="/api/auth")
app.include_router(dev.router)
app.include_router(staging.router)
app.include_router(lmo.router)
app.include_router(operations.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api")


@app.get("/verify", include_in_schema=False)
async def verify_issued_application(payload: str = Query(...), sig: str = Query(...)):
    if not verify_application_payload(payload, sig):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or tampered certificate signature")
    parts = payload.split(":", 2)
    return {"verified": True, "application_id": parts[0], "instrument_serial": parts[1], "expiry_date": parts[2]}

FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))


@app.get("/app.js", include_in_schema=False)
async def frontend_javascript():
    return FileResponse(os.path.join(FRONTEND_ROOT, "app.js"), media_type="application/javascript")


@app.get("/{page}.html", include_in_schema=False)
async def frontend_page(page: str):
    allowed_pages = {"index", "merchant", "lmo", "admin", "verify", "sandbox", "login", "staging-test"}
    if page not in allowed_pages:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(os.path.join(FRONTEND_ROOT, f"{page}.html"))

# Versioned compatibility paths used by the browser client and public API.
for prefix in ("/api", "/api/v1"):
    app.include_router(uploads.router, prefix=prefix)
    app.include_router(certificate_generate.router, prefix=prefix)
    app.include_router(certificate_verify.router, prefix=prefix)
    app.include_router(offline_sync.router, prefix=prefix)

    FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

    @app.get("/staging-test", include_in_schema=False)
    async def staging_test_page():
        from fastapi.responses import FileResponse
        return FileResponse(os.path.join(FRONTEND_ROOT, "staging-test.html"))