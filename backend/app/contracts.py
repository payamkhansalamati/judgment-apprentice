from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Decision(StrEnum):
    READY = "Ready for approval"
    HOLD = "Hold"
    ESCALATE = "Escalate"


class Case(BaseModel):
    id: str
    title: str
    description: str
    software_version: str
    functionality: list[str]
    report_version: str
    test_scope: list[str]
    test_results: Literal["passed", "failed", "unknown"] = "passed"
    author: str
    reviewer: str
    decision: Decision | None = None
    justification: str = ""


class Violation(BaseModel):
    rule_id: str
    explanation: str
    evidence_ids: list[str] = Field(default_factory=list)


EventSource = Literal["sandbox", "expert", "simulated", "visual", "learner", "system"]
EventPayload = dict[str, str | bool | int | list[str]]


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: EventSource
    payload: EventPayload


class Rule(BaseModel):
    id: str
    title: str
    kind: Literal["version_match", "coverage", "independent_review"]
    status: Literal["observed", "expert_confirmed", "unresolved"] = "observed"
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    screen_evidence_ids: list[str] = Field(default_factory=list)
    evidence_timestamps: dict[str, str] = Field(default_factory=dict)
    decision: Decision | None = None
    exceptions: str = ""
    escalation_owner: str = ""
    confirmation: str | None = None


class WorkMap(BaseModel):
    version: int = 1
    status: Literal["draft", "approved"] = "draft"
    rules: list[Rule]
    gaps: list[str] = Field(default_factory=lambda: ["exceptions", "owner", "missing"])
    answers: dict[str, str] = Field(default_factory=dict)


class Challenge(BaseModel):
    id: str
    case: Case
    expected: Decision
    map_version: int
    approved: bool = False
    assessment: bool = False


class Attempt(BaseModel):
    challenge_id: str
    first_decision: Decision
    first_reason: str
    hint_used: bool = False
    corrected_decision: Decision | None = None
    corrected_reason: str | None = None
    assessed_skills: list[str] = Field(default_factory=list)
    missing_reason_skills: list[str] = Field(default_factory=list)
    outcome: Literal["independent", "hinted", "corrected", "needs_practice"] = "needs_practice"


class Session(BaseModel):
    id: str
    title: str = "Release review apprenticeship"
    mode: Literal["simulated", "live"] = "simulated"
    phase: str = "capture"
    off_record: bool = False
    consent: bool = False
    recording_revision: int = 0
    cases: list[Case]
    events: list[Event] = Field(default_factory=list)
    work_map: WorkMap
    challenges: list[Challenge] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    known_conditions: list[str] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
