from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CertificateStatus

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User


class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "certificates"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,  # one active certificate per application
        index=True,
    )
    issued_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # --- Human-facing identifier, printed on the physical/PDF certificate ---
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    # --- Anti-tamper fields ---
    # certificate_hash: opaque, URL-safe identifier embedded in the QR code's
    #   verification URL (/api/v1/certificates/verify/{certificate_hash}).
    #   Distinct from certificate_number so the printed number and the
    #   scannable secret aren't the same value (avoids trivial URL guessing).
    certificate_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    # hmac_signature: HMAC-SHA256 of the certificate's canonical payload
    #   (certificate_number + instrument details + validity dates), keyed by
    #   CERTIFICATE_HMAC_SECRET. Recomputed and compared on every public
    #   verification request to detect tampering with stored/served data.
    hmac_signature: Mapped[str] = mapped_column(String(128), nullable=False)

    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus, name="certificate_status_enum", native_enum=True),
        nullable=False,
        default=CertificateStatus.ACTIVE,
        index=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Generated artifacts (paths in the storage backend, not the files themselves) ---
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    qr_code_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # --- Alert engine bookkeeping: prevents duplicate reminders being sent ---
    last_alert_sent_offset_days: Mapped[int | None] = mapped_column(nullable=True)

    # --- Relationships ---
    application: Mapped["Application"] = relationship(back_populates="certificate")
    issued_by: Mapped["User"] = relationship(back_populates="certificates_issued")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Certificate {self.certificate_number} status={self.status}>"
