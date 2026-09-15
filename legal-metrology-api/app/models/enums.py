"""
All domain enums live here to avoid circular imports between model files
and to give Alembic a single source of truth for PG ENUM types.
"""
import enum


class UserRole(str, enum.Enum):
    TRADER = "TRADER"          # Instrument owner
    LMO = "LMO"                # Legal Metrology Officer (government)
    GATC = "GATC"              # Government Approved Test Centre
    ADMIN = "ADMIN"             # State/Central regulator (superuser)


class JurisdictionZone(str, enum.Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    CENTRAL = "CENTRAL"


class InstrumentCategory(str, enum.Enum):
    WEIGHING_SCALE = "WEIGHING_SCALE"
    FUEL_DISPENSER = "FUEL_DISPENSER"
    FLOW_METER = "FLOW_METER"
    WEIGHBRIDGE = "WEIGHBRIDGE"
    TAXIMETER = "TAXIMETER"
    GAS_METER = "GAS_METER"
    WATER_METER = "WATER_METER"
    OTHER = "OTHER"


class ApplicationStatus(str, enum.Enum):
    PENDING_INSPECTION = "PENDING_INSPECTION"
    SUBMITTED = "SUBMITTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    SCHEDULED = "SCHEDULED"
    INSPECTION_IN_PROGRESS = "INSPECTION_IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class InspectionResult(str, enum.Enum):
    PASS_ = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class CertificateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"  # replaced by a re-verification certificate


class DocumentType(str, enum.Enum):
    INSTRUMENT_PHOTO = "INSTRUMENT_PHOTO"
    PROOF_OF_PURCHASE = "PROOF_OF_PURCHASE"
    PREVIOUS_CERTIFICATE = "PREVIOUS_CERTIFICATE"
    INSPECTOR_SIGNATURE = "INSPECTOR_SIGNATURE"
    OTHER = "OTHER"
