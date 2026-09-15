"""Create local development accounts for the e-Verify API.

Run from legal-metrology-api after the database is available:
    .venv\Scripts\python.exe scripts\seed_demo.py
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.models import application, certificate, inspection, instrument
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import UserRole
from app.models.user import User

DEMO_USERS = (
    ("Demo Administrator", "admin@example.com", "9000000001", UserRole.ADMIN),
    ("Demo Consumer", "consumer@example.com", "9000000002", UserRole.TRADER),
    ("Demo Field Officer", "officer@example.com", "9000000003", UserRole.LMO),
)


async def seed_demo_users() -> None:
    async with AsyncSessionLocal() as session:
        for full_name, email, phone, role in DEMO_USERS:
            existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                User(
                    id=uuid.uuid4(),
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    hashed_password=hash_password("Demo@123"),
                    role=role,
                    state="Tamil Nadu",
                    district="Chennai",
                    is_active=True,
                    is_verified=True,
                )
            )
        await session.commit()

    print("Demo accounts ready. Password for all accounts: Demo@123")
    for _, email, _, role in DEMO_USERS:
        normalized = {UserRole.ADMIN: "ADMIN", UserRole.TRADER: "CONSUMER", UserRole.LMO: "FIELD_OFFICER"}[role]
        print(f"{normalized}: {email}")


if __name__ == "__main__":
    asyncio.run(seed_demo_users())
