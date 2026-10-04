# Judgment Apprentice

An expert’s checklist tells a newcomer what to inspect. Judgment Apprentice captures why the expert stops, what evidence matters, and when a decision needs escalation.

The application follows a fictional software-release review from expert explanation to learner assessment. It combines a React workspace, a FastAPI backend, SQLite persistence, and a checkpointed LangGraph workflow. The complete simulated workflow runs without API keys.

## What you can do

- Capture a synthetic review and the expert’s explanations, with explicit consent and off-record controls.
- Explore counterfactual questions and resolve gaps during debrief.
- Review proposed corrections, inspect their diff, and explicitly confirm a versioned Work Map.
- Follow rules back to stored evidence and preserve older approved versions.
- Approve rule-conditioned practice and assessment cases before training begins.
- Block unsupported approval attempts and distinguish independent, corrected, and assisted learner outcomes.
- Optionally connect OpenAI visual observations and private ElevenLabs interviewer/tutor agents.

Expert confirmation governs policy. Model observations and generated proposals do not independently approve a rule or save a review decision. Simulated answers, browser speech, and live provider interactions are labeled separately.

## Public hackathon demo on Render

Use the [single-service Render deployment](docs/RENDER.md). `Dockerfile.render` builds React and serves it through FastAPI on the same public origin. Public mode enables only the simulated journey, blocks live providers and real uploads, and isolates visitor sessions. Demo data may reset when the hosting service restarts.

## Quick start with Docker

Requires Docker Engine or Docker Desktop and Docker Compose **2.24 or later**.

```bash
test -f .env || cp .env.example .env
docker compose up -d --build --wait
```

Open **http://127.0.0.1:4173**. Readiness is available at `http://127.0.0.1:4173/ready`. No credentials are required for simulated mode.

The frontend serves a compiled static build through unprivileged Nginx. API requests and WebSocket events use the same origin. Both published ports bind to localhost; the backend runs as a non-root user and stores sessions in the `judgment-data` volume.

If port 8000 is occupied, choose a free backend port:

```bash
JA_BACKEND_PORT=8001 docker compose up -d --build --wait
```

Keep that variable set for subsequent Compose commands. Port 4173 must be available. Stop with `docker compose down`; this preserves stored sessions. See the [deployment guide](docs/DEPLOYMENT.md) for startup verification, private remote hosting, persistence, and updates.

## Local development

Requires Python **3.11+**, [uv](https://docs.astral.sh/uv/), and Node.js **22.12+**.

From the repository root:

```bash
test -f .env || cp .env.example .env
uv sync --frozen
npm ci --prefix frontend
```

Start the backend:

```bash
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Open **http://127.0.0.1:5173**. These ports must be available. The development proxy uses `JA_BACKEND_URL` when supplied; backend requests retain the localhost host boundary. Local sessions and workflow checkpoints are stored under `data/`.

## Try the workflow

1. Start **simulated demo**, grant capture consent, and save **Hold** on the release with mismatched report versions.
2. Start capture and answer the apprentice’s questions. Scripted answers are available explicitly in simulated mode. Browser audio is optional; use **Enable demo audio** and **Test voice**.
3. Complete debrief. Review a proposed correction or keep the initial rules, then review teach-back and explicitly confirm the displayed map version.
4. Inspect a rule and its evidence. Review and approve both challenge cases, then begin training.
5. Try **Ready for approval** on a failing case. The server retains the attempt but blocks the unsafe decision. Explain the actual failed condition and submit a safe decision.
6. Complete the separate assessment and inspect Results. Assisted practice and independent performance remain distinct.

The [interactive walkthrough](docs/DEMO.md) includes the supported security-regression correction example. Changes to an approved map create a new draft; existing training stays pinned to its selected approved version.

## Optional live integrations

Add credentials only to the ignored root `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
ELEVENLABS_API_KEY=
ELEVENLABS_INTERVIEWER_AGENT_ID=
ELEVENLABS_TUTOR_AGENT_ID=
```

Restart the backend after editing configuration. Keys stay server-side. Live mode requires private agents configured with matching client tools and browser microphone permission; it does not silently fall back to simulated answers. See [live setup](docs/LIVE_SETUP.md).

Readiness reports whether required configuration is present, not whether credentials are valid. Automated provider tests use the official SDKs with mocked HTTP responses. Live in-app vision and agent conversations still require an end-to-end manual check.

## Verification

```bash
uv run ruff check backend scripts
uv run pytest -q
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
python3 scripts/check_publication.py
```

For browser checks, install Chromium once:

```bash
npm exec --prefix frontend -- playwright install chromium
JA_E2E_BACKEND_PORT=18000 JA_E2E_FRONTEND_PORT=4173 npm run test:e2e --prefix frontend
```

The selected ports must be free. Browser tests launch isolated servers, leave existing servers alone, and clear provider credentials in the test backend. Frontend test ports must be 5173 or 4173 because the backend deliberately restricts browser origins. To use installed Google Chrome instead, set `PLAYWRIGHT_CHANNEL=chrome`.

GitHub Actions runs backend checks, frontend checks, browser tests, the publication audit, and a Docker build/startup smoke check. Its first remote run will establish container runtime validation; the current development machine has no Docker installation.

## Project layout

```text
backend/app/        API, workflow, policies, provider adapters, persistence
backend/tests/      Policy, API, versioning, privacy, and provider tests
frontend/src/       React workspace, capture controls, map, training, audio
frontend/e2e/       Browser journeys and timing/privacy checks
docs/               Architecture, deployment, walkthrough, and limitations
scripts/            Local maintenance and publication checks
compose.yaml        Localhost container deployment
```

## Boundaries

This is a single-user prototype with fictional policies and a small supported rule vocabulary. The explanation rubric is a deterministic English heuristic. Passing a case does not establish mastery or certification. Automatic question timing cannot observe activity outside this application.

The default local/live mode has no user authentication or tenant isolation; keep it on localhost or a private SSH tunnel. The Render public-demo mode checks visitor ownership and disables provider/capture endpoints, but remains a temporary synthetic demo rather than a production identity system. Keep one backend worker while the workflow uses its process-local mutation lock.

Capture is opt-in. Off-record stops new capture and audio while preserving earlier evidence. Session deletion removes local artifacts; it cannot remove provider-side copies or external backups. See [limitations and privacy](docs/LIMITATIONS.md), [architecture](docs/ARCHITECTURE.md), and the [release review](docs/AUDIT.md).
