import { useState } from "react";
import type { Session } from "../contracts";
import { api } from "../api";
import { CorrectionEditor } from "./CorrectionEditor";
import { Button } from "./ui/button";
const questions: Record<string, string> = {
  exceptions: "Are there exceptions to these checks?",
  owner: "Who owns escalation when evidence is ambiguous?",
  missing: "What should a newcomer do when required information is missing?",
};
export function Debrief({
  session,
  onSession,
  onError,
  onConfirm,
  onNavigate,
}: {
  session: Session;
  onSession: (value: Session) => void;
  onError: (message: string) => void;
  onConfirm: () => void;
  onNavigate: (page: "expert" | "map") => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const run = async (task: () => Promise<Session>) => {
    setBusy(true);
    try {
      onSession(await task());
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Could not update debrief",
      );
    } finally {
      setBusy(false);
    }
  };
  if (session.phase === "capture")
    return (
      <section className="card">
        <h2>Finish the expert conversation first</h2>
        <p>
          Ask and answer the three capture questions in the Expert workspace.
        </p>
        <Button onClick={() => onNavigate("expert")}>
          Open expert workspace
        </Button>
      </section>
    );
  if (session.work_map.status === "approved")
    return (
      <section className="card">
        <h2>Expert confirmation recorded</h2>
        <p>
          Work Map v{session.work_map.version} is approved. Inspect its evidence
          and approve training challenges in the Work Map.
        </p>
        <Button onClick={() => onNavigate("map")}>
          Open Work Map and challenges
        </Button>
      </section>
    );
  return (
    <>
      <h2>Check what we understood</h2>
      <p className="muted">
        These three follow-up questions resolve details that the capture
        conversation did not answer.
      </p>
      <div className="debrief-grid">
        <div>
          {Object.entries(questions).map(([gap, question]) => (
            <section className="card" key={gap}>
              <div className="row spread">
                <h3>{question}</h3>
                <span className="badge neutral">
                  {session.work_map.gaps.includes(gap)
                    ? "Unresolved"
                    : "Answered"}
                </span>
              </div>
              {session.work_map.answers[gap] && (
                <blockquote>{session.work_map.answers[gap]}</blockquote>
              )}
              <label className="field">
                Your answer
                <textarea
                  disabled={session.phase !== "debrief"}
                  value={answers[gap] ?? ""}
                  onChange={(e) =>
                    setAnswers({ ...answers, [gap]: e.target.value })
                  }
                />
              </label>
              <div className="row wrap">
                <Button
                  variant="secondary"
                  disabled={
                    busy ||
                    !answers[gap]?.trim() ||
                    session.phase !== "debrief" ||
                    session.off_record
                  }
                  onClick={() =>
                    void run(() =>
                      api<Session>(`/sessions/${session.id}/gaps`, {
                        condition: gap,
                        text: answers[gap],
                        scripted: false,
                      }),
                    )
                  }
                >
                  Record answer
                </Button>
                {session.mode === "simulated" && (
                  <Button
                    variant="ghost"
                    disabled={
                      busy || session.phase !== "debrief" || session.off_record
                    }
                    onClick={() =>
                      void run(() =>
                        api<Session>(`/sessions/${session.id}/gaps`, {
                          condition: gap,
                          text: "Scripted answer",
                          scripted: true,
                        }),
                      )
                    }
                  >
                    Use demo answer
                  </Button>
                )}
              </div>
            </section>
          ))}
        </div>
        <aside>
          <section className="card">
            <span className="eyebrow">Expert correction</span>
            <h3>Make the coverage rule precise</h3>
            <blockquote>
              {session.work_map.rules.find((rule) => rule.id === "coverage")
                ?.reason || "No coverage reasoning captured yet."}
            </blockquote>
            <CorrectionEditor
              session={session}
              rule={session.work_map.rules.find(
                (rule) => rule.id === "coverage",
              )!}
              onSession={onSession}
              onError={onError}
            />
          </section>
          <section className="card teach-back">
            <span className="eyebrow">
              Teach-back · Map v{session.work_map.version}
            </span>
            <h3>Here’s the reasoning I’ll teach</h3>
            {session.work_map.rules.map((rule) => (
              <p key={rule.id}>
                <strong>{rule.title}:</strong> {rule.reason}
                <br />
                Required extra tests:{" "}
                {rule.parameters.required_test_scope.join(", ") || "None"}.
                Failure action: {rule.parameters.failure_decision}. Owner:{" "}
                {rule.escalation_owner}
              </p>
            ))}
            <p>
              <strong>When uncertain:</strong>{" "}
              {session.work_map.answers.missing ||
                "Unresolved — ask the expert."}
            </p>
            {!session.map_review_ready ? (
              <Button
                disabled={
                  busy || session.work_map.gaps.length > 0 || session.off_record
                }
                onClick={() =>
                  void run(() =>
                    api<Session>(`/sessions/${session.id}/map/teach-back`, {}),
                  )
                }
              >
                Review teach-back
              </Button>
            ) : (
              <Button
                disabled={
                  busy || !session.map_review_ready || session.off_record
                }
                onClick={onConfirm}
              >
                Confirm this map
              </Button>
            )}
            <p className="muted">
              Confirmation approves this exact version. Required gaps keep the
              debrief incomplete.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
