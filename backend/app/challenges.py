"""Seeded controlled variations with exactly one independently checked violation."""

from random import Random
from uuid import uuid4

from .contracts import Challenge, Decision, Session, WorkMap
from .policies import evaluate


def generate(session: Session, work_map: WorkMap, seed: int) -> list[Challenge]:
    rules = {
        rule.kind: rule
        for rule in work_map.rules
        if rule.status == "expert_confirmed" and rule.confirmation and rule.evidence_ids
    }
    if set(rules) != {"version_match", "coverage", "independent_review"}:
        raise ValueError(
            "Challenge generation unavailable: approved supported rules with evidence are required."
        )
    rng, batch = Random(seed), str(uuid4())
    revised_scope = rules["coverage"].parameters.required_test_scope
    kinds = ["coverage", "independent_review"] if revised_scope else ["version_match", "coverage"]
    topics = rng.sample(
        ["search ranking", "refund calculation", "invoice routing", "stock reconciliation"], 2
    )
    output = []
    for index, kind in enumerate(kinds):
        rule = rules[kind]
        version = f"{rng.randrange(3, 30)}.{rng.randrange(1, 9)}"
        scope = [topics[index], *revised_scope]
        case = session.cases[0].model_copy(
            deep=True,
            update=dict(
                id="assessment" if index else "practice",
                title=("Unseen assessment · " if index else "New case · ")
                + topics[index].capitalize(),
                description=f"Update {topics[index]}.",
                software_version=version,
                report_version=version,
                functionality=[topics[index]],
                test_scope=scope,
                test_results="passed",
                author="Robin Patel" if index else "Sam Rivera",
                reviewer="Taylor Park",
                decision=None,
                justification="",
            ),
        )
        if kind == "version_match":
            case.report_version = "1.0"
        elif kind == "coverage":
            case.test_scope = [
                value
                for value in scope
                if value != (revised_scope[0] if revised_scope else topics[index])
            ]
            if not case.test_scope:
                case.test_scope = ["unrelated legacy smoke check"]
        else:
            case.reviewer = case.author
        violations = [item.rule_id for item in evaluate(case, work_map.rules)]
        if violations != [kind]:
            raise ValueError(
                "Challenge generation unavailable: controlled template has unintended violations."
            )
        output.append(
            Challenge(
                id=str(uuid4()),
                case=case,
                map_version=work_map.version,
                expected=rule.parameters.failure_decision,
                assessment=bool(index),
                source_rule_id=rule.id,
                source_evidence_ids=list(
                    dict.fromkeys(rule.evidence_ids + rule.screen_evidence_ids)
                ),
                expected_violations=violations,
                accepted_decisions=[Decision.HOLD, Decision.ESCALATE],
                template_id=f"single-{kind}-v1",
                generation_seed=seed,
                batch_id=batch,
            )
        )
    return output
