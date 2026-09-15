# Legal Metrology Online Verification System - Full Stack

This package combines the supplied Stitch frontend pages with a working FastAPI backend and database layer without redesigning the supplied frontend.

## Run locally
1. Open a terminal in this folder.
2. Windows: run `run_windows.bat`
3. Linux/macOS: run `./run_linux.sh`
4. Open `http://localhost:8000/`
5. API docs: `http://localhost:8000/docs`

## Demo logins
- Trader: trader@example.com / Demo@123
- LMO: lmo@example.com / Demo@123
- GATC: gatc@example.com / Demo@123
- Admin: admin@example.com / Demo@123

## Pages
- `/` public portal
- `/merchant.html` trader dashboard
- `/lmo.html` LMO field inspection
- `/admin.html` state controller admin console
- `/verify.html` public certificate/hologram verification

## Database
The local demo automatically creates `backend/legal_metrology.db` (SQLite) and seeds sample users/instruments.
`database.sql` contains the normalized PostgreSQL production schema for Supabase/PostgreSQL.

## Important
This is a functional local/demo integration. For production deployment, set a strong JWT secret, certificate HMAC secret, HTTPS, a managed PostgreSQL database, object storage, and proper role/account onboarding.
