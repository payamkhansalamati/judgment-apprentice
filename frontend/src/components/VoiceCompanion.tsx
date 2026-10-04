import { lazy, Suspense } from "react";
import type { Session } from "../contracts";

const LiveVoiceCompanion = lazy(() => import("./LiveVoiceCompanion"));

type Speaker = "user" | "agent";
export interface VoiceCompanionProps {
  sessionId: string;
  sessionMode: "simulated" | "live";
  role: "interviewer" | "tutor";
  challengeId?: string;
  offRecord: boolean;
  context?: string;
  paused?: boolean;
  question?: { id: string; text: string } | null;
  onTranscript?: (speaker: Speaker, text: string) => void;
  onSessionChange?: (session: Session) => void;
  onActivity?: () => void;
  onConnectionChange?: (connected: boolean) => void;
  onSpeakingChange?: (speaking: boolean) => void;
}

export function VoiceCompanion(props: VoiceCompanionProps) {
  if (props.sessionMode === "simulated") {
    return (
      <section className="card voice-companion" aria-label="Voice companion">
        <div className="row">
          <h3>
            {props.role === "tutor" ? "Learning companion" : "Expert companion"}
          </h3>
          <span className="badge">Simulated voice</span>
        </div>
        <p className="muted">
          Scripted questions and answers support this demo. Use the written
          conversation below at any time.
        </p>
        <p className="status">
          {props.offRecord
            ? "Off record · recording stopped"
            : props.paused
              ? "Paused"
              : "Ready for the next question"}
        </p>
      </section>
    );
  }
  return (
    <Suspense
      fallback={
        <section
          className="card voice-companion"
          aria-label="Live voice companion"
        >
          <p className="status" role="status">
            Loading voice controls…
          </p>
        </section>
      }
    >
      <LiveVoiceCompanion key={`${props.sessionId}:${props.role}`} {...props} />
    </Suspense>
  );
}
