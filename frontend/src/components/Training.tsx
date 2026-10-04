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
      {session.challenges
        .filter((c) => c.batch_id === session.training_batch_id)
        .map((challenge) => (
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
              <p className="muted">
                Source: {challenge.source_rule_id} · {challenge.template_id} ·
                Seed {challenge.generation_seed} · Violations:{" "}
                {challenge.expected_violations.join(", ")}
              </p>
              <p className="muted">
                Test scope: {challenge.case.test_scope.join(", ")} · Accepted
                safe decisions: {challenge.accepted_decisions.join(" / ")} ·
                Evidence: {challenge.source_evidence_ids.length} stored moments
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
              disabled={
                busy ||
                !reason.trim() ||
                !session.consent ||
                session.off_record ||
                session.phase !== "training"
              }
              onClick={() => void answer()}
            >
              {attempt ? "Save corrected answer" : "Save first answer"}
            </Button>
            <Button
              variant="secondary"
              disabled={
                busy ||
                !attempt ||
                challenge.assessment ||
                !session.consent ||
                session.off_record ||
                session.phase !== "training"
              }
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
  onMap,
}: {
  session: Session;
  onSession: (session: Session) => void;
  onEvidence: (id: string) => void;
  onError: (message: string) => void;
  onResults: () => void;
  onMap: () => void;
}) {
  const active = session.challenges.filter(
    (c) => c.batch_id === session.training_batch_id,
  );
  const [selected, setSelected] = useState(active[0]?.id ?? "");
  const challenge = active.find((c) => c.id === selected) ?? active[0];
  if (!challenge || active.some((c) => !c.approved))
    return (
      <section className="card">
        <h2>Training starts with expert approval</h2>
        <p>
          Confirm the Work Map and approve both controlled challenge variations
          in the Work Map area.
        </p>
        <p className="muted">
          {session.phase === "capture"
            ? `${3 - session.known_conditions.length} expert conditions remain to explain, then debrief and confirmation.`
            : session.work_map.status === "draft"
              ? `${session.work_map.gaps.length} debrief gaps remain; review and confirm the draft.`
              : `${active.filter((c) => !c.approved).length} selected challenges still need expert approval.`}
        </p>
        <Button onClick={onMap}>
          {session.phase === "capture"
            ? "Return to Expert workspace"
            : session.work_map.status === "draft"
              ? "Open debrief and confirm map"
              : "Open Work Map and approve challenges"}
        </Button>
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
          disabled={active.some(
            (c) => !session.attempts.some((a) => a.challenge_id === c.id),
          )}
          onClick={onResults}
        >
          View results
        </Button>
      </div>
      <div className="case-tabs" role="group" aria-label="Training cases">
        {active.map((c) => (
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
        consent={session.consent}
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
          map: session.approved_maps.find(
            (map) => map.version === challenge.map_version,
          ),
          challenge_id: challenge.id,
          case: challenge.case,
          unresolved: "Escalate unknown exceptions to the release owner.",
        })}
        onSessionChange={onSession}
      />
    </>
  );
}
