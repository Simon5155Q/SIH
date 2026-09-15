from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InspectionResult

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User


class InspectionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Captures a single field inspection event for an application. An
    application may have more than one InspectionRecord (e.g. a FAIL
    followed by a re-inspection after repair), so this is a one-to-many
    off `Application`, not one-to-one.
    """
    __tablename__ = "inspection_records"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inspector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # --- Readings ---
    # Structured as JSONB so different instrument categories (weighing scale,
    # flow meter, taximeter...) can each store their own reading schema
    # without needing a new column/migration per category.
    # e.g. {"test_loads": [{"applied": 20.0, "observed": 20.05, "error": 0.05}], "unit": "kg"}
    actual_error_readings: Mapped[dict] = mapped_column(JSON, nullable=False)
    mpe_value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Maximum Permissible Error allowed for this instrument's class/capacity"
    )
    result: Mapped[InspectionResult] = mapped_column(
        Enum(InspectionResult, name="inspection_result_enum", native_enum=True),
        nullable=False,
        index=True,
    )

    # --- Geotagging & timestamp of the physical visit ---
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- Signature: path to a stored image/PDF/base64 blob in the file storage backend ---
    inspector_signature_path: Mapped[str] = mapped_column(String(500), nullable=False)

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    application: Mapped["Application"] = relationship(back_populates="inspection_records")
    inspector: Mapped["User"] = relationship(back_populates="inspections_conducted")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InspectionRecord {self.id} result={self.result}>"
