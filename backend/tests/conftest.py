import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Importing the ASGI entrypoint must never create test data in the developer's data directory.
os.environ["JA_DATA_DIR"] = tempfile.mkdtemp(prefix="ja-test-default-")

from app.integrations import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import DEMO_ANSWERS, QUESTIONS  # noqa: E402


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(tmp_path, Settings(_env_file=None))
    with TestClient(app) as client:
        yield client


def create_session(client, mode="simulated"):
    response = client.post("/api/sessions", json={"mode": mode})
    assert response.status_code == 200, response.text
    session = response.json()
    client.post(
        f"/api/sessions/{session['id']}/recording", json={"consent": True, "off_record": False}
    )
    return session["id"]


def capture(client, session_id):
    base = f"/api/sessions/{session_id}"
    for condition, _ in QUESTIONS:
        assert client.post(f"{base}/questions").status_code == 200
        response = client.post(
            f"{base}/answers",
            json={"condition": condition, "text": DEMO_ANSWERS[condition], "scripted": True},
        )
        assert response.status_code == 200, response.text
    response = client.post(f"{base}/debrief")
    assert response.status_code == 200, response.text
    return response.json()


def approved_session(client):
    session_id = create_session(client)
    capture(client, session_id)
    base = f"/api/sessions/{session_id}"
    for gap in ["exceptions", "owner", "missing"]:
        assert (
            client.post(
                f"{base}/gaps", json={"condition": gap, "text": DEMO_ANSWERS[gap], "scripted": True}
            ).status_code
            == 200
        )
    assert client.post(f"{base}/map/teach-back").status_code == 200
    response = client.post(f"{base}/map/confirm", json={"version": 1, "explicit": True})
    assert response.status_code == 200, response.text
    session = response.json()
    for challenge in session["challenges"]:
        assert (
            client.post(
                f"{base}/challenges/{challenge['id']}/approve",
                json={"version": 1, "explicit": True},
            ).status_code
            == 200
        )
    return client.get(base).json()
