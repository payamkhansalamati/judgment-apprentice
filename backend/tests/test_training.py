import pytest
from conftest import approved_session, create_session

VERSION_REASON = "The report version is older and does not match the software version."
ASSESSMENT_REASON = "Tests do not cover the changed refund calculation; the reviewer is the author."


@pytest.mark.parametrize(
    ("assisted", "outcome"),
    [("independent", "independent"), ("hint", "hinted"), ("retry", "corrected")],
)
def test_scoring_preserves_first_answer_and_distinguishes_assistance(client, assisted, outcome):
    session = approved_session(client)
    challenge = session["challenges"][0]
    base = f"/api/sessions/{session['id']}/challenges/{challenge['id']}"
    if assisted != "independent":
        response = client.post(
            f"{base}/answer", json={"decision": "Ready for approval", "reason": "All tests passed."}
        )
        assert not response.json()["saved"]
        assert response.json()["session"]["challenges"][0]["case"]["decision"] is None
        if assisted == "hint":
            assert client.post(f"{base}/hint").status_code == 200
    response = client.post(f"{base}/answer", json={"decision": "Hold", "reason": VERSION_REASON})
    assert response.json()["saved"]
    assert response.json()["outcome"] == outcome
    attempt = response.json()["session"]["attempts"][0]
    assert attempt["assessed_skills"] == ["version_match"]
    assert attempt["first_decision"] == (
        "Hold" if assisted == "independent" else "Ready for approval"
    )
    if assisted != "independent":
        assert attempt["first_reason"] == "All tests passed."
        assert attempt["corrected_reason"] == VERSION_REASON


def test_reason_rubric_rejects_arbitrary_text_and_assesses_only_intended_violation(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    practice, assessment = session["challenges"]
    response = client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={"decision": "Hold", "reason": "Because I think so."},
    )
    assert not response.json()["saved"]
    assert response.json()["reason_feedback"] == ["report and software version mismatch"]
    response = client.post(
        f"{base}/challenges/{assessment['id']}/answer",
        json={"decision": "Hold", "reason": "The report is an older version."},
    )
    assert not response.json()["saved"]
    assert response.json()["reason_feedback"] == ["test coverage of the changed functionality"]
    response = client.post(
        f"{base}/challenges/{assessment['id']}/answer",
        json={"decision": "Hold", "reason": ASSESSMENT_REASON},
    )
    assert response.json()["saved"]
    assert set(response.json()["session"]["attempts"][1]["assessed_skills"]) == {
        "coverage",
    }


def test_hints_require_first_attempt_and_are_unavailable_for_assessment(client):
    session = approved_session(client)
    practice, assessment = session["challenges"]
    base = f"/api/sessions/{session['id']}"
    assert client.post(f"{base}/challenges/{practice['id']}/hint").status_code == 409
    assert client.post(f"{base}/challenges/{assessment['id']}/hint").status_code == 409
    client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    )
    hint = client.post(f"{base}/challenges/{practice['id']}/hint").json()
    assert {rule["kind"] for rule in hint["rules"]} == {"version_match"}
    for rule in hint["rules"]:
        assert rule["status"] == "expert_confirmed"
        for event_id in rule["evidence_ids"]:
            assert client.get(f"{base}/evidence/{event_id}").status_code == 200


def test_challenge_requires_approval_from_current_map(client):
    session_id = create_session(client)
    assert (
        client.post(
            f"/api/sessions/{session_id}/challenges/unknown/approve",
            json={"version": 1, "explicit": True},
        ).status_code
        == 409
    )
    session = approved_session(client)
    current = client.app.state.store.get(session["id"])
    current.challenges[0].approved = False
    client.app.state.store.save(current)
    base = f"/api/sessions/{session['id']}/challenges/{current.challenges[0].id}"
    assert (
        client.post(
            f"{base}/answer", json={"decision": "Hold", "reason": VERSION_REASON}
        ).status_code
        == 409
    )
    assert client.post(f"{base}/approve", json={"version": 2, "explicit": True}).status_code == 409


def test_results_reports_only_attempted_skills_and_prevents_late_changes(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    assert client.post(f"{base}/results").status_code == 409
    for challenge, reason in zip(
        session["challenges"], [VERSION_REASON, ASSESSMENT_REASON], strict=True
    ):
        assert client.post(
            f"{base}/challenges/{challenge['id']}/answer",
            json={"decision": "Hold", "reason": reason},
        ).json()["saved"]
    results = client.post(f"{base}/results").json()
    assert results["phase"] == "results"
    assert [attempt["outcome"] for attempt in results["attempts"]] == ["independent", "independent"]
    assert "mastery" not in results
    assert (
        client.post(
            f"{base}/challenges/{session['challenges'][0]['id']}/answer",
            json={"decision": "Ready for approval", "reason": "passed"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    ("challenge_index", "reason"),
    [
        (0, "The report and software versions match."),
        (
            1,
            "Tests cover the changed refund calculation "
            "and the reviewer is independent of the author.",
        ),
    ],
)
def test_correct_decision_with_opposite_reason_does_not_score_success(
    client, challenge_index, reason
):
    session = approved_session(client)
    challenge = session["challenges"][challenge_index]
    response = client.post(
        f"/api/sessions/{session['id']}/challenges/{challenge['id']}/answer",
        json={"decision": "Hold", "reason": reason},
    )
    assert not response.json()["saved"]
    assert response.json()["outcome"] == "needs_practice"
    assert response.json()["reason_feedback"]
