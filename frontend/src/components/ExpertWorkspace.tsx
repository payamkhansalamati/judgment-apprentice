import { useCallback, useEffect, useRef, useState } from "react";
import { MonitorUp, Pause, Play, ShieldCheck, Sparkles } from "lucide-react";
import { cancelDemoAudio, speakDemo, useDemoAudio } from "../demoAudio";
import { QuestionScheduler } from "../questionScheduler";
import type { Eligibility, Cue } from "../questionScheduler";
import { api } from "../api";
import type { Decision, Session } from "../contracts";
import { useScreenCapture } from "../useScreenCapture";
import { VoiceCompanion } from "./VoiceCompanion";
import { CaseCard } from "./CaseCard";
import { Timeline } from "./Timeline";
import { Button } from "./ui/button";

export function ExpertWorkspace({
  publicDemo = false,
  session,
  onSession,
  onError,
  onEvidence,
  onDebrief,
}: {
  publicDemo?: boolean;
  session: Session;
  onSession: (value: Session) => void;
  onError: (message: string) => void;
  onEvidence: (id: string) => void;
  onDebrief: () => void;
}) {
  const demoAudio = useDemoAudio();
  const [caseId, setCaseId] = useState("B");
  const [question, setQuestion] = useState<{ id: string; text: string }>();
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");
  const [decision, setDecision] = useState<Decision>("Hold");
  const [paused, setPaused] = useState(false);
  const [consentValue, setConsentValue] = useState(session.consent);
  useEffect(() => setConsentValue(session.consent), [session.consent]);
  const [queued, setQueued] = useState(false);
  const [busy, setBusy] = useState(false);
  const [maskEnabled, setMaskEnabled] = useState(true);
  const [maskHeight, setMaskHeight] = useState(0.16);
  const activity = useRef(Date.now());
  const [automatic, setAutomatic] = useState(false);
  const scheduler = useRef(new QuestionScheduler());
  const generation = useRef(0);
  const latestState = useRef<Eligibility>(null!);
  const abort = useRef<AbortController | null>(null);
  const agentSpeaking = useRef(false);

  const inFlight = useRef(false);
  const voiceSpeaking = useRef(false);
  const userSpeaking = useRef(false);
  const sharedBefore = useRef(false);
  const mounted = useRef(true);
  const activeCase =
    session.cases.find((c) => c.id === caseId) ?? session.cases[0];
  const capture = useScreenCapture({
    sessionId: session.id,
    enabled: !publicDemo && session.consent && !session.off_record && !paused,
    masks: maskEnabled ? [{ x: 0, y: 0, width: 1, height: maskHeight }] : [],
    onObservation: () => undefined,
    onError,
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cancelDemoAudio();
    };
  }, []);
  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    try {
      await task();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Request failed");
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  const speak = (text: string) => {
    if (session.mode === "simulated" && !paused && !session.off_record) {
      agentSpeaking.current = speakDemo(text, () => {
        agentSpeaking.current = false;
        scheduler.current.activity();
      });
    }
  };
  const condition = session.asked_questions.find(
    (id) => !session.known_conditions.includes(id),
  );
  latestState.current = {
    active: automatic,
    consent: session.consent,
    paused,
    offRecord: session.off_record,
    capturePhase: session.phase === "capture",
    userSpeaking: userSpeaking.current,
    agentSpeaking:
      voiceSpeaking.current ||
      agentSpeaking.current ||
      (window.speechSynthesis?.speaking ?? false),
    stable: !capture.active || capture.stability,
    pending: Boolean(condition) || inFlight.current,
    known: session.known_conditions,
  };
  const cancelQuestions = useCallback(() => {
    generation.current++;
    abort.current?.abort();
    scheduler.current.cancel();
    setQueued(false);
    setQuestion(undefined);
    cancelDemoAudio();
    agentSpeaking.current = false;
  }, []);
  useEffect(() => {
    if (sharedBefore.current && !capture.active) {
      cancelQuestions();
      setAutomatic(false);
    }
    sharedBefore.current = capture.active;
  }, [capture.active, cancelQuestions]);
  useEffect(() => {
    if (!automatic || paused || session.off_record || !session.consent) {
      cancelQuestions();
      return;
    }
    const cases: Record<string, string> = {
      version_match: "B",
      coverage: "C",
      independent_review: "A",
    };
    for (const event of session.events.filter((e) =>
      ["sandbox_decision", "sandbox_case_snapshot"].includes(e.event_type),
    )) {
      const key =
        event.payload.case_id === "B"
          ? "version_match"
          : event.payload.case_id === "C"
            ? "coverage"
            : "independent_review";
      if (!session.known_conditions.includes(key))
        scheduler.current.enqueue({
          id: event.event_id,
          condition: key,
          caseId: String(event.payload.case_id),
          priority:
            event.payload.decision === "Escalate"
              ? 0
              : event.event_type === "sandbox_decision"
                ? 1
                : 2,
        });
    }
    for (const key of Object.keys(cases))
      if (!session.known_conditions.includes(key))
        scheduler.current.enqueue({
          id: `guardrail-${key}`,
          condition: key,
          caseId: cases[key],
          priority: 3,
        });
    setQueued(
      !condition &&
        session.known_conditions.length < 3 &&
        scheduler.current.size > 0,
    );
  }, [
    automatic,
    paused,
    session.off_record,
    session.consent,
    session.events,
    session.known_conditions,
    condition,
    cancelQuestions,
  ]);
  const ask = useCallback(
    async (manual = false) => {
      const state = {
        ...latestState.current,
        userSpeaking: userSpeaking.current,
        agentSpeaking:
          voiceSpeaking.current ||
          agentSpeaking.current ||
          (window.speechSynthesis?.speaking ?? false),
        pending: latestState.current.pending || inFlight.current,
      };
      if (!scheduler.current.eligible(state, manual)) return;
      let cue: Cue | undefined;
      if (manual) {
        const key = ["version_match", "coverage", "independent_review"].find(
          (key) => !state.known.includes(key),
        );
        if (!key) return;
        cue = {
          id: `manual-${key}`,
          condition: key,
          caseId: (
            {
              version_match: "B",
              coverage: "C",
              independent_review: "A",
            } as Record<string, string>
          )[key],
          priority: 0,
          created: Date.now(),
        };
      } else cue = scheduler.current.next(state);
      if (
        !cue ||
        !scheduler.current.eligible(
          {
            ...latestState.current,
            pending: inFlight.current || latestState.current.pending,
          },
          manual,
        )
      )
        return;
      const revision = generation.current;
      inFlight.current = true;
      const controller = new AbortController();
      abort.current = controller;
      try {
        const response = await fetch(`/api/sessions/${session.id}/questions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            condition: cue.condition,
            case_id: cue.caseId,
          }),
          signal: controller.signal,
        });
        const result = (await response.json()) as {
          question: string;
          session: Session;
          detail?: string;
        };
        if (!response.ok)
          throw new Error(result.detail || "Question unavailable");
        if (
          !mounted.current ||
          revision !== generation.current ||
          controller.signal.aborted
        )
          return;
        onSession(result.session);
        // Recheck controls and speech immediately before delivering audio.
        const current = latestState.current;
        if (
          !current.consent ||
          current.offRecord ||
          current.paused ||
          (!manual && !current.active)
        )
          return;
        const event = result.session.events
          .filter((e) => e.event_type === "question")
          .at(-1);
        setQuestion({ id: event?.event_id ?? cue.id, text: result.question });
        setCaseId(cue.caseId);
        setQueued(false);
        if (
          session.mode === "simulated" &&
          scheduler.current.eligible(
            {
              ...latestState.current,
              pending: false,
              userSpeaking: userSpeaking.current,
              agentSpeaking:
                voiceSpeaking.current ||
                (window.speechSynthesis?.speaking ?? false),
            },
            manual,
          )
        ) {
          agentSpeaking.current = speakDemo(result.question, () => {
            agentSpeaking.current = false;
            scheduler.current.activity();
          });
        }
        scheduler.current.delivered();
      } catch (error) {
        if (!controller.signal.aborted)
          onError(
            error instanceof Error ? error.message : "Question unavailable",
          );
      } finally {
        inFlight.current = false;
        // An aborted browser request may already have committed a question. Recover it
        // as text on the next session update; the server prevents duplicate delivery.
        if (controller.signal.aborted && mounted.current) {
          try {
            onSession(await api<Session>(`/sessions/${session.id}`));
          } catch {
            /* Retry via session refresh. */
          }
        }
      }
    },
    [session.id, session.mode, onSession, onError],
  );
  useEffect(() => {
    const timer = window.setInterval(() => void ask(false), 500);
    return () => clearInterval(timer);
  }, [ask]);
  useEffect(
    () => () => {
      generation.current++;
      abort.current?.abort();
    },
    [],
  );
  const onActivity = useCallback(() => {
    activity.current = Date.now();
    scheduler.current.activity();
  }, []);
  const latest = session.events
    .filter((event) => event.event_type === "expert_answer")
    .at(-1);
  const observation = async () => {
    if (!session.consent || session.off_record) return;
    try {
      const result = await api<Session>(
        `/sessions/${session.id}/cases/${caseId}/observe`,
        {},
      );
      if (mounted.current) onSession(result);
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Observation unavailable",
      );
    }
  };
  const recordAnswer = async (scripted: boolean) => {
    if (!condition) return;
    const result = await api<Session>(`/sessions/${session.id}/answers`, {
      condition,
      text: typed || "Scripted answer",
      scripted,
    });
    onSession(result);
    setTyped("");
    const answer = result.events
      .filter((e) => e.event_type === "expert_answer")
      .at(-1);
    if (scripted && answer) speak(String(answer.payload.text));
  };
  return (
    <div onKeyDown={onActivity} onPointerDown={onActivity}>
      <div className="row spread">
        <div>
          <h2>Capture the checks behind the decision</h2>
          <p className="muted">
            Observe the review. Ask about the reasoning. Keep the evidence.
          </p>
        </div>
        <span className="badge neutral">
          <ShieldCheck size={14} /> Synthetic data
        </span>
      </div>
      <section className="card consent">
        <h3>
          {session.consent
            ? session.off_record
              ? "Consent given · currently off record"
              : "Consent given · capture controls available"
            : "Start with explicit consent"}
        </h3>
        <p>
          Recording stores review moments and your answers locally. Screen
          sharing captures only the surface you choose. In live mode, masked
          frames go to OpenAI and microphone audio goes to ElevenLabs. Masking
          is manual and cannot detect all personal information.
        </p>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={consentValue}
            disabled={busy}
            onChange={(event) => {
              const value = event.target.checked;
              setConsentValue(value);
              void run(async () => {
                try {
                  onSession(
                    await api<Session>(`/sessions/${session.id}/recording`, {
                      consent: value,
                      off_record: false,
                    }),
                  );
                } catch (error) {
                  setConsentValue(session.consent);
                  throw error;
                }
              });
            }}
          />
          I consent to capturing this synthetic review and its answers.
        </label>
      </section>
      <div className="workspace-grid">
        <div>
          <div className="case-tabs" role="group" aria-label="Expert cases">
            {session.cases.map((c) => (
              <Button
                key={c.id}
                variant={caseId === c.id ? "default" : "secondary"}
                onClick={() => {
                  setCaseId(c.id);
                }}
              >
                Case {c.id}
              </Button>
            ))}
          </div>
          <CaseCard value={activeCase} />
          <section className="card">
            <div className="row spread">
              <h3>Review decision</h3>
              <Button
                variant="ghost"
                disabled={!session.consent || session.off_record}
                onClick={() => void observation()}
              >
                Record this screen moment
              </Button>
            </div>
            <div className="decision-fields">
              <label className="field">
                Decision
                <select
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as Decision)}
                >
                  <option>Ready for approval</option>
                  <option>Hold</option>
                  <option>Escalate</option>
                </select>
              </label>
              <label className="field">
                Justification
                <input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain your review decision"
                />
              </label>
            </div>
            <Button
              disabled={
                busy || !reason.trim() || session.off_record || !session.consent
              }
              onClick={() =>
                void run(async () => {
                  const result = await api<{ session: Session }>(
                    `/sessions/${session.id}/cases/${caseId}/decision`,
                    { decision, reason },
                  );
                  onSession(result.session);
                })
              }
            >
              Save review decision
            </Button>
          </section>
          {!publicDemo && (
            <section className="card capture-panel">
              <div className="row spread">
                <div>
                  <h3>Screen observation</h3>
                  <p className="muted">
                    {capture.active
                      ? "● Screen sharing active"
                      : "Screen sharing stopped"}
                    .{" "}
                    {session.mode === "simulated"
                      ? "Frames are stored locally; visual observations are simulated."
                      : "Live vision uses selected, masked frames."}
                  </p>
                </div>
                <span className="badge neutral">
                  {capture.active
                    ? "Recording selected screen"
                    : "Not capturing"}
                </span>
              </div>
              <div className="row wrap">
                <Button
                  variant="secondary"
                  disabled={
                    !session.consent ||
                    session.off_record ||
                    paused ||
                    capture.connecting
                  }
                  onClick={() => void capture.start()}
                >
                  <MonitorUp size={16} />
                  {capture.connecting
                    ? "Choosing screen…"
                    : "Share selected screen"}
                </Button>
                <Button
                  variant="ghost"
                  disabled={!capture.active}
                  onClick={() => {
                    cancelQuestions();
                    setAutomatic(false);
                    capture.stop();
                  }}
                >
                  Stop sharing
                </Button>
              </div>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={maskEnabled}
                  onChange={(e) => setMaskEnabled(e.target.checked)}
                />
                Mask the top of the selected screen before capture
              </label>
              {maskEnabled && (
                <label className="field small">
                  Mask height (% of selected screen)
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={Math.round(maskHeight * 100)}
                    onChange={(e) =>
                      setMaskHeight(
                        Math.max(0, Math.min(1, Number(e.target.value) / 100)),
                      )
                    }
                  />
                </label>
              )}
              <p className="muted">
                One frame at a time, about every 1.5 seconds. No access to
                typing in external apps.
              </p>
            </section>
          )}
          <Timeline events={session.events} onEvidence={onEvidence} />
        </div>
        <aside>
          <section className="card companion">
            <span className="eyebrow">
              <Sparkles size={14} /> Apprentice interviewer
            </span>
            <h3>Let’s uncover the “why”</h3>
            <p className="muted">
              {session.mode === "simulated"
                ? "Simulated dialogue · browser speech"
                : "Live dialogue · ElevenLabs"}
            </p>
            <div className="conversation-bubble">
              {question?.text ??
                (condition
                  ? String(
                      session.events
                        .filter((e) => e.event_type === "question")
                        .at(-1)?.payload.question,
                    )
                  : undefined) ??
                "Review a case and save your decision. Start capture for automatic questions, or choose Ask now."}
            </div>
            {latest && (
              <div className="expert-bubble">
                <span className="eyebrow">
                  {latest.source === "simulated"
                    ? "Scripted expert answer"
                    : "Expert answer"}
                </span>
                <p>{String(latest.payload.text)}</p>
              </div>
            )}
            <div className="row wrap">
              <Button
                variant="secondary"
                disabled={!session.consent || session.off_record || paused}
                onClick={() => {
                  cancelQuestions();
                  setAutomatic((value) => !value);
                }}
              >
                {automatic ? "Stop capture" : "Start capture"}
              </Button>
              <Button
                disabled={
                  busy ||
                  !session.consent ||
                  session.off_record ||
                  paused ||
                  Boolean(condition) ||
                  demoAudio.speaking ||
                  session.known_conditions.length === 3
                }
                onClick={() => void ask(true)}
              >
                Ask now
              </Button>
              <Button
                variant="secondary"
                disabled={
                  !session.consent ||
                  session.off_record ||
                  paused ||
                  Boolean(condition)
                }
                onClick={() => {
                  onActivity();
                  scheduler.current.activity();
                  setQueued(scheduler.current.size > 0);
                }}
              >
                Let me finish
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  cancelQuestions();
                  setPaused((p) => !p);
                }}
              >
                {paused ? <Play size={14} /> : <Pause size={14} />}{" "}
                {paused ? "Resume" : "Pause"}
              </Button>
            </div>
            {queued && !condition && (
              <p className="notice" role="status">
                Question queued. Waiting for activity, speech, and the screen to
                settle. These cues do not prove reading is finished.
              </p>
            )}
            <label className="field">
              Expert answer
              <textarea
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="Explain the condition in your own words…"
              />
            </label>
            <div className="row wrap">
              <Button
                variant="secondary"
                disabled={
                  busy ||
                  !condition ||
                  !typed.trim() ||
                  session.off_record ||
                  paused
                }
                onClick={() => void run(() => recordAnswer(false))}
              >
                Record typed answer
              </Button>
              {session.mode === "simulated" && (
                <Button
                  variant="secondary"
                  disabled={
                    busy ||
                    !condition ||
                    session.off_record ||
                    !session.consent ||
                    paused
                  }
                  onClick={() => void run(() => recordAnswer(true))}
                >
                  Play scripted answer
                </Button>
              )}
            </div>
            <p className="muted">
              {!session.consent
                ? "Next: give consent above."
                : session.off_record
                  ? "Next: resume recording."
                  : condition
                    ? "Next: record an expert answer."
                    : session.known_conditions.length === 3
                      ? "Next: start debrief."
                      : automatic
                        ? "Next: review a case; the interviewer waits for a quiet moment."
                        : "Next: start capture for automatic questions, or Ask now."}
            </p>
            <p className="muted">
              {session.known_conditions.length}/3 conditions explained ·
              Questions are never repeated after an answer.
            </p>
          </section>
          <VoiceCompanion
            sessionId={session.id}
            consent={session.consent}
            captureActive={automatic}
            pendingAnswer={Boolean(condition)}
            replayText={String(
              session.events
                .filter((event) => event.event_type === "question")
                .at(-1)?.payload.question ?? "",
            )}
            sessionMode={session.mode}
            role="interviewer"
            offRecord={session.off_record || !session.consent}
            paused={paused}
            question={question}
            context={JSON.stringify({
              case: activeCase,
              known_conditions: session.known_conditions,
              map: session.work_map,
            })}
            onActivity={onActivity}
            onUserSpeakingChange={(speaking) => {
              userSpeaking.current = speaking;
              if (speaking) onActivity();
            }}
            onSpeakingChange={(speaking) => {
              voiceSpeaking.current = speaking;
            }}
            onSessionChange={onSession}
          />
          <section className="card next-step">
            <h3>Ready to teach it back?</h3>
            <p>
              Resolve the missing details, correct the apprentice, and confirm
              the map.
            </p>
            <Button
              disabled={
                session.known_conditions.length !== 3 ||
                session.off_record ||
                !session.consent
              }
              onClick={onDebrief}
            >
              Start debrief
            </Button>
          </section>
        </aside>
      </div>
    </div>
  );
}
