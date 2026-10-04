from .contracts import Case, Rule, Session, WorkMap

QUESTIONS = [
    ("version_match", "The report and release versions differ. What makes that a release blocker?"),
    ("coverage", "If the versions matched, would you approve? What else must be true?"),
    ("independent_review", "Who can independently review this change? Can the author do it?"),
]
DEBRIEF = {
    "exceptions": "Are there exceptions to these checks?",
    "owner": "Who owns escalation when evidence is ambiguous?",
    "missing": "What should a newcomer do when required information is missing?",
}
DEMO_ANSWERS = {
    "version_match": "I hold the release until the report matches the software version.",
    "coverage": (
        "Only if the tests cover every changed functionality and all required checks are complete."
    ),
    "independent_review": "The independent reviewer must be someone other than the author.",
    "exceptions": "No exceptions permit approval without matching evidence and required checks.",
    "owner": "The release owner handles ambiguous evidence and exceptions.",
    "missing": "Hold when evidence is missing; escalate ambiguity to the release owner.",
}


def seed_session(session_id: str, mode: str) -> Session:
    base = dict(
        description="Update the checkout discount calculation.",
        software_version="2.4.1",
        functionality=["discount calculation"],
        report_version="2.4.1",
        test_scope=["discount calculation"],
        author="Alex Chen",
        reviewer="Morgan Lee",
    )
    cases = [Case(id="A", title="A · Complete evidence", **base)]
    cases.append(
        Case(id="B", title="B · Green tests, older report", **{**base, "report_version": "2.4.0"})
    )
    cases.append(
        Case(
            id="C", title="C · The changed feature is untested", **{**base, "test_scope": ["login"]}
        )
    )
    rules = [
        Rule(id=kind, kind=kind, title=title, guardrails=[title])
        for kind, title in [
            ("version_match", "Match release and report versions"),
            ("coverage", "Check coverage of changed functionality"),
            ("independent_review", "Require an independent reviewer"),
        ]
    ]
    return Session(id=session_id, mode=mode, cases=cases, work_map=WorkMap(rules=rules))
