import { useSyncExternalStore } from "react";

type AudioStatus = { enabled: boolean; message: string; speaking: boolean };
let state: AudioStatus = {
  enabled: false,
  message: "Audio is disabled. Written dialogue is available.",
  speaking: false,
};
const listeners = new Set<() => void>();
let utterance: SpeechSynthesisUtterance | undefined;
let timer: ReturnType<typeof setTimeout> | undefined;
let availableVoices: SpeechSynthesisVoice[] = [];
let watchingVoices = false;
function loadVoices() {
  availableVoices = window.speechSynthesis.getVoices();
  if (!watchingVoices) {
    window.speechSynthesis.addEventListener("voiceschanged", () => {
      availableVoices = window.speechSynthesis.getVoices();
    });
    watchingVoices = true;
  }
}
let finish: (() => void) | undefined;
function update(next: AudioStatus) {
  state = next;
  listeners.forEach((listener) => listener());
}
export function useDemoAudio() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    () => state,
  );
}
export function cancelDemoAudio() {
  const done = finish;
  finish = undefined;
  utterance = undefined;
  clearTimeout(timer);
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  done?.();
  if (state.speaking)
    update({
      ...state,
      speaking: false,
      message: state.enabled ? "Audio enabled. Ready." : "Audio disabled.",
    });
}
export function speakDemo(text: string, onFinish?: () => void): boolean {
  if (!state.enabled || !("speechSynthesis" in window)) return false;
  cancelDemoAudio();
  const speech = new SpeechSynthesisUtterance(text);
  utterance = speech;
  finish = onFinish;
  loadVoices();
  const voices = availableVoices;
  speech.voice =
    voices.find((voice) => voice.lang.startsWith("en") && voice.localService) ??
    voices.find((voice) => voice.lang.startsWith("en")) ??
    null;
  speech.lang = speech.voice?.lang ?? "en-US";
  const complete = (message: string) => {
    if (utterance !== speech) return;
    const done = finish;
    finish = undefined;
    utterance = undefined;
    clearTimeout(timer);
    update({ ...state, speaking: false, message });
    done?.();
  };
  speech.onstart = () => {
    if (utterance === speech)
      update({
        ...state,
        speaking: true,
        message: "Speaking with browser voice…",
      });
  };
  speech.onend = () => complete("Audio enabled. Browser playback completed.");
  speech.onerror = () =>
    complete(
      "Browser voice could not play. Try Test voice again or use written dialogue.",
    );
  timer = setTimeout(() => {
    complete(
      "Browser voice did not finish. Try Test voice again or use written dialogue.",
    );
    window.speechSynthesis.cancel();
  }, 45000);
  update({ ...state, speaking: true, message: "Starting browser voice…" });
  try {
    window.speechSynthesis.resume();
    window.speechSynthesis.speak(speech);
  } catch {
    complete("Browser voice is unavailable. Use written dialogue.");
    return false;
  }
  return true;
}
export function enableDemoAudio() {
  if (!("speechSynthesis" in window)) {
    update({
      ...state,
      message: "This browser has no speech synthesis. Use written dialogue.",
    });
    return;
  }
  update({
    enabled: true,
    speaking: false,
    message: "Audio enabled. Choose Test voice to check playback.",
  });
  // Called directly from a user gesture to satisfy browser autoplay restrictions.
  speakDemo(
    "Demo audio enabled. You can hear the apprentice using your browser voice.",
  );
}
export function disableDemoAudio() {
  cancelDemoAudio();
  update({
    enabled: false,
    speaking: false,
    message: "Audio is disabled. Written dialogue is available.",
  });
}
