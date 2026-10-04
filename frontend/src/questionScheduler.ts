export interface Cue {
  id: string;
  condition: string;
  caseId: string;
  priority: number;
  created: number;
}
export interface Eligibility {
  active: boolean;
  consent: boolean;
  paused: boolean;
  offRecord: boolean;
  capturePhase: boolean;
  userSpeaking: boolean;
  agentSpeaking: boolean;
  stable: boolean;
  pending: boolean;
  known: string[];
}
/** Silence and stable frames are scheduling cues, not proof the expert finished reading. */
export class QuestionScheduler {
  private queue: Cue[] = [];
  private seen: string[] = [];
  private activityAt: number;
  private askedAt = -Infinity;
  constructor(private clock: () => number = Date.now) {
    this.activityAt = clock();
  }
  activity() {
    this.activityAt = this.clock();
  }
  cancel() {
    this.queue = [];
    this.seen = [];
    this.activity();
  }
  enqueue(cue: Omit<Cue, "created">) {
    if (this.seen.includes(cue.id)) return;
    this.seen.push(cue.id);
    this.seen = this.seen.slice(-128);
    if (this.queue.some((item) => item.condition === cue.condition)) return;
    this.queue.push({ ...cue, created: this.clock() });
    this.queue.sort((a, b) => a.priority - b.priority || a.created - b.created);
    this.queue = this.queue.slice(0, 12);
  }
  eligible(state: Eligibility, manual = false) {
    return (
      state.consent &&
      !state.paused &&
      !state.offRecord &&
      state.capturePhase &&
      !state.userSpeaking &&
      !state.agentSpeaking &&
      state.stable &&
      !state.pending &&
      (manual ||
        (state.active &&
          this.clock() - this.activityAt >= 4000 &&
          this.clock() - this.askedAt >= 8000))
    );
  }
  next(state: Eligibility, manual = false) {
    this.queue = this.queue.filter(
      (cue) =>
        this.clock() - cue.created < 120000 &&
        !state.known.includes(cue.condition),
    );
    if (!this.eligible(state, manual)) return undefined;
    return this.queue.shift();
  }
  delivered() {
    this.askedAt = this.clock();
  }
  get size() {
    return this.queue.length;
  }
}
