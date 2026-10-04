# Render public demo

This is one Docker web service: FastAPI serves the compiled React frontend, API routes, and WebSockets. Public mode uses seeded fictional cases, disables live providers and real capture uploads, and checks an unguessable HttpOnly visitor cookie on session reads, writes, evidence, deletion, and WebSockets. Global session listing and the listing-based reset script are disabled. Visitors can delete their own sessions.

## Exact dashboard settings

1. In [Render](https://dashboard.render.com/), select **New → Web Service**, then connect `https://github.com/payamkhansalamati/judgment-apprentice`.
2. Configure:

   | Field | Value |
   | --- | --- |
   | Name | `judgment-apprentice-demo` or another available name |
   | Branch | `main` |
   | Language / Runtime | `Docker` |
   | Root Directory | Empty (repository root) |
   | Dockerfile Path | `./Dockerfile.render` |
   | Docker Build Context Directory, if shown | `.` |
   | Docker Command | Empty; use Dockerfile CMD |
   | Instance Type | `Free` |
   | Health Check Path | `/ready` |
   | Instances | One |
   | Persistent disk | None |

3. Set `JA_PUBLIC_DEMO=true`. The Dockerfile supplies `JA_FRONTEND_DIR=/app/frontend_dist` and `JA_DATA_DIR=/tmp/judgment-apprentice`. Render supplies `PORT` and `RENDER_EXTERNAL_URL`. Do not add API keys, upload `.env` files, import local data, or attach a database. For a custom domain, set `JA_PUBLIC_ORIGIN` to its exact HTTPS origin.
4. Deploy. Wait for a successful build and health check, then open the HTTPS URL shown by Render.
5. Start **simulated demo**, consent to the synthetic review, and follow capture → debrief → corrections/teach-back → confirmed Work Map → approved challenges → training → results. Optional browser speech stays labeled simulated. Live-session and real-screen-upload controls are hidden.
6. Verify two visitors using separate browser profiles or a normal/private window. Their sessions must be separate. `/api/sessions` is deliberately forbidden. Unknown API paths return JSON errors, not the frontend.

Uvicorn binds to `0.0.0.0:${PORT:-10000}` with **one worker**. The build uses `npm ci` and `uv sync --frozen --no-dev` with the existing lockfiles. The root `.dockerignore` excludes credentials, local databases, recordings, and the local artifact workspace. See Render’s [Docker configuration](https://render.com/docs/docker), [environment variables](https://render.com/docs/environment-variables), and [health checks](https://render.com/docs/health-checks).

## Demo lifetime

Data and ownership are ephemeral and may reset on service restart, redeploy, or spin-down. An expired session is cleared in the frontend so the visitor can start again. The public banner explains this. Use fictional information only.

Render Free may take about a minute to wake after inactivity and loses local files on restart/redeploy/spin-down. Open it shortly before presenting. No paid resource or persistent disk is required. See [Free limitations](https://render.com/docs/free).

## Verify locally

Build with `npm run build --prefix frontend`, then run the production journey on a free local port:

```bash
JA_E2E_PUBLIC_DEMO=true JA_E2E_FRONTEND_PORT=4173 PLAYWRIGHT_CHANNEL=chrome npm run test:e2e --prefix frontend -- e2e/journey.spec.ts e2e/public-demo.spec.ts
```

This starts and stops one FastAPI service serving production files. Cookies are Secure on HTTPS and HttpOnly/SameSite=Strict in both environments.

If Docker is installed:

```bash
docker build -f Dockerfile.render -t judgment-apprentice-render .
docker run --rm -p 127.0.0.1:4173:10000 -e PORT=10000 -e JA_PUBLIC_ORIGIN=http://127.0.0.1:4173 judgment-apprentice-render
```

Docker is unavailable on the implementation machine; the actual image build remains untested locally.

## Verification record

- Relevant backend checks: **26 passed**, including ownership and live-provider refusal.
- Frontend lint, formatting, strict TypeScript, and production build: passed.
- Production browser checks: **2 passed**, including the complete existing correction/confirmation/training journey and visitor isolation. The live-mode test is intentionally skipped in public mode.
- Docker CMD expands a custom `PORT` correctly and explicitly uses one worker.
- Docker image build: **untested locally because Docker is unavailable**. Render deployment itself has not been performed from this workspace.
