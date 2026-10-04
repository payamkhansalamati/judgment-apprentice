export type Decision = "Ready for approval" | "Hold" | "Escalate";
export type Source =
  "sandbox" | "expert" | "simulated" | "visual" | "learner" | "system";
export interface Event {
  event_id: string;
  session_id: string;
  event_type: string;
  timestamp: string;
  source: Source;
  payload: Record<string, string | boolean | number | string[]>;
}
export interface Case {
  id: string;
  title: string;
  description: string;
  software_version: string;
  functionality: string[];
  report_version: string;
  test_scope: string[];
  test_results: string;
  author: string;
  reviewer: string;
  decision: Decision | null;
  justification: string;
}
export interface Rule {
  id: string;
  title: string;
  kind: string;
  status: "observed" | "expert_confirmed" | "unresolved";
  reason: string;
  evidence_ids: string[];
  guardrails: string[];
  screen_evidence_ids: string[];
  evidence_timestamps: Record<string, string>;
  decision: Decision | null;
  exceptions: string;
  escalation_owner: string;
  confirmation: string | null;
}
export interface WorkMap {
  version: number;
  status: "draft" | "approved";
  rules: Rule[];
  gaps: string[];
  answers: Record<string, string>;
}
export interface Challenge {
  id: string;
  case: Case;
  expected: Decision;
  map_version: number;
  approved: boolean;
  assessment: boolean;
}
export interface Attempt {
  challenge_id: string;
  first_decision: Decision;
  first_reason: string;
  hint_used: boolean;
  corrected_decision: Decision | null;
  corrected_reason: string | null;
  assessed_skills: string[];
  missing_reason_skills: string[];
  outcome: string;
}
export interface Session {
  id: string;
  title: string;
  mode: "simulated" | "live";
  phase: string;
  off_record: boolean;
  consent: boolean;
  cases: Case[];
  events: Event[];
  work_map: WorkMap;
  challenges: Challenge[];
  attempts: Attempt[];
  known_conditions: string[];
  asked_questions: string[];
}
export interface SessionSummary {
  id: string;
  title: string;
  phase: string;
}
export interface Violation {
  rule_id: string;
  explanation: string;
  evidence_ids: string[];
}
