import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleDot,
  Compass,
  GitBranch,
  GraduationCap,
  LayoutDashboard,
  MessageSquareText,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Event, Session, SessionSummary } from "./contracts";
import { ExpertWorkspace } from "./components/ExpertWorkspace";
import { Debrief } from "./components/Debrief";
import { KnowledgeMap } from "./components/KnowledgeMap";
import { ChallengeApproval, Training } from "./components/Training";
import { Button } from "./components/ui/button";
import { Modal } from "./components/ui/dialog";

type Page = "overview" | "expert" | "debrief" | "map" | "training" | "results";
const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "expert", label: "Expert workspace", icon: Compass },
  { id: "debrief", label: "Debrief", icon: MessageSquareText },
  { id: "map", label: "Work Map", icon: GitBranch },
  { id: "training", label: "Training", icon: GraduationCap },
  { id: "results", label: "Results", icon: BookOpen },
] as const;

export function App() {
  const [page, setPage] = useState<Page>("overview");
  const [session, setSession] = useState<Session | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Event | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [connected, setConnected] = useState(false);
  const onSession = useCallback((value: Session) => {
    setSession(value);
    localStorage.setItem("ja-session", value.id);
  }, []);
  const onError = useCallback((message: string) => setError(message), []);
  const refresh = useCallback(async () => {
    setSessions(await api<SessionSummary[]>("/sessions"));
  }, []);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const summaries = await api<SessionSummary[]>("/sessions");
        if (cancelled) return;
        setSessions(summaries);
        const id = localStorage.getItem("ja-session");
        if (id && summaries.some((s) => s.id === id)) {
          const value = await api<Session>(`/sessions/${id}`);
          if (!cancelled) onSession(value);
        }
      } catch (error) {
        if (!cancelled)
          setError(
            error instanceof Error
              ? error.message
              : "Could not connect to local backend",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [onSession]);
  const currentSessionId = session?.id;
  useEffect(() => {
    if (!currentSessionId) return;
    const socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/sessions/${currentSessionId}/events`,
    );
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    socket.onmessage = (message) => {
      const event = JSON.parse(String(message.data)) as Event;
      setSession((previous) =>
        previous &&
        previous.id === event.session_id &&
        !previous.events.some((e) => e.event_id === event.event_id)
          ? { ...previous, events: [...previous.events, event] }
          : previous,
      );
    };
    return () => {
      socket.close();
      setConnected(false);
    };
  }, [currentSessionId]);
  const perform = async (task: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Request failed. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  };
  const create = (mode: "simulated" | "live") =>
    void perform(async () => {
      onSession(await api<Session>("/sessions", { mode }));
      setPage("expert");
      await refresh();
    });
  const openEvidence = useCallback(
    (id: string) => {
      if (!session) return;
      void api<Event>(`/sessions/${session.id}/evidence/${id}`)
        .then(setEvidence)
        .catch((error: unknown) =>
          onError(
            error instanceof Error ? error.message : "Evidence unavailable",
          ),
        );
    },
    [session, onError],
  );
  const update = async (path: string, body: unknown = {}) => {
    if (session)
      onSession(await api<Session>(`/sessions/${session.id}${path}`, body));
  };
  const confirm = () =>
    void perform(async () => {
      await update("/map/confirm", {
        version: session?.work_map.version,
        explicit: true,
      });
      setPage("map");
    });
  const phase = session?.phase.replaceAll("_", " ") ?? "Not started";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            setPage("overview");
          }}
        >
          <div className="brand-mark">
            <GitBranch size={22} />
          </div>
          <span>
            Judgment
            <br />
            <strong>Apprentice</strong>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => setPage(item.id)}
            >
              <item.icon size={18} />
              {item.label}
              {page === item.id && (
                <ChevronRight size={15} className="nav-arrow" />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <ShieldCheck size={18} />
          <p>
            Capture expert judgment.
            <br />
            Verify it. Teach the next generation.
          </p>
          <span className="badge">Local MVP</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <strong>{navigation.find((n) => n.id === page)?.label}</strong>
          </span>
          <div className="row">
            <span className="connection-status">
              <CircleDot size={13} />
              {session
                ? connected
                  ? "Updates connected"
                  : "Updates disconnected"
                : "Local workspace"}
            </span>
            <div className="avatar">JA</div>
          </div>
        </header>
        <main>
          <div className="page-title">
            <div>
              <span className="eyebrow">
                KNOWLEDGE THAT COMES WITH EVIDENCE
              </span>
              <h1>
                {page === "overview"
                  ? "Good judgment deserves a next generation."
                  : navigation.find((n) => n.id === page)?.label}
              </h1>
            </div>
            {session && (
              <span
                className={`badge ${session.mode === "simulated" ? "neutral" : ""}`}
              >
                {session.mode === "simulated" ? "Simulated demo" : "Live mode"}{" "}
                · {phase}
              </span>
            )}
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <Button
                variant="ghost"
                aria-label="Dismiss error"
                onClick={() => setError(null)}
              >
                <X size={16} />
              </Button>
            </div>
          )}
          {loading ? (
            <div className="card empty" role="status">
              Connecting to your local workspace…
            </div>
          ) : (
            <>
              {page === "overview" ? (
                <>
                  <section className="hero">
                    <div>
                      <span className="eyebrow">
                        THE EXPERTISE HIDING BETWEEN THE CHECKS
                      </span>
                      <h2>
                        All tests passed.
                        <br />
                        So why did the expert
                        <br />
                        <em>stop the release?</em>
                      </h2>
                      <p>
                        Turn an expert’s review into a verified map of
                        decisions, evidence, and guardrails. Then let a newcomer
                        practice the reasoning.
                      </p>
                      <div className="row wrap">
                        <Button
                          onClick={() => create("simulated")}
                          disabled={busy}
                        >
                          Start simulated demo <ArrowRight size={16} />
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => create("live")}
                          disabled={busy}
                        >
                          Start live session
                        </Button>
                      </div>
                      <p className="muted">
                        The apprentice asks about expert decisions and tutors
                        newcomers with reviewed evidence. Demo audio uses your
                        browser voice.
                      </p>
                      <p className="hero-note">
                        Synthetic cases · Fictional company policies · No paid
                        keys needed for the demo
                      </p>
                    </div>
                    <div
                      className="hero-diagram"
                      aria-label="Capture, confirm, teach"
                    >
                      <div className="diagram-step">
                        <Compass />
                        <span>
                          <small>01 · CAPTURE</small>
                          <strong>“Which evidence matters?”</strong>
                          <p>Expert reasoning, linked to the review</p>
                        </span>
                      </div>
                      <div className="diagram-line" />
                      <div className="diagram-step">
                        <Check />
                        <span>
                          <small>02 · VERIFY</small>
                          <strong>“Yes. That’s what I meant.”</strong>
                          <p>Expert review before rules are taught</p>
                        </span>
                      </div>
                      <div className="diagram-line" />
                      <div className="diagram-step">
                        <GraduationCap />
                        <span>
                          <small>03 · TEACH</small>
                          <strong>“Now try an unseen case.”</strong>
                          <p>Independent answers before hints</p>
                        </span>
                      </div>
                    </div>
                  </section>
                  <div className="stat-grid">
                    <div className="card stat">
                      <span>Review cases</span>
                      <strong>3</strong>
                      <p>Version, scope, and reviewer guardrails</p>
                    </div>
                    <div className="card stat">
                      <span>Knowledge boundary</span>
                      <strong>Visible</strong>
                      <p>Observed → confirmed → teachable</p>
                    </div>
                    <div className="card stat">
                      <span>Unseen challenges</span>
                      <strong>2</strong>
                      <p>
                        {session
                          ? `${session.challenges.filter((c) => c.batch_id === session.training_batch_id && c.approved).length}/2 selected challenges approved`
                          : "Expert review required before practice and assessment"}
                      </p>
                    </div>
                  </div>
                  <section className="card">
                    <div className="row spread">
                      <div>
                        <h2>Your sessions</h2>
                        <p className="muted">
                          Continue where you left off. Approved maps are saved
                          locally.
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        onClick={() => void perform(refresh)}
                      >
                        Refresh
                      </Button>
                    </div>
                    {sessions.length === 0 ? (
                      <p className="empty">
                        No sessions yet. Start the simulated demo to capture
                        your first review.
                      </p>
                    ) : (
                      sessions.map((item) => (
                        <button
                          className="session-row"
                          key={item.id}
                          onClick={() =>
                            void perform(async () => {
                              onSession(
                                await api<Session>(`/sessions/${item.id}`),
                              );
                              setPage(
                                item.phase === "capture"
                                  ? "expert"
                                  : item.phase === "training"
                                    ? "training"
                                    : item.phase === "results"
                                      ? "results"
                                      : "debrief",
                              );
                            })
                          }
                        >
                          <div className="session-icon">
                            <GitBranch size={20} />
                          </div>
                          <span>
                            <strong>{item.title}</strong>
                            <small>
                              {item.id.slice(0, 8)} ·{" "}
                              {item.phase.replaceAll("_", " ")}
                            </small>
                          </span>
                          <ChevronRight size={18} />
                        </button>
                      ))
                    )}
                  </section>
                </>
              ) : session ? (
                <>
                  <div className="session-controls">
                    <span className="muted">
                      Session {session.id.slice(0, 8)} · Work Map v
                      {session.work_map.version} ({session.work_map.status}) ·
                      Training v{session.training_map_version ?? "not selected"}
                    </span>
                    <div className="row">
                      <Button
                        variant="secondary"
                        disabled={busy}
                        onClick={() =>
                          void perform(() =>
                            update("/recording", {
                              consent: session.consent,
                              off_record: !session.off_record,
                            }),
                          )
                        }
                      >
                        {session.off_record
                          ? "Resume recording"
                          : "Go off record"}
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label="Delete session"
                        onClick={() => setDeleteOpen(true)}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </div>
                  </div>
                  {session.off_record && (
                    <p className="notice warning" role="status">
                      Off record. New screen and voice capture are stopped.
                      Previously stored evidence remains available.
                    </p>
                  )}
                  {page === "expert" &&
                    (session.phase === "capture" ? (
                      <ExpertWorkspace
                        session={session}
                        onSession={onSession}
                        onError={onError}
                        onEvidence={openEvidence}
                        onDebrief={() =>
                          void perform(async () => {
                            await update("/debrief");
                            setPage("debrief");
                          })
                        }
                      />
                    ) : (
                      <section className="card">
                        <h2>Expert capture is complete</h2>
                        <p>Continue in Debrief or inspect your Work Map.</p>
                        <Button onClick={() => setPage("debrief")}>
                          Open debrief
                        </Button>
                      </section>
                    ))}
                  {page === "debrief" && (
                    <Debrief
                      session={session}
                      onSession={onSession}
                      onError={onError}
                      onConfirm={confirm}
                      onNavigate={setPage}
                    />
                  )}
                  {page === "map" && (
                    <>
                      <KnowledgeMap
                        session={session}
                        onEvidence={openEvidence}
                        onSession={onSession}
                        onError={onError}
                      />
                      {session.approved_maps.length > 0 && (
                        <section className="card">
                          <h3>Select approved training version</h3>
                          <p>
                            Switching is explicit. Earlier challenges and
                            answers remain stored.
                          </p>
                          <div className="row wrap">
                            {session.approved_maps.map((map) => (
                              <Button
                                key={map.version}
                                variant="secondary"
                                disabled={busy}
                                onClick={() =>
                                  void perform(() =>
                                    update("/training/start", {
                                      version: map.version,
                                    }),
                                  )
                                }
                              >
                                Use approved v{map.version}
                              </Button>
                            ))}
                          </div>
                        </section>
                      )}
                      {session.training_map_version !== null && (
                        <>
                          <ChallengeApproval
                            session={session}
                            busy={busy}
                            onApprove={(id) =>
                              void perform(() =>
                                update(`/challenges/${id}/approve`, {
                                  version: session.training_map_version,
                                  explicit: true,
                                }),
                              )
                            }
                          />
                          <Button
                            disabled={session.challenges
                              .filter(
                                (c) => c.batch_id === session.training_batch_id,
                              )
                              .some((c) => !c.approved)}
                            onClick={() => setPage("training")}
                          >
                            Begin training <ArrowRight size={16} />
                          </Button>
                        </>
                      )}
                      {session.map_review_ready && (
                        <Button disabled={busy} onClick={confirm}>
                          Confirm this map
                        </Button>
                      )}
                      {session.work_map.status === "draft" && (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            setPage(
                              session.phase === "capture"
                                ? "expert"
                                : "debrief",
                            )
                          }
                        >
                          {session.phase === "capture"
                            ? "Return to Expert workspace"
                            : "Return to debrief for confirmation"}
                        </Button>
                      )}
                    </>
                  )}
                  {page === "training" && (
                    <>
                      <Training
                        session={session}
                        onSession={onSession}
                        onError={onError}
                        onEvidence={openEvidence}
                        onMap={() =>
                          setPage(
                            session.phase === "capture"
                              ? "expert"
                              : session.work_map.status === "draft"
                                ? "debrief"
                                : "map",
                          )
                        }
                        onResults={() =>
                          void perform(async () => {
                            await update("/results");
                            setPage("results");
                          })
                        }
                      />
                    </>
                  )}
                  {page === "results" && (
                    <section className="card">
                      <span className="eyebrow">
                        PERFORMANCE BASED ON OBSERVED ANSWERS
                      </span>
                      <h2>What the learner demonstrated</h2>
                      {session.attempts.length === 0 ? (
                        <p className="empty">
                          Practice first to see independent answers, hints, and
                          corrections.
                        </p>
                      ) : (
                        session.attempts.map((attempt) => (
                          <article
                            className="result-row"
                            key={attempt.challenge_id}
                          >
                            <span className="badge neutral">
                              {attempt.outcome.replaceAll("_", " ")}
                            </span>
                            <h3>
                              {
                                session.challenges.find(
                                  (c) => c.id === attempt.challenge_id,
                                )?.case.title
                              }
                            </h3>
                            <p>
                              First answer:{" "}
                              <strong>{attempt.first_decision}</strong> ·{" "}
                              {attempt.first_reason}
                            </p>
                            <p className="muted">
                              {attempt.hint_used
                                ? "Expert evidence was requested."
                                : "No hint requested."}
                              {attempt.corrected_decision &&
                                ` Correction: ${attempt.corrected_decision}.`}
                            </p>
                            <p className="muted">
                              Assessed checks:{" "}
                              {attempt.assessed_skills.join(", ") ||
                                "No checks demonstrated"}
                              .
                            </p>
                          </article>
                        ))
                      )}
                      <Button
                        variant="secondary"
                        onClick={() => setPage("training")}
                      >
                        Open training
                      </Button>
                      <p className="notice">
                        These results describe the assessed cases. They do not
                        establish mastery, certification, or standards
                        compliance.
                      </p>
                    </section>
                  )}
                </>
              ) : (
                <section className="card empty">
                  <h2>Start or open a session</h2>
                  <p>
                    Begin with the synthetic review to capture, verify, and
                    teach expert judgment.
                  </p>
                  <Button onClick={() => create("simulated")}>
                    Start simulated demo
                  </Button>
                </section>
              )}
            </>
          )}
          <footer>
            Judgment Apprentice · Synthetic data. Fictional company policies.
            Evidence before confidence.
          </footer>
        </main>
      </div>
      <Modal
        open={Boolean(evidence)}
        onOpenChange={(open) => {
          if (!open) setEvidence(null);
        }}
        title="Stored evidence"
        description="This moment is stored in the current session and can be traced from the Work Map."
      >
        {evidence && (
          <>
            <span className="badge neutral">
              {evidence.source} · {evidence.event_type.replaceAll("_", " ")}
            </span>
            <p className="muted">
              {new Date(evidence.timestamp).toLocaleString()} ·{" "}
              {evidence.event_id.slice(0, 8)}
            </p>
            {typeof evidence.payload.frame === "string" && (
              <img
                className="evidence-frame"
                src={evidence.payload.frame}
                alt="Stored masked screen frame"
              />
            )}
            <dl className="evidence-details">
              {Object.entries(evidence.payload)
                .filter(([key]) => key !== "frame" && key !== "map_json")
                .map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))}
            </dl>
          </>
        )}
      </Modal>
      <Modal
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete this local session?"
        description="This removes stored evidence, maps, challenges, attempts, and workflow checkpoints. It cannot remove provider-side copies already transmitted."
      >
        <Button
          variant="destructive"
          disabled={busy}
          onClick={() =>
            void perform(async () => {
              if (session)
                await api(`/sessions/${session.id}`, undefined, "DELETE");
              setSession(null);
              setEvidence(null);
              localStorage.removeItem("ja-session");
              setDeleteOpen(false);
              setPage("overview");
              await refresh();
            })
          }
        >
          Delete session and evidence
        </Button>
      </Modal>
    </div>
  );
}
