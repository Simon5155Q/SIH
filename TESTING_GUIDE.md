# e-Verify Legal Metrology Testing Guide

This guide covers the authenticated workflows, security checks, and staging panel scenarios for the Legal Metrology e-Verify system.

## 1. Start the services

1. Open a terminal in the backend folder:
   - `d:\vsc\legal-metrology-api`
2. Start the FastAPI server:
   - `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
3. Open the frontend app in a browser:
   - `d:\vsc\frontend\login.html`
   - or open `http://127.0.0.1:8000/staging-test` after the API is running

## 2. Seed demo users

Run the demo seeder once before tests:

- In `d:\vsc\legal-metrology-api`
- Command:
  - `python scripts/seed_demo.py`

Default credentials:

- Admin: `admin@example.com` / `Demo@123`
- Field Officer: `officer@example.com` / `Demo@123`
- Public Consumer: `consumer@example.com` / `Demo@123`

## 3. Login scenarios

### Scenario A: Valid JWT login

1. Open the browser login page at `frontend/login.html`.
2. Sign in with one of the seeded accounts.
3. Confirm that the browser stores a JWT token in local storage and redirects to a protected dashboard.
4. Open the browser devtools and inspect:
   - `lm_token`
   - `lm_user`

Expected result:
- Login succeeds with a 200 response.
- Response contains `access_token` and `user` data.
- Token is used as a Bearer token on protected API calls.

### Scenario B: Invalid password

1. Enter a wrong password for any seeded user.
2. Submit the form.

Expected result:
- API returns a 401 or 400 error.
- No JWT is saved to local storage.

### Scenario C: JWT bearer enforcement

1. Log out or clear `lm_token` in devtools.
2. Call a protected route such as:
   - `http://127.0.0.1:8000/api/v1/dev/seed`
3. Submit without a Bearer token.

Expected result:
- Request is rejected with an authentication error.

## 4. Staging Test Interface scenarios

Open the dedicated staging portal:

- `http://127.0.0.1:8000/staging-test`

### Scenario D: Identity switcher

In the right-side panel, click each role button:

- Login as Field Officer
- Login as Public Consumer
- Login as Department Admin

Expected result:
- The header updates with the selected role.
- `lm_user` stores the selected user profile.
- The token is stored locally and remains usable for testing routes.

### Scenario E: GPS geofencing checks

Use the GPS presets in the inspection card:

- On-Site (0m delta)
- Near Boundary (180m delta)
- Out of Bounds (350m delta)

Expected result:
- On-site: passes geofence or remains valid.
- Boundary: near threshold, should be treated as edge-case valid or rejected depending on implementation details.
- Out of bounds: should fail the inspection or be flagged as invalid.

### Scenario F: HMAC QR token validation

1. Click the QR token dropdown in the testing panel.
2. Choose the valid token option.
3. Click `Inject Test Token` to verify it through the real verification endpoint.
4. Then trigger the tampered token path.

Expected result:
- Valid token verifies successfully.
- Tampered token fails with `Invalid or tampered certificate signature`.
- The stateless HMAC verification must not require a database hit.

### Scenario G: PDF certificate streaming

1. Ensure you are logged in.
2. In the staging page, click `Generate Certificate`.
3. The portal should render the PDF inline in an iframe.

Expected result:
- A PDF is returned from `GET /api/v1/staging/certificate.pdf`.
- Response is returned as a binary PDF stream.
- No static PDF file is written to disk.

### Scenario H: Offline queue simulation

1. Toggle network to offline in the panel.
2. Click `Queue Sample Record`.
3. Observe the queue count grow.
4. Reconnect and click `Sync Now`.

Expected result:
- Records remain queued while offline.
- Sync resumes when the network returns.
- The queue count drops after successful remote sync.

### Scenario I: Seed route for admin-only control

1. Log in as the admin user.
2. Click `Seed Test Data` from the testing panel.

Expected result:
- Request succeeds because the route is protected with admin role requirements.
- New test officers and sandbox scales are created.

## 5. API checks to run directly

These are the most important route checks to confirm service health and security behavior.

### Public health

- `GET http://127.0.0.1:8000/`
- Expected: `{"status":"healthy"}`

### Auth login

- `POST http://127.0.0.1:8000/api/v1/auth/login`
- Body:
  ```json
  {
    "email": "admin@example.com",
    "password": "Demo@123"
  }
  ```
- Expected: JWT access token returned.

### Sample QR token

- `GET http://127.0.0.1:8000/api/v1/dev/sample-token`
- Expected: `valid_token` and `tampered_token` in the response.

### Token verification

- `GET http://127.0.0.1:8000/certificates/verify-token?token=...`
- Expected: payload reveals `verified: true` for a valid token.

### Staging PDF

- `GET http://127.0.0.1:8000/api/v1/staging/certificate.pdf`
- Header must include `Authorization: Bearer <token>`.
- Expected: PDF content type and successful inline response.

## 6. Acceptance checklist

Use this final checklist before sign-off:

- [ ] Backend starts on port `8000`.
- [ ] Demo users are seeded with the correct credentials.
- [ ] Login returns a valid JWT.
- [ ] Protected admin route rejects calls without a bearer token.
- [ ] The staging page loads at `/staging-test`.
- [ ] Identity switcher updates the active role.
- [ ] HMAC valid token succeeds.
- [ ] Tampered HMAC token fails as expected.
- [ ] Geofence presets simulate the required boundary conditions.
- [ ] PDF certificate streams in-memory without a static file write.
- [ ] Offline queue sync works after reconnect.

## 7. Troubleshooting

If a route fails:

1. Confirm the backend is running.
2. Confirm the database is reachable.
3. Re-run the demo seed script.
4. Check that the JWT is present in the browser or in the request header.
5. Verify the correct route prefix:
   - `/api/v1/auth/login`
   - `/api/v1/dev/sample-token`
   - `/api/v1/staging/certificate.pdf`

This guide is intentionally narrow and explicit so it can be used by judges, QA engineers, and developers for repeatable acceptance testing.
