-- Legal Metrology Online Verification System
-- PostgreSQL schema. The FastAPI demo uses SQLite by default; this schema is for production PostgreSQL/Supabase.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_role AS ENUM ('TRADER','LMO','GATC','ADMIN');
CREATE TYPE application_status AS ENUM ('SUBMITTED','PAYMENT_PENDING','SCHEDULED','INSPECTION_IN_PROGRESS','APPROVED','REJECTED','CERTIFICATE_ISSUED');
CREATE TYPE payment_status AS ENUM ('PENDING','PAID','FAILED','REFUNDED');
CREATE TYPE inspection_result AS ENUM ('PASS','FAIL','INCONCLUSIVE');
CREATE TYPE certificate_status AS ENUM ('ACTIVE','EXPIRED','REVOKED','SUPERSEDED');

CREATE TABLE users (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), full_name VARCHAR(150) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL,
 phone VARCHAR(20) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role user_role NOT NULL,
 state VARCHAR(100) NOT NULL, district VARCHAR(100) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE,
 is_verified BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_role ON users(role); CREATE INDEX idx_users_jurisdiction ON users(state,district);

CREATE TABLE instruments (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 model_name VARCHAR(150) NOT NULL, manufacturer VARCHAR(150) NOT NULL, serial_number VARCHAR(100) UNIQUE NOT NULL,
 category VARCHAR(50) NOT NULL, capacity NUMERIC(12,3) NOT NULL, capacity_unit VARCHAR(20) NOT NULL,
 precision_class VARCHAR(20) NOT NULL, address_line VARCHAR(255) NOT NULL, state VARCHAR(100) NOT NULL,
 district VARCHAR(100) NOT NULL, pincode VARCHAR(10) NOT NULL, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_instruments_owner ON instruments(owner_id); CREATE INDEX idx_instruments_location ON instruments(state,district);

CREATE TABLE applications (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), instrument_id UUID NOT NULL REFERENCES instruments(id) ON DELETE RESTRICT,
 applicant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, assigned_officer_id UUID REFERENCES users(id) ON DELETE SET NULL,
 status application_status NOT NULL DEFAULT 'SUBMITTED', scheduled_date TIMESTAMPTZ, payment_status payment_status NOT NULL DEFAULT 'PENDING',
 payment_reference VARCHAR(100), fee_amount NUMERIC(12,2), rejection_reason VARCHAR(500), decided_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_app_status ON applications(status); CREATE INDEX idx_app_assignee ON applications(assigned_officer_id);

CREATE TABLE inspection_records (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
 inspector_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, actual_error_readings JSONB NOT NULL DEFAULT '{}'::jsonb,
 mpe_value NUMERIC(12,6) NOT NULL, result inspection_result NOT NULL, latitude DOUBLE PRECISION NOT NULL,
 longitude DOUBLE PRECISION NOT NULL, inspected_at TIMESTAMPTZ NOT NULL, inspector_signature_path VARCHAR(500),
 remarks TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_inspection_application ON inspection_records(application_id);

CREATE TABLE certificates (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), application_id UUID UNIQUE NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
 issued_by_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, certificate_number VARCHAR(50) UNIQUE NOT NULL,
 certificate_hash VARCHAR(128) UNIQUE NOT NULL, hmac_signature VARCHAR(128) NOT NULL, issue_date TIMESTAMPTZ NOT NULL,
 expiry_date TIMESTAMPTZ NOT NULL, status certificate_status NOT NULL DEFAULT 'ACTIVE', revoked_reason VARCHAR(500),
 pdf_path VARCHAR(500), qr_code_path VARCHAR(500), last_alert_sent_offset_days INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cert_expiry ON certificates(expiry_date);

CREATE TABLE tamper_reports (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), reference VARCHAR(40) UNIQUE NOT NULL, query_value VARCHAR(150) NOT NULL,
 jurisdiction VARCHAR(150), reason VARCHAR(500) NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'OPEN',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE advisories (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), title VARCHAR(200) NOT NULL, message TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tamper_status ON tamper_reports(status);
CREATE INDEX idx_advisory_created ON advisories(created_at DESC);

-- Demo accounts (replace passwords immediately in production).
-- Password for all demo users: Demo@123
