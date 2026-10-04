# Limitations and privacy

This is a single-user local hackathon MVP using synthetic data and fictional company policies. It does not claim certification, standards compliance, or readiness for real confidential review data.

## What is simulated and what is live

The simulated journey uses deterministic seeded cases, scripted companion questions/answers, and explicit simulated observation events. It works without paid credentials. Actual browser screen sharing can be used in simulated mode, but no vision provider is invoked there. Simulated questions and answers can play through browser speech synthesis; they do not use a live AI speech service.

Real SDK adapters exist for OpenAI vision observations and private ElevenLabs interviewer/tutor conversations. Provider calls are mocked in automated tests. No live account connection, agent prompt behavior, paid vision request, microphone recording, or production audio quality has been verified with credentials. Account-side agent configuration and network/browser permissions remain necessary. Voice transcript evidence does not automatically choose a map rule or fill a debrief answer; the expert explicitly records the relevant explanation in the app. Live errors are surfaced; live mode has no silent simulation fallback.

## Recording controls and retention

Capture requires explicit app consent and the browser’s sharing picker. A visible indicator shows active capture. User-configured masks obscure known screen regions before transmission; they do not automatically detect every name, credential, face, or personal detail. Review the chosen surface and masks yourself.

Off-record stops new screen capture and ends the voice connection. The backend rejects new recording inputs and discards late frame results after an off-record transition. A provider request already transmitted may still complete, and previously sent audio/images cannot be recalled. Microphone mute alone does not stop screen sharing, end the provider conversation, or erase existing evidence. Explicit sandbox decisions can still update the current case off record, with capture events suppressed. Learner attempts/hints, map confirmation, recording inputs, and voice tool context require recording consent and an on-record session.

Local evidence can contain the resized, masked JPEG frame, observed summaries, transcript snippets, expert answers, and learner attempts. Session deletion removes the session document (including archived maps and derived challenges/attempts) and its LangGraph checkpoint thread, making old API evidence references invalid. SQLite secure-delete is enabled to overwrite deleted content in the active database. This is not a secure-erasure guarantee for journals, filesystem/operating-system snapshots, developer backups, or browser/provider caches.

OpenAI observation requests set `store=False`, but that does not establish zero retention of every provider log or previously transmitted payload. Deleting a local session does not call OpenAI or ElevenLabs deletion APIs and cannot remove their recordings or logs. External retention depends on your provider account configuration and applicable provider policies. Verify those settings before sending anything beyond synthetic data. No API keys or raw provider payloads are deliberately logged.

## Engineering boundaries

- There is no login or ownership identity. Session UUID and local-origin checks validate context, not authenticated authorization. Bind to `127.0.0.1`; do not expose the API or Compose ports publicly.
- SQLite session documents and in-process write/frame guards are intended for one local backend worker. There is no distributed lock, job recovery, schema migration framework, or production backup strategy.
- Controlled challenge templates cover the implemented fictional policy checks. They do not generate arbitrary expert workflows, interpret new free-form policies, or automatically resolve novel exceptions.
- Expert explanations and corrections are stored verbatim as evidence. Their wording cannot redefine the supported typed checks or the separate baseline approval gate. Confirmation validates types and evidence, but does not detect a contradictory free-form explanation; the expert must check that the reason agrees with the displayed rule title/type before confirming.
- Scoring compares the decision with the deterministic expected decision and checks supported English policy concepts with a small keyword rubric. It may ask a learner to rephrase a valid explanation and does not perform general semantic grading or establish professional competence.
- Question timing is a heuristic based on available SDK speech state, app interaction, frame stability, and cooldown. It cannot prove a reviewer has finished reading or detect typing/clicks in arbitrary external applications.
- A validated visual observation is still fallible. It is not proof of a sandbox field, an expert quotation, a hidden click, or intent. Authoritative policy checks use stored case fields.
- Browser automation verifies typed simulated flows. Real screen pickers, device permissions, operating-system capture controls, and live voice require a separate manual check in the chosen browser.
- Local container definitions are supplied for reproducibility. They do not supply production authentication, TLS, reverse-proxy hardening, paid resources, or hosting.

The acceptance checklist separates implemented paths from checks that require a live account or manual browser interaction. No demo footage is claimed.

Live tutor endpoints require the selected practice challenge’s first recorded answer. Assessment challenges refuse live tutor assistance, and successful tutor URL/context access counts as assistance for later scoring. Account-side prompts still control phrasing; the server controls evidence access and saves.
