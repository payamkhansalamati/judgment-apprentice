# Challenge acceptance checklist

This checklist describes implementation targets and verification scope. A checkmark means a path exists in the local MVP; it does not claim that a paid service or browser permission was exercised. Final command results belong in the verification record below.

| Requirement | Local acceptance evidence | Scope / remaining check |
| --- | --- | --- |
| [x] Synthetic expert cases A/B/C | Seeded complete, stale-report, and missing-coverage cases | All policies explicitly fictional |
| [x] Deterministic save gate | Current stored case evaluated; structured violations block Ready | Hold/Escalate remain available |
| [x] Required information and reviewer guardrail | Explicit missing-info and self-review checks | Pure Python, no generated code |
| [x] Explicit workflow and persistence | LangGraph checkpoint thread and SQLite session document | Single local backend worker |
| [x] Three nonrepetitive capture conditions | Version, counterfactual coverage, independent reviewer | Live spoken delivery requires configured agents |
| [x] Three new debrief gaps | Exceptions, escalation owner, missing evidence | Required gaps block teach-back/confirmation |
| [x] Explicit version confirmation | Current version plus explicit flag and resolving evidence | Approved edits require a new confirmation |
| [x] Evidence-linked knowledge | Stored answer/correction IDs, status, guardrails, owner/exception fields | Visual events remain separate from authoritative data |
| [x] Two controlled unseen challenges | Version mismatch and coverage/self-review variations | Expert template approval required |
| [x] Record independent answer before hint | Persisted first decision/reason and hint state | Small English policy-concept rubric, not general semantic grading |
| [x] Block unsafe learner save | Record attempted approval, return supported violations | Corrected answer may then save |
| [x] Reduced-assistance assessment | Independent case rejects hint requests | No invented mastery percentages |
| [x] Explicit simulated/live modes | No credentials needed for demo; live errors are actionable | No silent fallback |
| [x] Real provider adapters | Official ElevenLabs/Python/React and OpenAI SDK boundaries | Paid calls mocked; credentials untested |
| [x] Capture consent and bounded frames | Consent/off-record validation; 1.5 s sampling and one in-flight frame | Manual browser screen-picker check remains |
| [x] Resize and manual masks before transmission | Browser canvas resizes to max 960 px and masks configured regions | Does not detect all sensitive data |
| [x] Voice controls and typed fallback | Connecting/listening/speaking/disconnected, mute/pause/end, explicit errors | Live devices and account setup require manual checks |
| [x] Question timing controls | Ask now, Let me finish, Pause, app activity/stability/cooldown | Available speech signals are heuristics |
| [x] Product areas and clickable Work Map | Overview, Expert workspace, Debrief, Work Map, Training, Results | React Flow plus keyboard-accessible rule list |
| [x] Local deletion invalidates derived artifacts | Entire session body and checkpoint thread removed | No secure wipe/provider deletion claim |
| [x] Distinct health/readiness semantics | Process response versus persistence/configuration readiness | Configured flags do not validate a provider account |
| [x] Local CORS and event envelope | Explicit localhost origins, session-scoped WebSocket events | No login/ownership authentication |
| [ ] Live end-to-end interviewer/tutor | Follow LIVE_SETUP manual script | Requires user-owned private agents and credentials |
| [ ] Real OS screen/microphone permission journey | Browser picker, deny/retry, off-record stop | Cannot be proven by headless simulated tests |
| [ ] Local container runtime | Build and launch Compose on a Docker host | Record separately if Docker is unavailable |

## Verification record

Update with the actual commands and results after the final local verification. Do not infer success from the presence of test files or a mocked adapter.

- Backend policy/API pytest: **50 passed**, including mocked official SDK HTTP contracts.
- Backend Ruff lint and format checks: **passed**.
- Frontend strict TypeScript, ESLint, Prettier, and production build: **passed**. Build reports large dependency chunks; live voice is lazy loaded.
- Playwright: **5 passed** using installed Google Chrome on macOS 13. Covers the full expert correction/confirmation/assessment journey, live-mode labeling, masking/resize/backpressure, off-record screen permission races, and off-record microphone permission races.
- Paid OpenAI/ElevenLabs services: not exercised with credentials.
- Real microphone and OS sharing permission flow: manual verification required.
- Container runtime: not verified; Docker is not installed in the implementation environment.

The critical browser journey must cover expert correction → approved map → blocked unsafe learner save → learner correction. The backend suite must cover mismatched versions, missing coverage, self-review, required gaps, confirmation/version boundaries, assisted versus independent results, off-record behavior, and deletion of evidence/checkpoints.
