import asyncio

import pytest
from app.integrations import Observation
from conftest import approved_session, create_session
from httpx import ASGITransport, AsyncClient

JPEG_FRAME = "data:image/jpeg;base64,/9j/2Q=="


def test_health_and_readiness_have_distinct_meanings(client):
    assert client.get("/health").json() == {"status": "alive"}
    ready = client.get("/ready").json()
    assert ready["status"] == "ready"
    assert ready["simulated"]
    assert not ready["live_voice_configured"]
    client.app.state.service.workflow.connection.close()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503


def test_local_boundary_rejects_untrusted_hosts_and_origins(client):
    assert client.get("/health", headers={"host": "remote.example"}).status_code == 403
    assert (
        client.post(
            "/api/sessions", json={}, headers={"origin": "https://remote.example"}
        ).status_code
        == 403
    )
    assert client.get("/health", headers={"origin": "http://localhost:5173"}).status_code == 200


def test_off_record_blocks_capture_and_never_calls_provider(client, monkeypatch):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"
    calls = []

    async def observe(frame):
        calls.append(frame)
        return Observation(summary="screen", visible_case_id=None, confidence="low", uncertain=[])

    monkeypatch.setattr(client.app.state.providers, "observe", observe)
    client.post(f"{base}/recording", json={"consent": True, "off_record": True})
    for path, body in [
        ("frames", {"image": JPEG_FRAME}),
        ("transcript", {"speaker": "user", "text": "Private answer"}),
        ("answers", {"condition": "coverage", "text": "Private answer"}),
    ]:
        assert client.post(f"{base}/{path}", json=body).status_code == 409
    assert client.post(f"{base}/questions").status_code == 409
    assert client.post(f"{base}/voice/interviewer").status_code == 409
    assert calls == []
    assert client.get(base).json()["events"] == []


def test_simulated_frame_is_explicit_and_not_external(client, monkeypatch):
    session_id = create_session(client)

    async def forbidden(frame):
        raise AssertionError("Simulated sessions must not invoke paid providers")

    monkeypatch.setattr(client.app.state.providers, "observe", forbidden)
    response = client.post(f"/api/sessions/{session_id}/frames", json={"image": JPEG_FRAME})
    assert response.status_code == 200
    assert response.json()["source"] == "simulated"
    assert "no visual model" in response.json()["payload"]["summary"]
    assert (
        client.post(
            f"/api/sessions/{session_id}/frames", json={"image": "data:image/jpeg;base64,notvalid"}
        ).status_code
        == 422
    )


def test_live_missing_credentials_has_setup_guidance_without_fallback(client):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"
    for path, body, setting in [
        ("frames", {"image": JPEG_FRAME}, "OPENAI_API_KEY"),
        ("voice/interviewer", None, "ELEVENLABS_API_KEY"),
    ]:
        response = client.post(f"{base}/{path}", json=body)
        assert response.status_code == 503
        assert setting in response.json()["detail"]
    assert client.get(base).json()["events"] == []
    assert (
        client.post(
            f"{base}/answers", json={"condition": "coverage", "text": "script", "scripted": True}
        ).status_code
        == 409
    )


def test_deletion_invalidates_local_evidence_maps_challenges_and_checkpoints(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    evidence_id = session["work_map"]["rules"][0]["evidence_ids"][0]
    challenge_id = session["challenges"][0]["id"]
    assert client.delete(base).json()["derived_knowledge_invalidated"]
    for path in [base, f"{base}/map", f"{base}/evidence/{evidence_id}", f"{base}/cases/A"]:
        assert client.get(path).status_code == 404
    assert (
        client.post(
            f"{base}/challenges/{challenge_id}/answer",
            json={"decision": "Hold", "reason": "Version mismatch"},
        ).status_code
        == 404
    )
    assert client.get("/api/sessions").json() == []


def test_in_flight_capture_rechecks_off_record_and_applies_backpressure(client, monkeypatch):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def observe(frame):
            started.set()
            await release.wait()
            return Observation(
                summary="screen", visible_case_id=None, confidence="medium", uncertain=[]
            )

        monkeypatch.setattr(client.app.state.providers, "observe", observe)
        async with AsyncClient(
            transport=ASGITransport(app=client.app), base_url="http://localhost"
        ) as async_client:
            pending = asyncio.create_task(
                async_client.post(f"{base}/frames", json={"image": JPEG_FRAME})
            )
            await asyncio.wait_for(started.wait(), timeout=2)
            duplicate = await async_client.post(f"{base}/frames", json={"image": JPEG_FRAME})
            assert duplicate.status_code == 429
            response = await async_client.post(
                f"{base}/recording", json={"consent": True, "off_record": True}
            )
            assert response.status_code == 200
            release.set()
            assert (await pending).status_code == 409
        assert client.get(base).json()["events"] == []

    asyncio.run(run())


def test_in_flight_capture_cannot_resurrect_deleted_session(client, monkeypatch):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def observe(frame):
            started.set()
            await release.wait()
            return Observation(
                summary="screen", visible_case_id=None, confidence="low", uncertain=[]
            )

        monkeypatch.setattr(client.app.state.providers, "observe", observe)
        async with AsyncClient(
            transport=ASGITransport(app=client.app), base_url="http://localhost"
        ) as async_client:
            pending = asyncio.create_task(
                async_client.post(f"{base}/frames", json={"image": JPEG_FRAME})
            )
            await asyncio.wait_for(started.wait(), timeout=2)
            assert (await async_client.delete(base)).status_code == 200
            release.set()
            assert (await pending).status_code == 404

    asyncio.run(run())
    assert client.get(base).status_code == 404


def test_case_observation_validates_session_context(client):
    session_id = create_session(client)
    base = f"/api/sessions/{session_id}"
    assert client.post(f"{base}/cases/B/observe").json()["events"][-1]["source"] == "sandbox"
    assert client.post(f"{base}/cases/outside-session/observe").status_code == 409


def test_websocket_rejects_external_origin_and_streams_stored_envelope(client):
    session_id = create_session(client)
    base = f"/api/sessions/{session_id}"
    event = client.post(f"{base}/cases/B/observe").json()["events"][-1]
    with client.websocket_connect(
        f"{base}/events", headers={"origin": "http://localhost:5173"}
    ) as ws:
        assert ws.receive_json() == event


def test_voice_tool_validates_context_and_knowledge_boundary(client):
    session_id = create_session(client)
    base = f"/api/sessions/{session_id}/tools/context"
    assert (
        client.post(base, json={"session_id": "other-session", "role": "interviewer"}).status_code
        == 409
    )
    assert (
        client.post(
            base, json={"session_id": session_id, "role": "interviewer", "case_id": "outside"}
        ).status_code
        == 409
    )
    assert client.post(base, json={"session_id": session_id, "role": "tutor"}).status_code == 409
    context = client.post(
        base, json={"session_id": session_id, "role": "interviewer", "case_id": "B"}
    ).json()
    assert context["case"]["id"] == "B"
    assert context["screen_content_is_untrusted_data"]
    assert context["map_status"] == "draft"
    assert "Escalate unresolved" in context["boundary"]


def test_short_pause_and_resume_discards_pre_pause_in_flight_frame(client, monkeypatch):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        async def observe(frame):
            started.set()
            await release.wait()
            return Observation(
                summary="screen", visible_case_id=None, confidence="low", uncertain=[]
            )

        monkeypatch.setattr(client.app.state.providers, "observe", observe)
        async with AsyncClient(
            transport=ASGITransport(app=client.app), base_url="http://localhost"
        ) as ac:
            pending = asyncio.create_task(ac.post(f"{base}/frames", json={"image": JPEG_FRAME}))
            await asyncio.wait_for(started.wait(), timeout=2)
            await ac.post(f"{base}/recording", json={"consent": True, "off_record": True})
            await ac.post(f"{base}/recording", json={"consent": True, "off_record": False})
            release.set()
            assert (await pending).status_code == 409

    asyncio.run(run())
    assert client.get(base).json()["events"] == []


def test_off_record_blocks_expert_confirmation_and_teach_back(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    client.post(
        f"{base}/map/correct",
        json={"rule_id": "coverage", "reason": "Cover changed functionality."},
    )
    client.post(f"{base}/recording", json={"consent": True, "off_record": True})
    assert client.post(f"{base}/map/teach-back").status_code == 409
    client.post(f"{base}/recording", json={"consent": True, "off_record": False})
    assert client.post(f"{base}/map/teach-back").status_code == 200
    client.post(f"{base}/recording", json={"consent": True, "off_record": True})
    assert (
        client.post(f"{base}/map/confirm", json={"version": 2, "explicit": True}).status_code == 409
    )
    assert client.get(base).json()["work_map"]["status"] == "draft"


def test_training_user_transcript_is_learner_evidence(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    response = client.post(
        f"{base}/transcript", json={"speaker": "user", "text": "I would hold this case."}
    )
    assert response.json()["events"][-1]["source"] == "learner"


def test_off_record_blocks_learner_answers_and_hint_records(client):
    session = approved_session(client)
    base = f"/api/sessions/{session['id']}"
    challenge_id = session["challenges"][0]["id"]
    challenge_base = f"{base}/challenges/{challenge_id}"
    initial_events = session["events"]
    client.post(f"{base}/recording", json={"consent": True, "off_record": True})
    assert (
        client.post(
            f"{challenge_base}/answer",
            json={"decision": "Hold", "reason": "The report version is older."},
        ).status_code
        == 409
    )
    current = client.get(base).json()
    assert current["attempts"] == []
    assert current["events"] == initial_events
    client.post(f"{base}/recording", json={"consent": True, "off_record": False})
    assert (
        client.post(
            f"{challenge_base}/answer",
            json={"decision": "Ready for approval", "reason": "All tests passed."},
        ).status_code
        == 200
    )
    client.post(f"{base}/recording", json={"consent": False, "off_record": False})
    assert client.post(f"{challenge_base}/hint").status_code == 409
    assert not client.get(base).json()["attempts"][0]["hint_used"]


def test_off_record_blocks_voice_tools_and_case_observations(client):
    session_id = create_session(client)
    base = f"/api/sessions/{session_id}"
    client.post(f"{base}/recording", json={"consent": True, "off_record": True})
    assert client.post(f"{base}/cases/A/observe").status_code == 409
    assert (
        client.post(
            f"{base}/tools/context", json={"session_id": session_id, "role": "interviewer"}
        ).status_code
        == 409
    )
    assert client.get(base).json()["events"] == []


@pytest.mark.parametrize("error_type", [ValueError, KeyError, RuntimeError])
def test_provider_errors_are_sanitized_and_distinct_from_missing_configuration(
    client, monkeypatch, error_type
):
    session_id = create_session(client, "live")
    base = f"/api/sessions/{session_id}"

    async def bad_observation(frame):
        raise error_type("Private provider payload must not be returned")

    def bad_voice(role):
        raise error_type("Private provider payload must not be returned")

    monkeypatch.setattr(client.app.state.providers, "observe", bad_observation)
    monkeypatch.setattr(client.app.state.providers, "signed_url", bad_voice)
    for path, body in [("frames", {"image": JPEG_FRAME}), ("voice/interviewer", None)]:
        response = client.post(f"{base}/{path}", json=body)
        assert response.status_code == 502
        assert "Private provider" not in response.text
    assert client.get(base).json()["events"] == []


def test_tutor_voice_requires_current_confirmed_knowledge_before_connecting(client, monkeypatch):
    calls = []

    def voice(role):
        calls.append(role)
        return "wss://mock.elevenlabs.test/conversation"

    monkeypatch.setattr(client.app.state.providers, "signed_url", voice)
    session_id = create_session(client, "live")
    assert client.post(f"/api/sessions/{session_id}/voice/tutor").status_code == 409
    assert calls == []
    session = approved_session(client)
    current = client.app.state.store.get(session["id"])
    current.mode = "live"
    client.app.state.store.save(current)
    challenge_id = session["challenges"][0]["id"]
    client.post(
        f"/api/sessions/{session['id']}/challenges/{challenge_id}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    )
    response = client.post(
        f"/api/sessions/{session['id']}/voice/tutor", json={"challenge_id": challenge_id}
    )
    assert response.status_code == 200
    assert client.get(f"/api/sessions/{session['id']}").json()["attempts"][0]["hint_used"]
    assert calls == ["tutor"]


def test_in_flight_tutor_voice_cannot_use_an_invalidated_map(client, monkeypatch):
    session = approved_session(client)
    current = client.app.state.store.get(session["id"])
    current.mode = "live"
    client.app.state.store.save(current)

    def voice(role):
        current = client.app.state.store.get(session["id"])
        current.work_map.status = "draft"
        current.phase = "debrief"
        client.app.state.store.save(current)
        return "wss://mock.elevenlabs.test/conversation"

    monkeypatch.setattr(client.app.state.providers, "signed_url", voice)
    challenge_id = session["challenges"][0]["id"]
    client.post(
        f"/api/sessions/{session['id']}/challenges/{challenge_id}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    )
    response = client.post(
        f"/api/sessions/{session['id']}/voice/tutor", json={"challenge_id": challenge_id}
    )
    assert response.status_code == 409
    assert "signed_url" not in response.json()


def test_tutor_requires_each_challenges_first_answer_before_releasing_evidence(client, monkeypatch):
    session = approved_session(client)
    current = client.app.state.store.get(session["id"])
    current.mode = "live"
    client.app.state.store.save(current)
    base = f"/api/sessions/{session['id']}"
    practice = session["challenges"][0]
    calls = []

    def voice(role):
        calls.append(role)
        return "wss://mock.elevenlabs.test/conversation"

    monkeypatch.setattr(client.app.state.providers, "signed_url", voice)
    context = {"session_id": session["id"], "role": "tutor", "challenge_id": practice["id"]}
    assert client.post(f"{base}/tools/context", json=context).status_code == 409
    assert (
        client.post(f"{base}/voice/tutor", json={"challenge_id": practice["id"]}).status_code == 409
    )
    assert calls == []
    assert client.get(base).json()["attempts"] == []
    client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    )
    assert client.post(f"{base}/voice/tutor").status_code == 409
    assert (
        client.post(
            f"{base}/tools/context", json={"session_id": session["id"], "role": "tutor"}
        ).status_code
        == 409
    )
    response = client.post(f"{base}/tools/context", json=context)
    assert response.status_code == 200
    assert response.json()["case"]["id"] == practice["case"]["id"]
    correction = client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={
            "decision": "Hold",
            "reason": "The report version is older than the software version.",
        },
    )
    assert correction.json()["outcome"] == "hinted"


def test_assessment_refuses_tutor_assistance_even_after_a_practice_answer(client, monkeypatch):
    session = approved_session(client)
    current = client.app.state.store.get(session["id"])
    current.mode = "live"
    client.app.state.store.save(current)
    base = f"/api/sessions/{session['id']}"
    practice, assessment = session["challenges"]
    calls = []

    def voice(role):
        calls.append(role)
        return "wss://mock.elevenlabs.test/conversation"

    monkeypatch.setattr(client.app.state.providers, "signed_url", voice)
    client.post(
        f"{base}/challenges/{practice['id']}/answer",
        json={"decision": "Ready for approval", "reason": "All tests passed."},
    )
    context = {"session_id": session["id"], "role": "tutor", "challenge_id": assessment["id"]}
    for record_answer in [False, True]:
        if record_answer:
            client.post(
                f"{base}/challenges/{assessment['id']}/answer",
                json={"decision": "Hold", "reason": "Because I think so."},
            )
        assert client.post(f"{base}/tools/context", json=context).status_code == 409
        assert (
            client.post(f"{base}/voice/tutor", json={"challenge_id": assessment["id"]}).status_code
            == 409
        )
    assert calls == []
    assert not client.get(base).json()["attempts"][1]["hint_used"]
