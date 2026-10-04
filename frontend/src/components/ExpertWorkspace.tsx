import { useCallback, useEffect, useRef, useState } from "react";
import { MonitorUp, Pause, Play, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../api";
import type { Decision, Session } from "../contracts";
import { useScreenCapture } from "../useScreenCapture";
import { VoiceCompanion } from "./VoiceCompanion";
import { CaseCard } from "./CaseCard";
import { Timeline } from "./Timeline";
import { Button } from "./ui/button";

const QUESTION_COOLDOWN = 8_000;
const ACTIVITY_SETTLE = 4_000;
export function ExpertWorkspace({
  session,
  onSession,
  onError,
  onEvidence,
  onDebrief,
}: {
  session: Session;
  onSession: (value: Session) => void;
  onError: (message: string) => void;
  onEvidence: (id: string) => void;
  onDebrief: () => void;
}) {
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
  const lastAsked = useRef(0);
  const inFlight = useRef(false);
  const voiceSpeaking = useRef(false);
  const mounted = useRef(true);
  const activeCase =
    session.cases.find((c) => c.id === caseId) ?? session.cases[0];
  const capture = useScreenCapture({
    sessionId: session.id,
    enabled: session.consent && !session.off_record && !paused,
    masks: maskEnabled ? [{ x: 0, y: 0, width: 1, height: maskHeight }] : [],
    onObservation: () => undefined,
    onError,
  });
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      speechSynthesis.cancel();
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
      speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => {
        activity.current = Date.now();
      };
      speechSynthesis.speak(utterance);
    }
  };
  const ask = useCallback(async () => {
    if (inFlight.current || paused || session.off_record || !session.consent)
      return;
    inFlight.current = true;
    try {
      const result = await api<{ question: string; session: Session }>(
        `/sessions/${session.id}/questions`,
        {},
      );
      if (!mounted.current) return;
      onSession(result.session);
      const event = result.session.events
        .filter((e) => e.event_type === "question")
        .at(-1);
      setQuestion({
        id: event?.event_id ?? String(Date.now()),
        text: result.question,
      });
      const caseForCondition: Record<string, string> = {
        version_match: "B",
        coverage: "C",
        independent_review: "A",
      };
      if (event && typeof event.payload.condition === "string")
        setCaseId(caseForCondition[event.payload.condition] ?? "B");
      setQueued(false);
      lastAsked.current = Date.now();
      if (session.mode === "simulated") {
        const utterance = new SpeechSynthesisUtterance(result.question);
        utterance.onend = () => {
          activity.current = Date.now();
        };
        speechSynthesis.speak(utterance);
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : "Question unavailable");
      setQueued(false);
    } finally {
      inFlight.current = false;
    }
  }, [
    session.id,
    session.mode,
    session.consent,
    session.off_record,
    paused,
    onSession,
    onError,
  ]);
  useEffect(() => {
    if (!queued) return;
    const timer = window.setInterval(() => {
      const now = Date.now();
      if (
        now - activity.current >= ACTIVITY_SETTLE &&
        now - lastAsked.current >= QUESTION_COOLDOWN &&
        (!capture.active || capture.stability) &&
        !speechSynthesis.speaking &&
        !voiceSpeaking.current
      )
        void ask();
    }, 500);
    return () => clearInterval(timer);
  }, [queued, capture.active, capture.stability, ask]);
  useEffect(() => {
    if (session.off_record || paused) {
      speechSynthesis.cancel();
      setQueued(false);
    }
  }, [session.off_record, paused]);
  const onActivity = useCallback(() => {
    activity.current = Date.now();
  }, []);
  const condition = session.asked_questions.find(
    (id) => !session.known_conditions.includes(id),
  );
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
            ? "Recording consent given"
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
                {c.id} ·{" "}
                {c.id === "A"
                  ? "Complete checks"
                  : c.id === "B"
                    ? "Older report"
                    : "Missing coverage"}
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
              disabled={busy || !reason.trim()}
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
                {capture.active ? "Recording selected screen" : "Not capturing"}
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
                onClick={capture.stop}
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
              One frame at a time, about every 1.5 seconds. No access to typing
              in external apps.
            </p>
          </section>
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
                "All tests passed. So why did the expert stop the release?"}
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
                disabled={
                  busy ||
                  !session.consent ||
                  session.off_record ||
                  paused ||
                  Boolean(condition) ||
                  session.known_conditions.length === 3
                }
                onClick={() => void ask()}
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
                  setQueued(true);
                }}
              >
                Let me finish
              </Button>
              <Button variant="ghost" onClick={() => setPaused((p) => !p)}>
                {paused ? <Play size={14} /> : <Pause size={14} />}{" "}
                {paused ? "Resume" : "Pause"}
              </Button>
            </div>
            {queued && (
              <p className="notice" role="status">
                Question queued. Waiting for in-app activity to settle and the
                screen to stabilize.
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
                  disabled={busy || !condition || session.off_record || paused}
                  onClick={() => void run(() => recordAnswer(true))}
                >
                  Play scripted answer
                </Button>
              )}
            </div>
            <p className="muted">
              {session.known_conditions.length}/3 conditions explained ·
              Questions are never repeated after an answer.
            </p>
          </section>
          <VoiceCompanion
            sessionId={session.id}
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
