"""
User model.

Design note on RBAC: rather than a separate many-to-many `Role` table
(over-engineering for 4 fixed, mutually-exclusive roles), each user has a
single `role` enum column. This keeps `has_role([...])` dependency checks
O(1) and avoids a join on every authenticated request. If in future a user
needs multiple concurrent roles, this is the seam to introduce a
`user_roles` association table instead.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import JurisdictionZone, UserRole

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.certificate import Certificate
    from app.models.inspection import InspectionRecord
    from app.models.instrument import Instrument


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=True),
        nullable=False,
        index=True,
    )

    # --- Jurisdiction mapping (used for LMO/GATC assignment & TRADER's local office) ---
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    zone: Mapped[JurisdictionZone | None] = mapped_column(
        Enum(JurisdictionZone, name="jurisdiction_zone_enum", native_enum=True),
        nullable=True,
    )

    # --- GATC-specific accreditation fields (nullable for other roles) ---
    gatc_accreditation_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gatc_accreditation_valid_till: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Account state ---
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Admin/LMO accounts are typically pre-verified by a super-admin during onboarding;
    # TRADER/GATC self-registrations require document/KYC verification before is_verified=True.

    # --- Relationships ---
    instruments: Mapped[list["Instrument"]] = relationship(
        back_populates="owner", foreign_keys="Instrument.owner_id"
    )
    applications_filed: Mapped[list["Application"]] = relationship(
        back_populates="applicant", foreign_keys="Application.applicant_id"
    )
    applications_assigned: Mapped[list["Application"]] = relationship(
        back_populates="assigned_officer", foreign_keys="Application.assigned_officer_id"
    )
    inspections_conducted: Mapped[list["InspectionRecord"]] = relationship(
        back_populates="inspector"
    )
    certificates_issued: Mapped[list["Certificate"]] = relationship(
        back_populates="issued_by"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} role={self.role}>"
