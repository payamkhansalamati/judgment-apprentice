from app.services import Apprenticeship
from conftest import approved_session, capture, create_session


def test_unconfirmed_rules_cannot_support_training(client):
    session_id = create_session(client)
    session = client.app.state.store.get(session_id)
    assert Apprenticeship.active_rules(session) == []
    assert (
        client.post(
            f"/api/sessions/{session_id}/map/confirm", json={"version": 1, "explicit": True}
        ).status_code
        == 409
    )
    assert client.get(f"/api/sessions/{session_id}").json()["challenges"] == []


def test_three_distinct_grounded_questions_and_real_evidence(client):
    session_id = create_session(client)
    session = capture(client, session_id)
    assert len(session["known_conditions"]) == 3
    questions = [event for event in session["events"] if event["event_type"] == "question"]
    assert len({event["payload"]["question"] for event in questions}) == 3
    assert "If the versions matched" in questions[1]["payload"]["question"]
    for rule in session["work_map"]["rules"]:
        assert rule["status"] == "observed"
        assert rule["screen_evidence_ids"]
        for evidence_id in rule["screen_evidence_ids"] + rule["evidence_ids"]:
            response = client.get(f"/api/sessions/{session_id}/evidence/{evidence_id}")
            assert response.status_code == 200
            assert response.json()["timestamp"] == rule["evidence_timestamps"][evidence_id]
    assert client.post(f"/api/sessions/{session_id}/questions").status_code == 409


def test_required_gaps_and_explicit_current_version_confirmation(client):
    session_id = create_session(client)
    capture(client, session_id)
    base = f"/api/sessions/{session_id}"
    assert client.post(f"{base}/map/teach-back").status_code == 409
    assert (
        client.post(f"{base}/map/confirm", json={"version": 1, "explicit": True}).status_code == 409
    )
    for gap in ["exceptions", "owner", "missing"]:
        response = client.post(
            f"{base}/gaps", json={"condition": gap, "text": "Expert answer", "scripted": False}
        )
        assert response.status_code == 200
    assert client.post(f"{base}/map/teach-back").json()["phase"] == "awaiting_confirmation"
    for body in [{"version": 1, "explicit": False}, {"version": 2, "explicit": True}]:
        assert client.post(f"{base}/map/confirm", json=body).status_code == 409
    session = client.post(f"{base}/map/confirm", json={"version": 1, "explicit": True}).json()
    assert session["phase"] == "training"
    assert all(rule["status"] == "expert_confirmed" for rule in session["work_map"]["rules"])
    assert len(session["challenges"]) == 2
    assert not any(challenge["approved"] for challenge in session["challenges"])
    assert all(challenge["case"]["decision"] is None for challenge in session["challenges"])


def test_expert_correction_preserves_pinned_training_and_requires_reconfirmation(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    old_challenge = session["challenges"][0]["id"]
    response = client.post(
        f"{base}/map/correct",
        json={"rule_id": "coverage", "reason": "Tests must cover the changed functionality."},
    )
    assert response.status_code == 200
    current = response.json()
    assert current["work_map"]["version"] == 2
    assert current["work_map"]["status"] == "draft"
    assert current["challenges"] == session["challenges"]
    assert current["approved_maps"][0] == session["work_map"]
    assert current["training_map_version"] == 1
    assert current["phase"] == "training"
    assert all(rule["confirmation"] is None for rule in current["work_map"]["rules"])
    assert (
        client.post(
            f"{base}/challenges/{old_challenge}/answer",
            json={"decision": "Hold", "reason": "Version mismatch"},
        ).status_code
        == 200
    )
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 409
    )
    assert client.post(f"{base}/map/teach-back").status_code == 200
    assert (
        client.post(f"{base}/map/confirm", json={"version": 1, "explicit": True}).status_code == 409
    )
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 200
    )


def test_pending_teach_back_must_be_repeated_after_correction(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    correction = {"rule_id": "coverage", "reason": "Cover the changed functionality."}
    assert client.post(f"{base}/map/correct", json=correction).status_code == 200
    assert client.post(f"{base}/map/teach-back").status_code == 200
    response = client.post(f"{base}/map/correct", json=correction)
    assert response.json()["phase"] == "training"
    assert not response.json()["map_review_ready"]
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 409
    )


def test_map_confirmation_rejects_dangling_evidence(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    client.post(f"{base}/map/correct", json={"rule_id": "coverage", "reason": "Changed tests."})
    client.post(f"{base}/map/teach-back")
    current = client.app.state.store.get(session["id"])
    current.work_map.rules[0].evidence_ids.append("fabricated")
    client.app.state.store.save(current)
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 409
    )


def test_checkpoint_is_persisted_and_deleted_with_session(client):
    session = approved_session(client)
    workflow = client.app.state.service.workflow
    config = workflow.config(session["id"])
    assert workflow.graph.get_state(config).values["phase"] == "training"
    assert workflow.graph.get_state(config).values["version"] == 1
    assert client.delete(f"/api/sessions/{session['id']}").status_code == 200
    assert workflow.graph.get_state(config).values == {}
