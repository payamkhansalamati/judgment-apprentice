"""Delete simulated sessions through the local API; live sessions are preserved."""

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000/api"


def fetch(path: str, method: str = "GET"):
    with urlopen(Request(f"{BASE_URL}{path}", method=method), timeout=10) as response:
        return json.load(response)


def main() -> None:
    removed = 0
    for summary in fetch("/sessions"):
        session = fetch(f"/sessions/{summary['id']}")
        if session["mode"] == "simulated":
            fetch(f"/sessions/{session['id']}", method="DELETE")
            removed += 1
    print(f"Deleted {removed} simulated sessions and their local derived artifacts.")
    print("Start a new simulated session in the app to restore the seeded cases.")


if __name__ == "__main__":
    try:
        main()
    except URLError as error:
        raise SystemExit("Start the local backend before resetting demo sessions.") from error
