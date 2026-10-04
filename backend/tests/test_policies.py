import pytest
from app.contracts import Decision
from app.policies import evaluate
from app.seed import seed_session
from conftest import create_session


@pytest.mark.parametrize(
    ("update", "rule_id"),
    [
        ({"report_version": "2.4.0"}, "version_match"),
        ({"test_scope": ["login"]}, "coverage"),
        ({"reviewer": " alex CHEN "}, "independent_review"),
        ({"software_version": " ", "report_version": " "}, "required_information"),
        ({"functionality": [" "], "test_scope": [" "]}, "required_information"),
        ({"reviewer": ""}, "required_information"),
        ({"test_results": "unknown"}, "test_results"),
    ],
)
def test_missing_or_invalid_evidence_blocks_approval(update, rule_id):
    case = seed_session("policy", "simulated").cases[0].model_copy(update=update)
    violations = evaluate(case)
    assert rule_id in {violation.rule_id for violation in violations}
    assert all(not violation.evidence_ids for violation in violations)


def test_complete_evidence_is_ready():
    assert evaluate(seed_session("policy", "simulated").cases[0]) == []


def test_save_gate_reads_current_server_state_and_keeps_safe_choices_available(client):
    session_id = create_session(client)
    base = f"/api/sessions/{session_id}"
    case = client.app.state.store.get(session_id)
    case.cases[0].reviewer = case.cases[0].author
    client.app.state.store.save(case)
    response = client.post(
        f"{base}/cases/A/decision", json={"decision": Decision.READY, "reason": "All tests passed."}
    )
    assert response.status_code == 409
    assert response.json()["violations"][0]["rule_id"] == "independent_review"
    assert client.get(f"{base}/cases/A").json()["decision"] is None
    for decision in [Decision.HOLD, Decision.ESCALATE]:
        assert (
            client.post(
                f"{base}/cases/A/decision",
                json={"decision": decision, "reason": "The reviewer is also the author."},
            ).status_code
            == 200
        )
