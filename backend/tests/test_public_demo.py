from uuid import UUID

import pytest
from app.integrations import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ORIGIN = "https://judgment-demo.onrender.com"


@pytest.fixture
def public_client(tmp_path):
    frontend = tmp_path / "dist"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text('<html><div id="root"></div></html>')
    (frontend / "assets" / "app.js").write_text("console.log('synthetic demo')")
    settings = Settings(
        _env_file=None,
        ja_public_demo=True,
        render_external_url=ORIGIN,
        ja_frontend_dir=str(frontend),
        openai_api_key="must-not-be-used",
        elevenlabs_api_key="must-not-be-used",
        elevenlabs_interviewer_agent_id="must-not-be-used",
        elevenlabs_tutor_agent_id="must-not-be-used",
    )
    app = create_app(tmp_path / "data", settings)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def test_production_routes_and_disabled_live_capabilities(public_client, monkeypatch):
    client = public_client
    assert client.get("/").headers["content-type"].startswith("text/html")
    assert client.get("/work-map").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    for path in ("/api/not-a-route", "/api", "/assets/missing.js", "/missing.js"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
    assert client.post("/api/not-a-route").status_code == 404
    assert client.get("/api/sessions", headers={"origin": ORIGIN}).status_code == 403
    assert client.get("/api/config").json() == {"public_demo": True}
    readiness = client.get("/ready").json()
    assert readiness["status"] == "ready"
    assert not readiness["live_vision_configured"]
    assert not readiness["live_voice_configured"]
    assert client.get("/api/sessions").status_code == 403
    assert client.post("/api/sessions", json={"mode": "live"}).status_code == 403
    response = client.post("/api/sessions", json={"mode": "simulated"})
    session_id = response.json()["id"]
    assert UUID(session_id).version == 4
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie

    def forbidden(*args, **kwargs):
        pytest.fail("A public demo called a live provider")

    monkeypatch.setattr(client.app.state.providers, "signed_url", forbidden)
    monkeypatch.setattr(client.app.state.providers, "observe", forbidden)
    for path in ("voice/interviewer", "voice/tutor", "frames", "transcript", "tools/context"):
        assert client.post(f"/api/sessions/{session_id}/{path}", json={}).status_code == 403
    assert client.get("/", headers={"origin": "https://other.example"}).status_code == 403
    assert client.get("/", headers={"host": "other.example"}).status_code == 403


def test_visitors_cannot_read_modify_delete_or_stream_other_sessions(public_client):
    first = public_client
    second = TestClient(first.app, base_url=ORIGIN)
    first_id = first.post("/api/sessions", json={}).json()["id"]
    second_id = second.post("/api/sessions", json={}).json()["id"]
    assert first_id != second_id
    assert first.cookies.get("ja-demo-visitor") != second.cookies.get("ja-demo-visitor")
    assert first.get(f"/api/sessions/{first_id}").status_code == 200
    for method, path, body in (
        ("GET", "", None),
        ("GET", "/map", None),
        ("GET", "/cases/B", None),
        ("POST", "/recording", {"consent": True, "off_record": False}),
        ("DELETE", "", None),
    ):
        assert (
            second.request(method, f"/api/sessions/{first_id}{path}", json=body).status_code == 404
        )
    with pytest.raises(WebSocketDisconnect):
        with second.websocket_connect(
            f"/api/sessions/{first_id}/events",
            headers={
                "origin": ORIGIN,
                "cookie": f"ja-demo-visitor={second.cookies.get('ja-demo-visitor')}",
            },
        ):
            pytest.fail("A visitor opened another visitor's event stream")
    first.post(f"/api/sessions/{first_id}/recording", json={"consent": True, "off_record": False})
    first.post(f"/api/sessions/{first_id}/cases/B/observe")
    with first.websocket_connect(
        f"/api/sessions/{first_id}/events",
        headers={
            "origin": ORIGIN,
            "cookie": f"ja-demo-visitor={first.cookies.get('ja-demo-visitor')}",
        },
    ) as socket:
        assert socket.receive_json()["session_id"] == first_id
    assert first.delete(f"/api/sessions/{first_id}").status_code == 200
    assert second.get(f"/api/sessions/{second_id}").status_code == 200


def test_client_chosen_cookie_is_not_accepted_as_a_visitor_identity(public_client):
    public_client.cookies.set("ja-demo-visitor", "predictable")
    response = public_client.post("/api/sessions", json={})
    assert response.status_code == 200
    assert "ja-demo-visitor=predictable" not in response.headers["set-cookie"]
