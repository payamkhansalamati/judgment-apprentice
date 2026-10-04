from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RuleParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_test_scope: list[str] = Field(default_factory=list, max_length=10)
    failure_decision: Literal[Decision.HOLD, Decision.ESCALATE] = Decision.HOLD

    @model_validator(mode="after")
    def clean_scope(self):
        if any(not item.strip() or len(item) > 100 for item in self.required_test_scope):
            raise ValueError("Required checks must be nonempty names of at most 100 characters")
        self.required_test_scope = list(
            dict.fromkeys(item.strip() for item in self.required_test_scope)
        )
        return self


class Rule(BaseModel):
    id: str
    title: str
    kind: Literal["version_match", "coverage", "independent_review"]
    status: Literal["observed", "expert_confirmed", "unresolved"] = "observed"
    reason: str = ""
    parameters: RuleParameters = Field(default_factory=RuleParameters)
    evidence_ids: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    screen_evidence_ids: list[str] = Field(default_factory=list)
    evidence_timestamps: dict[str, str] = Field(default_factory=dict)
    decision: Decision | None = None
    exceptions: str = ""
    escalation_owner: str = ""
    confirmation: str | None = None

    @model_validator(mode="after")
    def supported_parameters(self):
        if self.kind != "coverage" and self.parameters.required_test_scope:
            raise ValueError("Additional test checks belong only to the coverage rule")
        return self


class StructuredCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_test_scope: list[str] | None = Field(default=None, max_length=10)
    failure_decision: Literal[Decision.HOLD, Decision.ESCALATE] | None = None
    escalation_owner: str | None = Field(default=None, max_length=300)
    guardrails: list[str] | None = Field(default=None, max_length=10)


class CorrectionExtraction(BaseModel):
    """Provider output is a suggestion, never executable policy or code."""

    status: Literal["ready", "ambiguous", "unsupported", "contradiction"]
    required_test_scope: list[str] | None
    failure_decision: Literal[Decision.HOLD, Decision.ESCALATE] | None
    escalation_owner: str | None
    guardrails: list[str] | None
    message: str
    clarification: str | None


class CorrectionProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    rule_id: str
    map_version: int
    expert_words: str
    mode: Literal["simulated", "live", "structured"]
    status: Literal["ready", "ambiguous", "unsupported", "contradiction", "applied"]
    message: str
    proposed_rule: Rule | None = None
    before_rule: Rule
    changes: list[str] = Field(default_factory=list)
    clarification: str | None = None
    evidence_id: str


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
    source_rule_id: str = ""
    source_evidence_ids: list[str] = Field(default_factory=list)
    expected_violations: list[str] = Field(default_factory=list)
    accepted_decisions: list[Decision] = Field(default_factory=list)
    template_id: str = ""
    generation_seed: int = 0
    batch_id: str = ""


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
    approved_maps: list[WorkMap] = Field(default_factory=list)
    correction_proposals: list[CorrectionProposal] = Field(default_factory=list)
    training_map_version: int | None = None
    training_batch_id: str | None = None
    map_review_ready: bool = False
    known_conditions: list[str] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
