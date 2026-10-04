"""Session transactions, captured knowledge, and deterministic training."""

from datetime import UTC, datetime

from .challenges import generate
from .contracts import (
    Attempt,
    Challenge,
    Decision,
    Event,
    EventPayload,
    EventSource,
    Session,
    WorkMap,
)
from .policies import SKILL_LABELS, SUPPORTED_RULES, evaluate, explanation_skills
from .seed import DEBRIEF, QUESTIONS
from .storage import Store
from .workflow import Workflow


class DomainError(ValueError):
    pass


class Apprenticeship:
    def __init__(self, store: Store, workflow: Workflow):
        self.store, self.workflow = store, workflow

    @staticmethod
    def event(
        session: Session, event_type: str, source: EventSource, payload: EventPayload
    ) -> Event:
        Apprenticeship.recording(session)
        event = Event(session_id=session.id, event_type=event_type, source=source, payload=payload)
        session.events.append(event)
        return event

    @staticmethod
    def recording(session: Session) -> None:
        if session.off_record or not session.consent:
            raise DomainError("Recording is paused or consent has not been given.")

    def observe_case(self, session: Session, case_id: str) -> Event:
        self.recording(session)
        case = next((case for case in session.cases if case.id == case_id), None)
        if case is None:
            raise DomainError("Case does not belong to this session")
        return self.event(
            session,
            "sandbox_case_snapshot",
            "sandbox",
            {
                "case_id": case_id,
                "case_json": case.model_dump_json(),
                "authority": "Current synthetic sandbox state; no inferred expert reasoning.",
            },
        )

    def ask(
        self, session: Session, selected: str | None = None, selected_case: str | None = None
    ) -> str:
        self.recording(session)
        if session.phase != "capture":
            raise DomainError("Capture questions are available only during expert capture")
        if any(key not in session.known_conditions for key in session.asked_questions):
            raise DomainError("Answer the pending question before another is delivered")
        if selected and selected not in {key for key, _ in QUESTIONS}:
            raise DomainError("Unsupported capture condition")
        for condition, question in QUESTIONS:
            if selected and condition != selected:
                continue
            if (
                condition not in session.known_conditions
                and condition not in session.asked_questions
            ):
                case_id = {"version_match": "B", "coverage": "C", "independent_review": "A"}[
                    condition
                ]
                case_id = selected_case or case_id
                evidence = self.observe_case(session, case_id)
                rule = next(rule for rule in session.work_map.rules if rule.id == condition)
                rule.screen_evidence_ids.append(evidence.event_id)
                rule.evidence_timestamps[evidence.event_id] = evidence.timestamp
                case = next(case for case in session.cases if case.id == case_id)
                rule.decision = case.decision
                prefix = (
                    f"You chose {case.decision.value} for case {case.id}. "
                    if case.decision
                    else f"In case {case.id}, "
                )
                if condition == "version_match":
                    question = (
                        f"The release is {case.software_version} and the report is "
                        f"{case.report_version}. How does that affect your decision?"
                    )
                question = prefix + question
                session.asked_questions.append(condition)
                self.event(
                    session,
                    "question",
                    "simulated" if session.mode == "simulated" else "system",
                    {"question": question, "condition": condition, "case_id": case_id},
                )
                return question
        if selected:
            raise DomainError("This queued condition is already known or was asked")
        return "All three capture conditions have been discussed. Continue to debrief."

    def answer(self, session: Session, condition: str, text: str, simulated: bool) -> None:
        self.recording(session)
        if session.phase != "capture":
            raise DomainError("Expert capture is already complete.")
        rule = next((rule for rule in session.work_map.rules if rule.id == condition), None)
        if rule is None:
            raise DomainError("Unknown condition")
        if not text.strip():
            raise DomainError("Provide the expert's actual explanation")
        if condition in session.known_conditions:
            raise DomainError("This condition is already known; use an explicit map correction")
        if condition not in session.asked_questions:
            raise DomainError("Ask the corresponding question first")
        evidence = self.event(
            session,
            "expert_answer",
            "simulated" if simulated else "expert",
            {"condition": condition, "text": text},
        )
        rule.reason = text
        rule.evidence_ids.append(evidence.event_id)
        rule.evidence_timestamps[evidence.event_id] = evidence.timestamp
        if condition not in session.known_conditions:
            session.known_conditions.append(condition)

    def debrief(self, session: Session) -> None:
        self.recording(session)
        if session.phase != "capture":
            raise DomainError("Debrief already started")
        if len(session.known_conditions) != 3:
            raise DomainError("Discuss all three conditions before debrief")
        session.phase = self.workflow.advance(
            session.id, session.work_map.gaps, session.work_map.version
        )
        for gap, question in DEBRIEF.items():
            self.event(
                session,
                "debrief_question",
                "simulated" if session.mode == "simulated" else "system",
                {"gap": gap, "question": question},
            )

    def fill_gap(self, session: Session, gap: str, text: str, simulated: bool) -> None:
        self.recording(session)
        if session.phase != "debrief" or gap not in DEBRIEF:
            raise DomainError("This debrief question is not available")
        if not text.strip():
            raise DomainError("A required debrief answer cannot be blank")
        if session.work_map.answers.get(gap):
            raise DomainError("This question was already answered")
        session.work_map.answers[gap] = text
        session.work_map.gaps = [key for key in DEBRIEF if not session.work_map.answers.get(key)]
        evidence = self.event(
            session,
            "debrief_answer",
            "simulated" if simulated else "expert",
            {"gap": gap, "text": text},
        )
        for rule in session.work_map.rules:
            rule.evidence_ids.append(evidence.event_id)
            rule.evidence_timestamps[evidence.event_id] = evidence.timestamp
            if gap == "owner":
                rule.escalation_owner = text
            if gap == "exceptions":
                rule.exceptions = text

    def correct(self, session: Session, rule_id: str, reason: str) -> None:
        self.recording(session)
        rule = next((rule for rule in session.work_map.rules if rule.id == rule_id), None)
        if rule is None:
            raise DomainError("Unknown rule")
        if not reason.strip():
            raise DomainError("A corrected explanation cannot be blank")
        self.draft_revision(session)
        rule = next(item for item in session.work_map.rules if item.id == rule_id)
        evidence = self.event(
            session, "expert_correction", "expert", {"condition": rule_id, "text": reason}
        )
        rule.reason = reason
        rule.evidence_ids.append(evidence.event_id)
        rule.evidence_timestamps[evidence.event_id] = evidence.timestamp
        rule.status = "observed"
        rule.confirmation = None

    def draft_revision(self, session: Session) -> None:
        if session.work_map.status == "approved":
            if not any(item.version == session.work_map.version for item in session.approved_maps):
                session.approved_maps.append(session.work_map.model_copy(deep=True))
            session.work_map = session.work_map.model_copy(deep=True)
            session.work_map.version += 1
            session.work_map.status = "draft"
            for rule in session.work_map.rules:
                rule.status, rule.confirmation = "observed", None
        session.map_review_ready = False
        if session.phase == "awaiting_confirmation":
            self.workflow.remove(session.id)
            self.workflow.start(session.id)
            self.workflow.advance(session.id, [], session.work_map.version)
            session.phase = "debrief"

    def teach_back(self, session: Session) -> None:
        self.recording(session)
        if (
            session.work_map.status != "draft"
            or session.work_map.gaps
            or session.phase == "capture"
        ):
            raise DomainError("Answer all required debrief gaps first")
        if not all(rule.reason and rule.evidence_ids for rule in session.work_map.rules):
            raise DomainError("Each rule needs actual expert evidence")
        session.map_review_ready = True
        if session.phase == "debrief":
            session.phase = self.workflow.advance(session.id, [], session.work_map.version)

    def confirm(self, session: Session, version: int, explicit: bool) -> None:
        self.recording(session)
        if not explicit or version != session.work_map.version:
            raise DomainError("Explicit confirmation of the current map version is required")
        if (
            not session.map_review_ready
            or session.work_map.status != "draft"
            or session.work_map.gaps
        ):
            raise DomainError("Debrief and teach-back must be complete before confirmation")
        known = {event.event_id for event in session.events}
        if (
            len(session.work_map.rules) != len(SUPPORTED_RULES)
            or {rule.kind for rule in session.work_map.rules} != SUPPORTED_RULES
        ):
            raise DomainError("Only supported validated policy types can be confirmed")
        if any(
            rule.status == "unresolved"
            or not rule.reason
            or not rule.evidence_ids
            or not rule.screen_evidence_ids
            or not set(rule.evidence_ids + rule.screen_evidence_ids).issubset(known)
            for rule in session.work_map.rules
        ):
            raise DomainError("Rule evidence does not resolve")
        timestamp = datetime.now(UTC).isoformat()
        for rule in session.work_map.rules:
            rule.status, rule.confirmation = "expert_confirmed", timestamp
        session.work_map.status = "approved"
        session.approved_maps.append(session.work_map.model_copy(deep=True))
        session.map_review_ready = False
        if session.phase == "awaiting_confirmation":
            session.phase = self.workflow.confirm(session.id)
        self.event(session, "map_confirmed", "expert", {"version": version})
        if session.training_map_version is None:
            self.generate_challenges(session)

    @staticmethod
    def active_rules(session: Session) -> list[str]:
        if session.work_map.status != "approved" or session.work_map.gaps:
            return []
        known = {event.event_id for event in session.events}
        return [
            rule.kind
            for rule in session.work_map.rules
            if rule.kind in SUPPORTED_RULES
            and rule.status == "expert_confirmed"
            and rule.confirmation
            and rule.evidence_ids
            and set(rule.evidence_ids + rule.screen_evidence_ids).issubset(known)
        ]

    @staticmethod
    def approved_map(session: Session, version: int | None = None) -> WorkMap:
        version = version or session.training_map_version
        artifact = next((item for item in session.approved_maps if item.version == version), None)
        if (
            artifact is None
            and session.work_map.status == "approved"
            and session.work_map.version == version
        ):
            artifact = session.work_map
        if artifact is None:
            raise DomainError("An approved Work Map version is required")
        known = {event.event_id for event in session.events}
        if (
            artifact.gaps
            or len(artifact.rules) != 3
            or any(
                rule.status != "expert_confirmed"
                or not rule.confirmation
                or not rule.evidence_ids
                or not set(rule.evidence_ids + rule.screen_evidence_ids).issubset(known)
                for rule in artifact.rules
            )
        ):
            raise DomainError("Approved knowledge has unresolved evidence")
        return artifact

    def require_tutor_knowledge(self, session: Session) -> None:
        if session.phase not in {"training", "results"}:
            raise DomainError("Tutor tools require an approved Work Map")
        self.approved_map(session)

    def require_tutor_assistance(self, session: Session, challenge_id: str | None) -> Attempt:
        self.require_tutor_knowledge(session)
        if not challenge_id:
            raise DomainError("Tutor assistance requires the current learner challenge")
        challenge = self.challenge(session, challenge_id)
        if not challenge.approved:
            raise DomainError("Expert approval of this challenge is required")
        if challenge.assessment:
            raise DomainError("Tutor assistance is unavailable during independent assessment")
        attempt = next(
            (attempt for attempt in session.attempts if attempt.challenge_id == challenge_id), None
        )
        if attempt is None:
            raise DomainError("Record your independent first answer before using the tutor")
        return attempt

    def generate_challenges(
        self, session: Session, version: int | None = None, seed: int = 17
    ) -> None:
        artifact = self.approved_map(session, version or session.work_map.version)
        existing = [
            item
            for item in session.challenges
            if item.map_version == artifact.version and item.generation_seed == seed
        ]
        if not existing:
            try:
                existing = generate(session, artifact, seed)
            except ValueError as error:
                raise DomainError(str(error)) from error
            session.challenges.extend(existing)
        session.training_map_version = artifact.version
        session.training_batch_id = existing[0].batch_id
        session.phase = "training"

    def challenge(self, session: Session, challenge_id: str) -> Challenge:
        challenge = next((item for item in session.challenges if item.id == challenge_id), None)
        if challenge is None or challenge.batch_id != session.training_batch_id:
            raise DomainError("Challenge does not reference the selected training batch")
        self.approved_map(session, challenge.map_version)
        return challenge

    def assess(self, session: Session, challenge_id: str, decision: Decision, reason: str) -> dict:
        self.recording(session)
        if session.phase != "training":
            raise DomainError("Learner answers are available only during training")
        challenge = self.challenge(session, challenge_id)
        if not challenge.approved:
            raise DomainError("Expert approval of this challenge is required")
        attempt = next(
            (item for item in session.attempts if item.challenge_id == challenge_id), None
        )
        if attempt is None:
            attempt = Attempt(
                challenge_id=challenge_id, first_decision=decision, first_reason=reason
            )
            session.attempts.append(attempt)
        else:
            attempt.corrected_decision = decision
            attempt.corrected_reason = reason
        artifact = self.approved_map(session, challenge.map_version)
        violations = evaluate(challenge.case, artifact.rules)
        demonstrated, missing = explanation_skills(challenge.case, reason, artifact.rules)
        attempt.assessed_skills = demonstrated
        attempt.missing_reason_skills = missing
        valid = decision in challenge.accepted_decisions and bool(reason.strip()) and not missing
        if valid:
            attempt.outcome = (
                "hinted"
                if attempt.hint_used
                else "corrected"
                if attempt.corrected_decision is not None
                else "independent"
            )
            challenge.case.decision, challenge.case.justification = decision, reason
        else:
            attempt.outcome = "needs_practice"
        self.event(
            session,
            "learner_attempt",
            "learner",
            {
                "challenge_id": challenge_id,
                "decision": decision.value,
                "reason": reason,
                "saved": valid,
            },
        )
        evidence_ids = {event.event_id for event in session.events}
        for violation in violations:
            violation.evidence_ids = [
                evidence_id
                for rule in artifact.rules
                if rule.kind == violation.rule_id and rule.status == "expert_confirmed"
                for evidence_id in rule.evidence_ids
                if evidence_id in evidence_ids
            ]
        return {
            "saved": valid,
            "violations": [item.model_dump() for item in violations],
            "reason_feedback": [SKILL_LABELS[skill] for skill in missing],
            "outcome": attempt.outcome,
            "message": "Decision saved"
            if valid
            else "Pause: the evidence does not support this answer. Review and try again.",
        }
