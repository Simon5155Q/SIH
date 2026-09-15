from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ApplicationStatus, PaymentStatus

if TYPE_CHECKING:
    from app.models.certificate import Certificate
    from app.models.inspection import InspectionRecord
    from app.models.instrument import Instrument
    from app.models.user import User


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Represents a single verification/re-verification request and tracks it
    through the state machine:

        SUBMITTED -> PAYMENT_PENDING -> SCHEDULED -> INSPECTION_IN_PROGRESS
                  -> APPROVED / REJECTED -> CERTIFICATE_ISSUED

    Valid transitions are enforced in the service layer
    (see app/services/application_service.py), not at the DB layer, so that
    business-rule changes don't require a migration.
    """
    __tablename__ = "applications"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_officer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status_enum", native_enum=True),
        nullable=False,
        default=ApplicationStatus.SUBMITTED,
        index=True,
    )

    # --- Scheduling ---
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Payment ---
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", native_enum=True),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fee_amount: Mapped[float | None] = mapped_column(nullable=True)

    # --- Decision ---
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    instrument: Mapped["Instrument"] = relationship(back_populates="applications")
    applicant: Mapped["User"] = relationship(
        back_populates="applications_filed", foreign_keys=[applicant_id]
    )
    assigned_officer: Mapped["User | None"] = relationship(
        back_populates="applications_assigned", foreign_keys=[assigned_officer_id]
    )
    inspection_records: Mapped[list["InspectionRecord"]] = relationship(
        back_populates="application", order_by="InspectionRecord.created_at"
    )
    certificate: Mapped["Certificate | None"] = relationship(
        back_populates="application", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Application {self.id} status={self.status}>"
