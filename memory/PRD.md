# SafeWalk Mumbai — Product Requirements Document

## Vision
A community-powered women's safety mobile app for Mumbai. One SOS button alerts verified women volunteers within 500 m and the user's emergency contacts with GPS location.

## Users
- Primary: Women 16–45 in Mumbai commuting alone, especially at night.
- Secondary: Volunteer women (verified) who respond to nearby SOS alerts.

## MVP Scope (shipped)
- **Phone OTP onboarding** (mocked; any 6-digit code accepted — `123456`) with name, 3 emergency contacts, language pick (EN/HI/MR), optional volunteer opt-in.
- **Walking Mode Dashboard** — stylised full-screen map, "I am walking alone" GPS toggle, giant 3-second press-and-hold red SOS button (≈28 % of screen height), route-safety color legend (green/yellow/red), volunteer inbox shortcut (visible only to volunteers), discreet-mode entry (music-note icon).
- **SOS Trigger** — 3-second press-and-hold (haptic + circular progress) OR shake-3× (via expo-sensors, when Walking Mode is on).
- **SOS Active State** — pulsing red screen, 10-second cancel countdown, live volunteer list with distance + ETA, real 60-second audio recording via expo-audio (loops), notified emergency contacts panel, cancel button.
- **Discreet Mode** — full music-player disguise with album art, controls, and secret 3-tap on play/pause to silently trigger SOS.
- **Volunteer Interface** — dedicated screen: incoming SOS card with location & distance, "I am responding" flow that shares volunteer identity for accountability.
- **Community Safety Map + Route Rating** — 1–5 stars + tags (no lights / unsafe crowd / well-lit-CCTV / lonely) + BMC flag. Aggregated pins render on community map with color coding.
- **Helplines** — one-tap dial for Nirbhaya (1091), Mumbai Police (100), Bandra & Andheri women's police stations, Ambulance (108).
- **Multi-language** — English, Hindi, Marathi; switchable from onboarding & profile; persisted with local storage.
- **Profile** — edit emergency contacts, toggle volunteer status, change language, logout.

## Backend API
- `POST /api/auth/send-otp` — mock send (returns hint "Use 123456").
- `POST /api/auth/verify-otp` — accepts only `123456`; returns `user_id` + `is_new`.
- `POST /api/users` — create user profile.
- `GET /api/users/{id}` / `PATCH /api/users/{id}` — read / update.
- `POST /api/sos` — create SOS incident; generates 4 nearby mocked volunteers (Priya, Ananya, Meera, Riya) with distances 80–480 m and computed ETA.
- `GET /api/sos/{id}` — poll incident state.
- `POST /api/sos/{id}/respond` — volunteer accepts.
- `POST /api/sos/{id}/simulate-response` — used by the app 4 s after trigger so a live "Responding" volunteer appears in the SOS screen.
- `POST /api/sos/{id}/cancel` — user cancels within 10 s.
- `POST /api/ratings` + `GET /api/community/pins` — route rating + aggregated map pins.
- `GET /api/helplines` — helpline directory.

## Mocked pieces (clearly flagged)
- **MOCKED OTP delivery** — no real SMS. Any phone works; code is always `123456`.
- **MOCKED SMS to emergency contacts** — the SOS payload lists the contacts as "notified" but no real SMS is sent (was chosen for the MVP to avoid Twilio dependency).
- **MOCKED nearby volunteers** — server generates 4 realistic profiles per SOS.
- **MOCKED ID + selfie verification** — opt-in on onboarding sets `id_verified=true`.

## Non-goals for MVP (Phase 2)
- Real Twilio/MSG91 SMS fallback.
- USSD feature-phone fallback.
- Corporate/institution dashboards, subscription tiers.
- Real end-to-end encryption of location (currently in-transit HTTPS only).

## Smart business enhancement (Next Action)
- Add a **"Safe Corridor" partner program** — verified retail stores / cafés / auto-stands display a small SafeWalk badge in the map. Store owners pay a small monthly listing fee for foot-traffic + goodwill, and users get an extra safe waypoint mid-route. This creates a sustainable revenue loop without touching the core free safety feature.
