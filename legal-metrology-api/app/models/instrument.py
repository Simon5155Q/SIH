from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import InstrumentCategory

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.user import User


class Instrument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "instruments"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(150), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[InstrumentCategory] = mapped_column(
        Enum(InstrumentCategory, name="instrument_category_enum", native_enum=True),
        nullable=False,
        index=True,
    )

    # --- Technical specification, used to compute permissible error (MPE) at inspection time ---
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_unit: Mapped[str] = mapped_column(String(20), nullable=False)  # kg, litre, m3, etc.
    precision_class: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. Class III

    # --- Deployment location (site of use, not owner's registered address) ---
    address_line: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Relationships ---
    owner: Mapped["User"] = relationship(back_populates="instruments", foreign_keys=[owner_id])
    applications: Mapped[list["Application"]] = relationship(back_populates="instrument")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Instrument {self.serial_number} ({self.category})>"
