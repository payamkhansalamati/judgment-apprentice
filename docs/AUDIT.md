# Release review — 2026-10-04

The review covered backend contracts, policy evaluation, map correction/versioning, challenge generation, persistence, provider adapters, capture/privacy boundaries, React navigation/training/audio, browser tests, dependencies, Docker configuration, and public documentation. This is a source review and reproducible local verification, not an independent security certification.

## Completed changes

- Replaced the frontend’s Vite preview container with a multi-stage static build served by unprivileged Nginx. Added same-origin HTTP/WebSocket proxying, readiness, bounded request bodies, and asset caching.
- Preserved the non-root backend and persistent volume, added bytecode-write suppression and container security/restart settings, and made the published backend port configurable while retaining localhost bindings.
- Excluded the entire local artifact workspace and generated media from Git and Docker build contexts. Kept `.env`, session data, dependencies, and caches excluded. Existing local files are preserved.
- Added a publication audit for candidate files and Git history. It checks protected paths, known local credentials, common secret patterns, and oversized files without displaying credential values.
- Added a supported deployment guide for local containers and private remote access through SSH. Rewrote the README, walkthrough, and implementation notes around current behavior.
- Added GitHub CI for backend/frontend/browser checks and container build/startup verification.
- Bounded ElevenLabs signed-URL requests to a 20-second SDK timeout and omitted both provider keys from settings representations. Added a regression check.
- Made browser checks use configurable isolated server ports, clear live-provider credentials, and clean up through the frontend proxy. Existing application servers remain untouched.

The correction, version-pinning, challenge approval, learner save gates, evidence links, timing controls, and audio controls passed their existing targeted and end-to-end tests. No broad application refactor was needed.

## Final verification

| Check | Actual local result |
| --- | --- |
| Backend Ruff, including maintenance scripts | Passed |
| Backend pytest | **58 passed** |
| Frontend ESLint, Prettier, strict TypeScript | Passed |
| Frontend production build | Passed; existing large-chunk advisory remains |
| Playwright on installed Chrome | **11 passed** on isolated ports 18000 / 4173 |
| Frontend locked dependency audit | No reported vulnerabilities |
| Backend locked runtime dependency audit | No known vulnerabilities reported |
| Publication files/history audit | Passed: **71 candidate files, 1 history commit** |
| Compose schema validation | Passed against the official Compose specification |
| Deployment smoke script | App shell, readiness, simulated session API, and WebSocket event delivery passed against the isolated Vite/backend pair |
| Git diff whitespace check | Passed |

The smoke check creates and deletes its own synthetic session and deliberately creates an evidence event before checking stream delivery. The local check validates the script and application contract; it does not establish Nginx/container execution.

## Remaining checks and limits

**Actual blocker:** Docker is not installed on this machine. Image builds, Nginx runtime configuration, container health checks, and volume behavior have not been exercised locally. The CI container job is configured to perform the build/startup and proxy checks after publication; no remote CI result is claimed yet.

Live in-app OpenAI vision and ElevenAgents interviewer/tutor conversations still require the manual smoke check. Automated SDK tests use mocked provider HTTP responses. Real OS screen/microphone permission journeys and audible browser output remain manual checks.

The app intentionally remains single-user, unauthenticated, and limited to supported fictional policy types. Public application hosting requires further identity/ownership and HTTPS work. Bundle-size optimization and additional visual polish remain future improvements; they do not block sharing the source.

No commit, GitHub push, public deployment, or paid provider request was performed during this review.
