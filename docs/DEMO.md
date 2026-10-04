# Interactive walkthrough

Run the simulated demo without OpenAI or ElevenLabs credentials. All review data and company policies are fictional. Browser speech is **demo audio**, not a live provider conversation.

## Start now

Prerequisites: Python 3.11+, uv, and Node.js 22.12+ (or a compatible newer version). From the repository root, once:

```bash
test -f .env || cp .env.example .env
uv sync --frozen
npm ci --prefix frontend
```

Terminal 1, from the repository root:

```bash
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2, from the repository root:

```bash
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173. Keep both services bound to loopback. Existing `.env` values are preserved; leave credentials empty for the simulated demo.

## Mac audio check (30 seconds)

1. Use Chrome or Safari with system volume up and the tab unmuted. Start **simulated demo**, then give recording consent.
2. Click **Enable demo audio**. You should hear a short browser voice sample. Click **Test voice** and listen again.
3. Ask a question; **Replay question** repeats it. **Stop voice** cancels playback; **Mute audio** disables it. Re-enable with an explicit click. Pause/off-record also stops playback.
4. If nothing is audible, check system output device, tab mute, and volume; stop playback and retry Test voice. Voices may load asynchronously; an available English voice or the browser default is used. The displayed completion means the speech API completed, not proof that sound reached the speakers. Typed answers remain available.

## 3–5 minute walkthrough

1. **Capture (60–90 seconds).** Start simulated demo and consent. Enable/test audio. On Case B, save **Hold** with “The report must match the release.” Click **Start capture**. Avoid typing/clicking for about four seconds; the apprentice asks automatically. Audio, recent interaction, pending answers, unstable shared frames, and an eight-second cooldown defer questions. Choose **Play scripted answer** for each of the three conditions. The coverage question is counterfactual. **Ask now** can skip timing delays; **Let me finish** resets the quiet period. Scripted answers are labeled. Actual screen sharing is optional and separate from automatic sandbox capture.
2. **Debrief and correction (60 seconds).** Start debrief. Use all three demo answers. In the correction field enter exactly: **Also require security regression tests before approval.** Review the proposed correction: required scope changes from empty to security regression. Apply it. Other wording can use **Edit supported fields explicitly**; credential-free extraction recognizes controlled examples only. Review teach-back and explicitly confirm the displayed map version.
3. **Challenges (45 seconds).** In Work Map, inspect a rule and open a real stored evidence link. Review and approve both challenges. Their displayed source rule, seed, evidence, and map version describe controlled templates. The revised coverage rule produces a practice case missing security regression coverage; the assessment isolates reviewer independence. Begin training.
4. **Learner mistake and correction (45 seconds).** Submit **Ready for approval**, “All tests passed.” The first answer is retained, but the unsafe case decision does not save. Ask for expert evidence, then submit **Hold**, “Missing security regression test coverage.” Hold and Escalate are safe alternatives when the rule fails. Complete unseen assessment with **Hold**, “The reviewer is the same person as the author.” Hints are disabled in assessment.
5. **Results and versions (30 seconds).** View Results. Distinguish independent, corrected, and hinted outcomes. A later approved-map correction creates a new draft requiring teach-back/confirmation while old training remains pinned. Use **Use approved vN** only when intentionally switching training; prior maps and answers remain stored.

## Status and limitations

| Capability | Submission status |
| --- | --- |
| Credential-free capture → correction → confirmation → challenges → results | Implemented with controlled scripts and deterministic checks |
| Browser demo audio | Explicit controls and speech API checks; audible output needs the Mac check above |
| Automatic timing | Local heuristic with fake-clock tests; cannot observe typing outside this app or prove reading finished |
| Corrections | Reviewed typed changes, preserved exact words/history; simulated examples or explicit fields without credentials |
| Challenges | Approved-rule-conditioned seeded templates, checked for unintended violations; no model-generated ground truth |
| Real screen sharing | Browser API implemented; automation uses synthetic streams; OS picker/permissions require manual verification |
| Live ElevenLabs/OpenAI | Adapters exist; no real credentialed session has been verified |
| Docker/deployment | Static Nginx frontend, non-root backend, readiness checks, and deployment guide; local Docker runtime unavailable |

Live voice needs `ELEVENLABS_API_KEY`, private interviewer/tutor agent IDs, account-side prompts/tools, and microphone permission. Live extraction/vision needs `OPENAI_API_KEY`. See [LIVE_SETUP.md](LIVE_SETUP.md). Missing settings produce setup guidance; live mode never silently becomes simulated. Controlled extraction fixtures and mocked provider tests are not evidence of broad real-model understanding.

The small English explanation rubric can require rephrasing; results do not establish mastery, certification, or compliance. Off-record stops new capture/audio and preserves existing evidence. Session deletion removes local artifacts, not provider copies or backups. See [LIMITATIONS.md](LIMITATIONS.md).
