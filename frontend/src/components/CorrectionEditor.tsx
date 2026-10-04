import { useState } from "react";
import { api } from "../api";
import type { CorrectionProposal, Rule, Session } from "../contracts";
import { Button } from "./ui/button";

export function CorrectionEditor({
  session,
  rule,
  onSession,
  onError,
}: {
  session: Session;
  rule: Rule;
  onSession: (value: Session) => void;
  onError: (value: string) => void;
}) {
  const [words, setWords] = useState("");
  const [structured, setStructured] = useState(false);
  const [scope, setScope] = useState(
    rule.parameters.required_test_scope.join(", "),
  );
  const [action, setAction] = useState(rule.parameters.failure_decision);
  const [owner, setOwner] = useState(rule.escalation_owner);
  const [guardrails, setGuardrails] = useState(rule.guardrails.join("\n"));
  const [proposal, setProposal] = useState<CorrectionProposal>();
  const [busy, setBusy] = useState(false);
  const run = async (apply: boolean) => {
    setBusy(true);
    try {
      if (apply && proposal) {
        onSession(
          await api<Session>(
            `/sessions/${session.id}/map/corrections/${proposal.id}/apply`,
            { explicit: true },
          ),
        );
        setProposal({ ...proposal, status: "applied" });
      } else {
        const result = await api<{
          session: Session;
          proposal: CorrectionProposal;
        }>(`/sessions/${session.id}/map/corrections/propose`, {
          rule_id: rule.id,
          reason: words,
          ...(structured
            ? {
                structured: {
                  required_test_scope:
                    rule.kind === "coverage"
                      ? scope
                          .split(",")
                          .map((v) => v.trim())
                          .filter(Boolean)
                      : null,
                  failure_decision: action,
                  escalation_owner: owner,
                  guardrails: guardrails
                    .split("\n")
                    .map((v) => v.trim())
                    .filter(Boolean),
                },
              }
            : {}),
        });
        onSession(result.session);
        setProposal(result.proposal);
      }
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Correction review failed",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="correction-editor">
      <label className="field">
        Correction in the expert’s words
        <textarea
          value={words}
          onChange={(e) => {
            setWords(e.target.value);
            setProposal(undefined);
          }}
        />
      </label>
      {session.mode === "simulated" && (
        <p className="muted">
          Controlled simulated example: “Also require security regression tests
          before approval.” Other wording can use structured editing.
        </p>
      )}
      <label className="checkbox">
        <input
          type="checkbox"
          checked={structured}
          onChange={(e) => {
            setStructured(e.target.checked);
            setProposal(undefined);
          }}
        />
        Edit supported fields explicitly
      </label>
      {structured && (
        <fieldset disabled={busy} onChange={() => setProposal(undefined)}>
          {rule.kind === "coverage" && (
            <label className="field">
              Additional required test scope (comma separated)
              <input value={scope} onChange={(e) => setScope(e.target.value)} />
            </label>
          )}
          <label className="field">
            When this check fails
            <select
              value={action}
              onChange={(e) => setAction(e.target.value as "Hold" | "Escalate")}
            >
              <option>Hold</option>
              <option>Escalate</option>
            </select>
          </label>
          <label className="field">
            Escalation owner
            <input value={owner} onChange={(e) => setOwner(e.target.value)} />
          </label>
          <label className="field">
            Guardrails (one per line)
            <textarea
              value={guardrails}
              onChange={(e) => setGuardrails(e.target.value)}
            />
          </label>
        </fieldset>
      )}
      <Button
        disabled={
          busy || !words.trim() || !session.consent || session.off_record
        }
        onClick={() => void run(false)}
      >
        Review proposed correction
      </Button>
      {proposal && (
        <div className="notice" role="status">
          <strong>
            {proposal.mode} · {proposal.status}
          </strong>
          <p>{proposal.message}</p>
          <blockquote>{proposal.expert_words}</blockquote>
          {proposal.changes.map((change) => (
            <p key={change}>{change}</p>
          ))}
          {proposal.clarification && <p>{proposal.clarification}</p>}
          {proposal.status === "ready" && (
            <Button
              disabled={busy || session.off_record || !session.consent}
              onClick={() => void run(true)}
            >
              Apply reviewed correction
            </Button>
          )}
          {proposal.status === "applied" && (
            <p>
              Draft updated. Review teach-back and confirm this version before
              teaching it.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
