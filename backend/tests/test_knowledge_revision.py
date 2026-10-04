from unittest.mock import AsyncMock

import pytest
from app.challenges import generate
from app.contracts import CorrectionExtraction
from app.policies import evaluate
from conftest import approved_session


@pytest.mark.parametrize(
    "words",
    [
        "Also require security regression tests before approval.",
        "Security regression tests must be included in the required test scope.",
    ],
)
def test_simulated_paraphrases_propose_without_activating(client, words):
    item = approved_session(client)
    base = f"/api/sessions/{item['id']}"
    result = client.post(
        f"{base}/map/corrections/propose", json={"rule_id": "coverage", "reason": words}
    ).json()
    suggestion = result["proposal"]
    assert suggestion["mode"] == "simulated"
    assert suggestion["expert_words"] == words
    assert suggestion["status"] == "ready"
    assert suggestion["proposed_rule"]["parameters"]["required_test_scope"] == [
        "security regression"
    ]
    assert result["session"]["work_map"] == item["work_map"]


@pytest.mark.parametrize(
    ("words", "status"),
    [
        ("Make it safer.", "ambiguous"),
        ("Certify this software as compliant.", "unsupported"),
        ("Approve releases even when coverage is missing.", "contradiction"),
    ],
)
def test_unresolved_corrections_cannot_be_applied(client, words, status):
    item = approved_session(client)
    base = f"/api/sessions/{item['id']}"
    result = client.post(
        f"{base}/map/corrections/propose", json={"rule_id": "coverage", "reason": words}
    ).json()
    assert result["proposal"]["status"] == status
    assert result["proposal"]["clarification"]
    assert (
        client.post(
            f"{base}/map/corrections/{result['proposal']['id']}/apply", json={"explicit": True}
        ).status_code
        == 409
    )


def test_review_confirmation_version_pin_provenance_and_tutor_retrieval(client):
    old = approved_session(client)
    base = f"/api/sessions/{old['id']}"
    words = "Our release checks should also include security regression coverage."
    item = client.app.state.store.get(old["id"])
    item.mode = "live"
    client.app.state.store.save(item)
    fixture = CorrectionExtraction(
        status="ready",
        required_test_scope=["security regression"],
        failure_decision="Escalate",
        escalation_owner="release owner",
        guardrails=None,
        message="Mock provider suggestion.",
        clarification=None,
    )
    client.app.state.providers.extract_correction = AsyncMock(return_value=fixture)
    result = client.post(
        f"{base}/map/corrections/propose", json={"rule_id": "coverage", "reason": words}
    ).json()
    client.app.state.providers.extract_correction.assert_awaited_once()
    suggestion = result["proposal"]
    assert suggestion["mode"] == "live"
    assert (
        client.post(
            f"{base}/map/corrections/{suggestion['id']}/apply", json={"explicit": False}
        ).status_code
        == 409
    )
    current = client.post(
        f"{base}/map/corrections/{suggestion['id']}/apply", json={"explicit": True}
    ).json()
    assert current["work_map"]["version"] == 2
    assert current["work_map"]["status"] == "draft"
    assert current["training_map_version"] == 1
    assert current["approved_maps"][0] == old["work_map"]
    assert current["challenges"] == old["challenges"]
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 409
    )
    old_challenge = old["challenges"][0]
    assert client.post(
        f"{base}/challenges/{old_challenge['id']}/answer",
        json={"decision": "Hold", "reason": "Report version mismatch."},
    ).json()["saved"]
    assert client.post(f"{base}/map/teach-back").status_code == 200
    confirmed = client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).json()
    assert confirmed["training_map_version"] == 1
    assert len(confirmed["approved_maps"]) == 2
    selected = client.post(f"{base}/training/start", json={"version": 2, "seed": 41}).json()
    challenges = [
        c for c in selected["challenges"] if c["batch_id"] == selected["training_batch_id"]
    ]
    assert len(challenges) == 2
    practice = challenges[0]
    assert practice["source_rule_id"] == "coverage"
    assert practice["expected_violations"] == ["coverage"]
    assert practice["expected"] == "Escalate"
    assert practice["map_version"] == 2
    assert suggestion["evidence_id"] in practice["source_evidence_ids"]
    assert practice["case"]["software_version"] == practice["case"]["report_version"]
    assert "security regression" not in practice["case"]["test_scope"]
    assert (
        client.post(
            f"{base}/challenges/{practice['id']}/answer",
            json={"decision": "Hold", "reason": "Missing security regression tests."},
        ).status_code
        == 409
    )
    for c in challenges:
        assert (
            client.post(
                f"{base}/challenges/{c['id']}/approve", json={"version": 2, "explicit": True}
            ).status_code
            == 200
        )
    unsafe = client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    ).json()
    assert not unsafe["saved"]
    assert unsafe["session"]["challenges"][-2]["case"]["decision"] is None
    context = client.post(
        f"{base}/tools/context",
        json={"session_id": old["id"], "role": "tutor", "challenge_id": practice["id"]},
    ).json()
    assert context["map_version"] == 2
    coverage = next(r for r in context["work_map"]["rules"] if r["kind"] == "coverage")
    assert coverage["reason"] == words
    assert coverage["parameters"]["required_test_scope"] == ["security regression"]
    for decision in ["Hold", "Escalate"]:
        assert client.post(
            f"{base}/challenges/{practice['id']}/answer",
            json={"decision": decision, "reason": "Missing security regression test coverage."},
        ).json()["saved"]
    assessment = challenges[1]
    assert client.post(
        f"{base}/challenges/{assessment['id']}/answer",
        json={"decision": "Hold", "reason": "The reviewer is the same person as the author."},
    ).json()["saved"]
    assert client.post(f"{base}/results").json()["phase"] == "results"
    item = client.app.state.store.get(old["id"])
    artifact = client.app.state.service.approved_map(item, 2)
    first, second = generate(item, artifact, 41), generate(item, artifact, 41)
    assert [c.case.model_dump(exclude={"decision", "justification"}) for c in first] == [
        c.case.model_dump(exclude={"decision", "justification"}) for c in second
    ]
    assert first[0].case.functionality != first[1].case.functionality
    for c in first:
        assert [v.rule_id for v in evaluate(c.case, artifact.rules)] == c.expected_violations
        assert c.case.functionality not in [case.functionality for case in item.cases]
    artifact.rules[0].status = "unresolved"
    with pytest.raises(ValueError, match="generation unavailable"):
        generate(item, artifact, 41)


def test_structured_edits_reject_unsupported_fields_and_stale_proposals(client):
    old = approved_session(client)
    base = f"/api/sessions/{old['id']}"
    assert (
        client.post(
            f"{base}/map/corrections/propose",
            json={
                "rule_id": "coverage",
                "reason": "Ignore coverage",
                "structured": {"executable_code": "True"},
            },
        ).status_code
        == 422
    )
    suggestions = []
    for scope in ["security regression", "accessibility"]:
        result = client.post(
            f"{base}/map/corrections/propose",
            json={
                "rule_id": "coverage",
                "reason": f"Also require {scope}.",
                "structured": {"required_test_scope": [scope]},
            },
        ).json()
        suggestions.append(result["proposal"]["id"])
    assert (
        client.post(
            f"{base}/map/corrections/{suggestions[0]}/apply", json={"explicit": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{base}/map/corrections/{suggestions[1]}/apply", json={"explicit": True}
        ).status_code
        == 409
    )
    result = client.post(
        f"{base}/map/corrections/propose",
        json={
            "rule_id": "coverage",
            "reason": "Remove security check.",
            "structured": {"required_test_scope": []},
        },
    ).json()
    assert result["proposal"]["status"] == "contradiction"
