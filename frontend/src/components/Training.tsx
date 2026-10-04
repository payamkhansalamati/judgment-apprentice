import { useState } from "react";
import { api } from "../api";
import type {
  Challenge,
  Decision,
  Rule,
  Session,
  Violation,
} from "../contracts";
import { CaseCard } from "./CaseCard";
import { RuleEvidence } from "./KnowledgeMap";
import { Button } from "./ui/button";
import { VoiceCompanion } from "./VoiceCompanion";

export function ChallengeApproval({
  session,
  busy,
  onApprove,
}: {
  session: Session;
  busy: boolean;
  onApprove: (id: string) => void;
}) {
  return (
    <section className="card">
      <h3>Expert-approved challenges</h3>
      <p className="muted">
        Review these controlled variations before using them for assessment.
        Expected decisions come from confirmed checks and the fictional sandbox
        policies.
      </p>
      {session.challenges.map((challenge) => (
        <div className="challenge-approval" key={challenge.id}>
          <div>
            <strong>{challenge.case.title}</strong>
            <p className="muted">
              Map v{challenge.map_version} · Expected: {challenge.expected} ·{" "}
              {challenge.case.functionality.join(", ")} · Report{" "}
              {challenge.case.report_version} / release{" "}
              {challenge.case.software_version} · Reviewer:{" "}
              {challenge.case.reviewer}
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={busy || challenge.approved}
            onClick={() => onApprove(challenge.id)}
          >
            {challenge.approved ? "Expert approved" : "Approve challenge"}
          </Button>
        </div>
      ))}
    </section>
  );
}

function LearnerCase({
  session,
  challenge,
  onSession,
  onEvidence,
  onError,
}: {
  session: Session;
  challenge: Challenge;
  onSession: (session: Session) => void;
  onEvidence: (id: string) => void;
  onError: (message: string) => void;
}) {
  const [decision, setDecision] = useState<Decision>("Ready for approval");
  const [reason, setReason] = useState("");
  const [violations, setViolations] = useState<Violation[]>([]);
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState<string[]>([]);
  const [hints, setHints] = useState<Rule[]>([]);
  const [busy, setBusy] = useState(false);
  const attempt = session.attempts.find((a) => a.challenge_id === challenge.id);
  const answer = async () => {
    setBusy(true);
    try {
      const result = await api<{
        session: Session;
        saved: boolean;
        message: string;
        violations: Violation[];
        reason_feedback: string[];
      }>(`/sessions/${session.id}/challenges/${challenge.id}/answer`, {
        decision,
        reason,
      });
      onSession(result.session);
      setMessage(result.message);
      setFeedback(result.reason_feedback);
      setViolations(result.saved ? [] : result.violations);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not save answer");
    } finally {
      setBusy(false);
    }
  };
  const hint = async () => {
    setBusy(true);
    try {
      const result = await api<{ session: Session; rules: Rule[] }>(
        `/sessions/${session.id}/challenges/${challenge.id}/hint`,
        {},
      );
      onSession(result.session);
      setHints(result.rules);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Hint unavailable");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="training-grid">
      <div>
        <CaseCard value={challenge.case} />
        <section className="card">
          <h3>
            {challenge.assessment
              ? "Independent assessment"
              : "Your judgment, first"}
          </h3>
          <p className="muted">
            Predict the decision and explain the evidence. Your first answer is
            saved before assistance.
          </p>
          <label className="field">
            Your decision
            <select
              value={decision}
              onChange={(event) => setDecision(event.target.value as Decision)}
            >
              <option>Ready for approval</option>
              <option>Hold</option>
              <option>Escalate</option>
            </select>
          </label>
          <label className="field">
            Why?
            <textarea
              placeholder="Explain which evidence supports your decision…"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <div className="row wrap">
            <Button
              disabled={busy || !reason.trim()}
              onClick={() => void answer()}
            >
              {attempt ? "Save corrected answer" : "Save first answer"}
            </Button>
            <Button
              variant="secondary"
              disabled={busy || !attempt || challenge.assessment}
              onClick={() => void hint()}
            >
              Ask for expert evidence
            </Button>
          </div>
          {message && (
            <p
              className={violations.length ? "notice warning" : "notice"}
              role="status"
            >
              {message}
            </p>
          )}
          {feedback.length > 0 && (
            <p className="notice warning">
              Explain these checks: {feedback.join(", ")}.
            </p>
          )}
          {violations.length > 0 && (
            <ul className="violations">
              {violations.map((v) => (
                <li key={v.rule_id}>{v.explanation}</li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <aside className="card">
        <span className="eyebrow">Apprentice tutor</span>
        <h3>
          {challenge.assessment
            ? "Try this one independently"
            : "Make the reasoning visible"}
        </h3>
        <p>
          {challenge.assessment
            ? "Hints are reduced for this unseen case. If you cannot resolve the evidence, recommend escalation."
            : "Green results do not tell the whole story. Compare the evidence, then explain the condition you checked."}
        </p>
        {attempt && (
          <div className="notice">
            <strong>First answer recorded</strong>
            <p>
              {attempt.first_decision} · {attempt.first_reason}
            </p>
            <span className="badge neutral">
              {attempt.outcome.replaceAll("_", " ")}
            </span>
          </div>
        )}
        <RuleEvidence rules={hints} onEvidence={onEvidence} />
        <p className="muted">
          I can teach confirmed checks. An unresolved exception belongs with the
          release owner.
        </p>
      </aside>
    </div>
  );
}

export function Training({
  session,
  onSession,
  onEvidence,
  onError,
  onResults,
}: {
  session: Session;
  onSession: (session: Session) => void;
  onEvidence: (id: string) => void;
  onError: (message: string) => void;
  onResults: () => void;
}) {
  const [selected, setSelected] = useState(session.challenges[0]?.id ?? "");
  const challenge =
    session.challenges.find((c) => c.id === selected) ?? session.challenges[0];
  if (!challenge || session.challenges.some((c) => !c.approved))
    return (
      <section className="card">
        <h2>Training starts with expert approval</h2>
        <p>
          Confirm the Work Map and approve both controlled challenge variations
          in the Work Map area.
        </p>
      </section>
    );
  return (
    <>
      <div className="row spread">
        <div>
          <h2>Learn the judgment behind the check</h2>
          <p className="muted">
            Training is pinned to approved Work Map v{challenge.map_version}.
          </p>
        </div>
        <Button
          variant="secondary"
          disabled={session.attempts.length < session.challenges.length}
          onClick={onResults}
        >
          View results
        </Button>
      </div>
      <div className="case-tabs" role="group" aria-label="Training cases">
        {session.challenges.map((c) => (
          <Button
            variant={c.id === challenge.id ? "default" : "secondary"}
            key={c.id}
            onClick={() => setSelected(c.id)}
          >
            {c.assessment ? "Unseen assessment" : "Guided practice"}
          </Button>
        ))}
      </div>
      <LearnerCase
        key={challenge.id}
        session={session}
        challenge={challenge}
        onSession={onSession}
        onEvidence={onEvidence}
        onError={onError}
      />
      <p className="muted">
        {challenge.assessment
          ? "Voice tutoring is paused for this independent assessment."
          : "Record your first independent answer before connecting the tutor."}
      </p>
      <VoiceCompanion
        sessionId={session.id}
        sessionMode={session.mode}
        role="tutor"
        challengeId={challenge.id}
        offRecord={session.off_record || !session.consent}
        paused={
          challenge.assessment ||
          !session.attempts.some(
            (attempt) => attempt.challenge_id === challenge.id,
          )
        }
        context={JSON.stringify({
          map: session.work_map,
          challenge_id: challenge.id,
          case: challenge.case,
          unresolved: "Escalate unknown exceptions to the release owner.",
        })}
        onSessionChange={onSession}
      />
    </>
  );
}
