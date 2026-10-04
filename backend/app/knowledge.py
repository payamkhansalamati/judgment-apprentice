"""Bounded suggestions; expert review is the authority for every change."""

from .contracts import CorrectionExtraction, CorrectionProposal, Rule, StructuredCorrection


def simulated_extraction(words: str) -> CorrectionExtraction:
    fixtures = {
        "Also require security regression tests before approval.": ["security regression"],
        "Security regression tests must be included in the required test scope.": [
            "security regression"
        ],
    }
    result = dict(
        status="ambiguous",
        required_test_scope=None,
        failure_decision=None,
        escalation_owner=None,
        guardrails=None,
        message="The simulated extractor recognizes only the documented examples.",
        clarification="Which supported field should change? Use structured editing.",
    )
    if words.strip() in fixtures:
        result.update(
            status="ready",
            required_test_scope=fixtures[words.strip()],
            message="Controlled simulated example; review the proposed fields.",
            clarification=None,
        )
    elif words.strip() == "Escalate incomplete coverage to the release owner.":
        result.update(
            status="ready",
            failure_decision="Escalate",
            escalation_owner="release owner",
            message="Controlled simulated escalation example.",
            clarification=None,
        )
    elif words.strip() == "Approve releases even when coverage is missing.":
        result.update(status="contradiction", message="Baseline coverage cannot be relaxed.")
    elif words.strip() == "Certify this software as compliant.":
        result.update(status="unsupported", message="Certification is not a supported rule type.")
    return CorrectionExtraction.model_validate(result)


def proposal(
    rule: Rule,
    version: int,
    words: str,
    mode: str,
    evidence_id: str,
    extraction: CorrectionExtraction,
) -> CorrectionProposal:
    status, message, clarification = extraction.status, extraction.message, extraction.clarification
    updated, changes = None, []
    if status == "ready":
        try:
            patch = StructuredCorrection.model_validate(
                {key: getattr(extraction, key) for key in StructuredCorrection.model_fields}
            )
            data = rule.model_dump()
            if patch.required_test_scope is not None:
                if rule.kind != "coverage":
                    raise ValueError("Additional test scope belongs only to coverage.")
                if not set(rule.parameters.required_test_scope).issubset(patch.required_test_scope):
                    status = "contradiction"
                    raise ValueError("Existing required checks cannot be removed.")
                data["parameters"]["required_test_scope"] = patch.required_test_scope
            if patch.failure_decision is not None:
                data["parameters"]["failure_decision"] = patch.failure_decision
            for field in ("escalation_owner", "guardrails"):
                if getattr(patch, field) is not None:
                    data[field] = getattr(patch, field)
            updated = Rule.model_validate(data)
            if (patch.escalation_owner is not None and not updated.escalation_owner.strip()) or any(
                not item.strip() or len(item) > 300 for item in updated.guardrails
            ):
                raise ValueError("Owner and guardrails must contain meaningful bounded text.")
            for field in ("parameters", "escalation_owner", "guardrails"):
                before, after = rule.model_dump()[field], updated.model_dump()[field]
                if before != after:
                    changes.append(f"{field}: {before} → {after}")
            if not changes:
                status, message = (
                    "ambiguous",
                    "No supported field changed. Clarify the intended change.",
                )
                updated = None
            else:
                updated.reason = words
                updated.status, updated.confirmation = "observed", None
        except ValueError as error:
            updated = None
            if status != "contradiction":
                status = "unsupported"
            message, clarification = (
                str(error),
                "Choose supported fields without relaxing baseline checks.",
            )
    return CorrectionProposal(
        rule_id=rule.id,
        map_version=version,
        expert_words=words,
        mode=mode,
        status=status,
        message=message,
        clarification=clarification,
        before_rule=rule.model_copy(deep=True),
        proposed_rule=updated,
        changes=changes,
        evidence_id=evidence_id,
    )
