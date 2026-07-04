# SafeWalk Mumbai — Test Credentials

## Mock OTP (development/testing only)

- OTP code: **123456** (works for any phone number)
- Any Indian-format phone number will work, e.g. `+919999999999`, `+918888888888`

## Typical test users to create via onboarding

- Phone: `+919999999999`
  - Name: Aditi
  - Emergency contacts: ("Amma", "+919111111111"), ("Papa", "+919222222222"), ("Rohan", "+919333333333")
  - `is_volunteer`: false

- Phone: `+918888888888`
  - Name: Meera (Volunteer)
  - Emergency contacts: ("Sister", "+919444444444")
  - `is_volunteer`: true (so the volunteer inbox entry appears on the Home screen)

## Notes for testing agent

- No real SMS is sent. OTP is entirely mocked in `/api/auth/verify-otp`.
- The backend runs on `:8001` internally and is exposed under `/api/*` via ingress.
- Frontend uses `EXPO_PUBLIC_BACKEND_URL` from `frontend/.env`.
