# Judgment Apprentice

**Capture expert judgment. Verify it. Teach the next generation.**

“All tests passed. So why did the expert stop the release?”

This local hackathon MVP captures a software reviewer’s reasoning, links it to stored evidence, asks for an explicit teach-back confirmation, and teaches a newcomer with unseen cases. The synthetic review portal uses **fictional company policies**. It makes no certification or standards-compliance claims.

The default **simulated demo** runs without paid API credentials. Scripted questions and answers use browser speech synthesis and are visibly identified, as are simulated model observations. Browser screen sharing is available independently of live AI. Live ElevenLabs voice and OpenAI vision use separate adapters and require setup; real provider sessions have not been exercised with credentials.

## Local setup on macOS

Install Python 3.11 or newer, `uv`, and Node.js 22.12+ (or a compatible newer version). The project uses Python and npm lockfiles. Run these commands in the repository:

```bash
cd /Users/payam/Documents/judgment-apprentice
cp .env.example .env
uv sync --frozen
cd frontend
npm ci
cd ..
```

Keep `.env` local and ignored. Leave its API key values empty for the simulated demo. No keys belong in a `VITE_` variable or browser bundle.

Start the backend in one terminal:

```bash
cd /Users/payam/Documents/judgment-apprentice
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```bash
cd /Users/payam/Documents/judgment-apprentice/frontend
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173**. The API documentation is at **http://127.0.0.1:8000/docs**. This MVP has no user authentication; keep both services bound to loopback. Explicit allowed browser origins are localhost/127.0.0.1 on ports 5173 and 4173.

If macOS or the browser refuses screen sharing, allow the browser in System Settings → Privacy & Security → Screen & System Audio Recording, restart the browser if requested, and retry using the app’s explicit sharing control. The system picker decides which surface is shared. Typed interaction remains available when microphone permission is denied.

## Try the complete journey

1. Choose **Start simulated demo** and select **I consent to capturing this synthetic review and its answers.**
2. In **Expert workspace**, review A, B, and C. Use **Ask now** and **Play scripted answer** for the three conditions, including the counterfactual and independent-review guardrail.
3. Choose **Start debrief**, answer all three gaps with **Use demo answer**, then enter “Only if tests cover every changed functionality, versions match, and an independent reviewer signs off.” and choose **Save expert correction**.
4. Choose **Review teach-back**, then **Confirm this map** for the current version. Approve the two generated challenge templates before assessment.
5. Try “Ready for approval” on the first unseen case. The server records the first answer but blocks the unsafe save. Inspect linked evidence, then correct to Hold.
6. Complete the unseen assessment and inspect independent/assisted outcomes in Results.

The full recording guide is in [docs/DEMO.md](docs/DEMO.md). It is a storyboard and script; no demo video is generated.

## Persistence and resetting synthetic data

Sessions, cases, evidence, Work Maps, and attempts are stored in `data/app.sqlite`. LangGraph checkpoints are stored in `data/workflow.sqlite`. Refreshing the browser preserves approved work.

Create a new session to get the same seeded expert cases and a clean workflow. To remove all simulated sessions and their local derived artifacts, keep the backend running and use:

```bash
uv run python scripts/reset_demo.py
```

The reset script preserves live sessions. After reset, choose **Start simulated demo** to seed a new session. Open a session and use **Delete session**, then **Delete session and evidence** to remove its local evidence, archived map versions, challenges, attempts, and checkpoint thread. API equivalents:

```bash
curl -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"mode":"simulated"}'

# Replace SESSION_ID with the id returned by the create endpoint.
curl -X DELETE http://127.0.0.1:8000/api/sessions/SESSION_ID
```

Local deletion does not remove provider-side recordings or independent backups and does not guarantee secure erasure of every SQLite/journal file. See [privacy and limitations](docs/LIMITATIONS.md).

## Checks

From the repository root:

```bash
uv run ruff check backend
uv run pytest
```

From `frontend`:

```bash
npm run lint
npm run typecheck
npm run build
npx playwright install chromium

# Stop any existing backend/frontend servers first; Playwright starts both.
npm run test:e2e
```

On macOS 13, where the current Playwright Chromium download may be unsupported, use an installed Google Chrome instead:

```bash
PLAYWRIGHT_CHANNEL=chrome npm run test:e2e
```

Paid integrations are mocked in automated tests. A passing mock test validates the adapter contract, not a live account, voice quality, microphone permission, or browser picker.

`GET /health` reports that the API process responds. `GET /ready` also checks SQLite storage and checkpoint connectivity and reports whether live credentials are configured. “Configured” does not verify credentials or provider availability.

## Live setup and architecture

[Live setup](docs/LIVE_SETUP.md) describes the two private ElevenLabs agents, local environment variables, conversation context, and supported client tools. Missing live credentials produce a setup error; a live session never silently becomes simulated.

[Architecture](docs/ARCHITECTURE.md) explains the workflow, policy gate, event contract, and capture boundaries. [Acceptance checklist](docs/ACCEPTANCE.md) maps the requested behaviors to implementation and verification. [Limitations](docs/LIMITATIONS.md) records practical gaps.

## Local containers

After the local checks pass, use Docker with Compose 2.24 or newer:

```bash
cd /Users/payam/Documents/judgment-apprentice
# Stop the local backend first so port 8000 is free.
docker compose up --build
```

Open **http://127.0.0.1:4173**. The backend remains accessible at **http://127.0.0.1:8000**. Both published ports bind to loopback. The frontend uses Vite preview to serve its production build and proxy API/WebSocket calls to the backend container. This is a local reproducibility setup.

The root `.env` is optional: an absent file starts the credential-free demo; an existing file supplies only the backend's live settings. Secret files, local databases, caches, and dependency folders are excluded from image build contexts. Compose 2.24+ supports the [optional environment file](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/); Python dependencies use the frozen lockfile and the [documented uv container workflow](https://docs.astral.sh/uv/guides/integration/docker/).

Container evidence lives in the named `judgment-data` volume, separately from the local `data/` directory. Use the app's session deletion control to remove a session. Stop containers without deleting that volume with `docker compose down`.

Docker is unavailable on the implementation host, so image builds and Compose startup have not been exercised. No service was published, pushed, or provisioned.
