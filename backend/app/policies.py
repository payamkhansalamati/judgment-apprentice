"""Fictional company policies; never execute generated expressions or code."""

from .contracts import Case, Violation

SUPPORTED_RULES = {"version_match", "coverage", "independent_review"}
SKILL_LABELS = {
    "version_match": "report and software version mismatch",
    "coverage": "test coverage of the changed functionality",
    "independent_review": "reviewer independence from the author",
    "required_information": "missing required review information",
    "test_results": "passing test results",
}


def evaluate(case: Case) -> list[Violation]:
    """Baseline sandbox checks apply even before an expert approves captured knowledge."""
    violations: list[Violation] = []
    required_strings = [case.software_version, case.report_version, case.author, case.reviewer]
    required_lists = [case.functionality, case.test_scope]
    if any(not value.strip() for value in required_strings) or any(
        not values or any(not value.strip() for value in values) for values in required_lists
    ):
        violations.append(
            Violation(
                rule_id="required_information",
                explanation="Required review information is missing.",
            )
        )
    if case.software_version.strip() != case.report_version.strip():
        violations.append(
            Violation(
                rule_id="version_match",
                explanation="The test report covers an older or different version.",
            )
        )
    missing = sorted(
        {value.strip() for value in case.functionality}
        - {value.strip() for value in case.test_scope}
    )
    if missing:
        violations.append(
            Violation(rule_id="coverage", explanation=f"Tests do not cover: {', '.join(missing)}.")
        )
    if case.author.strip().casefold() == case.reviewer.strip().casefold():
        violations.append(
            Violation(
                rule_id="independent_review",
                explanation="The independent reviewer cannot be the change author.",
            )
        )
    if case.test_results != "passed":
        violations.append(
            Violation(rule_id="test_results", explanation="Passing test results are required.")
        )
    return violations


def explanation_skills(case: Case, reason: str) -> tuple[list[str], list[str]]:
    """Small visible English rubric, not a general natural-language or mastery evaluator.

    Recognize the concepts exercised by a controlled case. This deliberately conservative
    check may ask a learner to rephrase a valid explanation; no LLM grades their answer.
    """
    text = reason.casefold()
    checks = {
        "version_match": (
            "version" in text
            or case.report_version.casefold() in text
            and case.software_version.casefold() in text
        )
        and any(
            word in text
            for word in [
                "mismatch",
                "different",
                "older",
                "outdated",
                "wrong",
                "not match",
                "doesn't match",
                "don't match",
                "not the same",
                "instead",
                "while",
                " vs ",
            ]
        ),
        "coverage": any(word in text for word in ["test", "scope", "cover", "untested"])
        and any(
            word in text
            for word in [
                "not cover",
                "doesn't cover",
                "don't cover",
                "uncovered",
                "untested",
                "missing",
                "miss",
                "lack",
            ]
        )
        and any(
            word in text
            for word in ["feature", "function", "change", "cover"]
            + [value.casefold() for value in case.functionality]
        ),
        "independent_review": any(word in text for word in ["review", "independent"])
        and any(word in text for word in ["author", "same", "self", "own"])
        and any(
            word in text
            for word in [
                "same",
                "self",
                "own",
                "is the author",
                "also the author",
                "cannot",
                "must differ",
                "different",
                "not independent",
            ]
        ),
        "required_information": any(word in text for word in ["missing", "incomplete", "unknown"]),
        "test_results": "test" in text
        and any(word in text for word in ["fail", "pass", "unknown"]),
    }
    required = [violation.rule_id for violation in evaluate(case)] or sorted(SUPPORTED_RULES)
    demonstrated = [skill for skill in required if checks.get(skill, False)]
    missing = [skill for skill in required if skill not in demonstrated]
    return demonstrated, missing
