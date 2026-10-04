import { expect, test } from "@playwright/test";
import { QuestionScheduler, type Eligibility } from "../src/questionScheduler";
const state: Eligibility = {
  active: true,
  consent: true,
  paused: false,
  offRecord: false,
  capturePhase: true,
  userSpeaking: false,
  agentSpeaking: false,
  stable: true,
  pending: false,
  known: [],
};
function fixture() {
  let now = 0;
  const queue = new QuestionScheduler(() => now);
  queue.enqueue({
    id: "decision-1",
    condition: "coverage",
    caseId: "C",
    priority: 1,
  });
  return {
    queue,
    advance: (ms: number) => {
      now += ms;
    },
  };
}
test("quiet period waits for typing and speech, then delivers", () => {
  const { queue, advance } = fixture();
  advance(3000);
  expect(queue.next(state)).toBeUndefined();
  queue.activity();
  advance(4000);
  expect(queue.next({ ...state, userSpeaking: true })).toBeUndefined();
  expect(queue.next({ ...state, agentSpeaking: true })).toBeUndefined();
  expect(queue.next(state)?.condition).toBe("coverage");
});
test("cooldown delays the next interruption", () => {
  const { queue, advance } = fixture();
  advance(4000);
  expect(queue.next(state)).toBeTruthy();
  queue.delivered();
  queue.enqueue({
    id: "decision-2",
    condition: "version_match",
    caseId: "B",
    priority: 1,
  });
  advance(7999);
  expect(queue.next(state)).toBeUndefined();
  advance(1);
  expect(queue.next(state)).toBeTruthy();
});
test("pause cancels delivery and stopped/privacy/pending/unstable states block", () => {
  const { queue, advance } = fixture();
  advance(4000);
  for (const blocked of [
    { paused: true },
    { active: false },
    { offRecord: true },
    { consent: false },
    { pending: true },
    { stable: false },
  ])
    expect(queue.next({ ...state, ...blocked })).toBeUndefined();
  queue.cancel();
  expect(queue.next(state)).toBeUndefined();
});
test("duplicate, known and stale cues never repeat", () => {
  const { queue, advance } = fixture();
  queue.enqueue({
    id: "decision-1",
    condition: "coverage",
    caseId: "C",
    priority: 1,
  });
  expect(queue.size).toBe(1);
  advance(120000);
  expect(queue.next(state)).toBeUndefined();
  queue.enqueue({
    id: "decision-2",
    condition: "coverage",
    caseId: "C",
    priority: 1,
  });
  expect(queue.next({ ...state, known: ["coverage"] })).toBeUndefined();
});
test("manual override skips quiet time but respects speech and privacy", () => {
  const { queue } = fixture();
  expect(queue.eligible(state, true)).toBe(true);
  expect(queue.eligible({ ...state, userSpeaking: true }, true)).toBe(false);
  expect(queue.eligible({ ...state, offRecord: true }, true)).toBe(false);
});
