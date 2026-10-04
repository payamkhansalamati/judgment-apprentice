import { lazy, Suspense, useEffect } from "react";
import {
  cancelDemoAudio,
  disableDemoAudio,
  enableDemoAudio,
  speakDemo,
  useDemoAudio,
} from "../demoAudio";
import { Button } from "./ui/button";
import type { Session } from "../contracts";

const LiveVoiceCompanion = lazy(() => import("./LiveVoiceCompanion"));

type Speaker = "user" | "agent";
export interface VoiceCompanionProps {
  sessionId: string;
  sessionMode: "simulated" | "live";
  role: "interviewer" | "tutor";
  challengeId?: string;
  offRecord: boolean;
  consent?: boolean;
  captureActive?: boolean;
  pendingAnswer?: boolean;
  replayText?: string;
  context?: string;
  paused?: boolean;
  question?: { id: string; text: string } | null;
  onTranscript?: (speaker: Speaker, text: string) => void;
  onSessionChange?: (session: Session) => void;
  onActivity?: () => void;
  onConnectionChange?: (connected: boolean) => void;
  onUserSpeakingChange?: (speaking: boolean) => void;
  onSpeakingChange?: (speaking: boolean) => void;
}

export function VoiceCompanion(props: VoiceCompanionProps) {
  if (props.sessionMode === "simulated") {
    return <DemoVoiceCompanion {...props} />;
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

function DemoVoiceCompanion(props: VoiceCompanionProps) {
  const audio = useDemoAudio();
  useEffect(() => {
    if (props.offRecord || props.paused) cancelDemoAudio();
  }, [props.offRecord, props.paused]);
  useEffect(() => () => cancelDemoAudio(), []);
  const blocked = props.offRecord || props.paused;
  const status =
    props.consent === false
      ? "Consent required before recording or audio."
      : props.offRecord
        ? "Off record · recording and audio stopped"
        : props.paused
          ? "Paused · questions and audio stopped"
          : props.role === "tutor"
            ? "Simulated tutor · written evidence remains available"
            : props.pendingAnswer
              ? "Waiting for the expert’s answer"
              : props.captureActive
                ? "Automatic capture active · waiting for eligible question cues"
                : "Automatic capture stopped · Ask now remains available";
  return (
    <section className="card voice-companion" aria-label="Voice companion">
      <div className="row">
        <h3>
          {props.role === "tutor" ? "Learning companion" : "Expert companion"}
        </h3>
        <span className="badge">Simulated voice</span>
      </div>
      <p className="muted">
        Credential-free browser speech. Enable audio with a click, then test
        playback. Written dialogue works independently.
      </p>
      <p className="status">{status}</p>
      <div className="row wrap">
        <Button
          variant="secondary"
          disabled={blocked || audio.enabled}
          onClick={enableDemoAudio}
        >
          Enable demo audio
        </Button>
        <Button
          variant="secondary"
          disabled={blocked || !audio.enabled}
          onClick={() =>
            speakDemo(
              "This is Judgment Apprentice. Your browser voice is ready for the synthetic demo.",
            )
          }
        >
          Test voice
        </Button>
        {audio.enabled && (
          <Button variant="ghost" onClick={disableDemoAudio}>
            Mute audio
          </Button>
        )}
        <Button
          variant="secondary"
          disabled={blocked || !audio.enabled || !props.replayText}
          onClick={() => speakDemo(props.replayText!)}
        >
          Replay question
        </Button>
        <Button
          variant="ghost"
          disabled={!audio.speaking}
          onClick={cancelDemoAudio}
        >
          Stop voice
        </Button>
      </div>
      <p role="status">{audio.message}</p>
    </section>
  );
}
