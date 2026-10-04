# Implementation notes

## Authority and persistence

FastAPI validates typed requests and serializes mutations under a process-local lock. SQLite stores complete session snapshots; LangGraph stores workflow checkpoints separately. Run one backend worker. Expert-confirmed policy and authoritative sandbox facts remain distinct from provider observations and transcripts.

## Versioned knowledge

Corrections are proposals against a specific map version and prior rule. The expert reviews the changed supported fields before applying them. A later correction archives the approved map and creates a draft requiring teach-back and explicit confirmation. Training remains pinned to its selected approved version.

## Challenge generation and grading

Seeded templates are conditioned on approved rule parameters and carry source rule/evidence provenance. Each case is independently checked to isolate its intended violation. Practice permits recorded assistance; the separate assessment refuses tutor hints. The save gate evaluates case facts against the approved rules, while the explanation rubric remains a limited English heuristic.

## Interaction and capture

Automatic prompts use local activity, screen stability, speech state, and bounded cooldowns. Capture and audio require explicit controls. In-flight visual results are discarded if consent changes. Screen observations never establish an expert’s reasoning by themselves.

## Provider adapters

Official OpenAI and ElevenLabs SDKs are isolated behind server-side adapters with bounded timeouts. Permanent credentials stay out of browser code. Automated provider checks use mocked HTTP responses; live in-app behavior needs the manual check described in [LIVE_SETUP.md](LIVE_SETUP.md).

## Packaging

The frontend compiles into static assets served by unprivileged Nginx. The backend installs locked dependencies and runs as a non-root user. Compose health checks and the persistent data volume support a localhost or private SSH deployment. See [DEPLOYMENT.md](DEPLOYMENT.md).
