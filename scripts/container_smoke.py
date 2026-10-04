"""Verify the running Compose frontend, API proxy, and WebSocket event stream."""

import asyncio
import json
from urllib.request import Request, urlopen

from websockets.asyncio.client import connect

BASE_URL = "http://127.0.0.1:4173"


def fetch(path: str, body: dict | None = None, method: str | None = None):
    request = Request(
        BASE_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


async def events(session_id: str) -> None:
    async with connect(
        f"ws://127.0.0.1:4173/api/sessions/{session_id}/events",
        origin=BASE_URL,
        open_timeout=10,
    ) as websocket:
        message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=10))
        assert message["session_id"] == session_id


def main() -> None:
    assert fetch("/ready")["status"] == "ready"
    with urlopen(BASE_URL, timeout=10) as response:
        assert b'<div id="root">' in response.read()
    session = fetch("/api/sessions", {"mode": "simulated"})
    session_id = session["id"]
    try:
        assert fetch(f"/api/sessions/{session_id}")["mode"] == "simulated"
        fetch(
            f"/api/sessions/{session_id}/recording",
            {"consent": True, "off_record": False},
        )
        fetch(f"/api/sessions/{session_id}/cases/B/observe", {})
        asyncio.run(events(session_id))
    finally:
        fetch(f"/api/sessions/{session_id}", method="DELETE")
    print("Deployment smoke passed: app shell, readiness, API, and WebSocket proxy.")


if __name__ == "__main__":
    main()
