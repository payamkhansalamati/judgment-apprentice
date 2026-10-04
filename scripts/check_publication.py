"""Check publishable files and Git history without displaying credential values."""

import io
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = {".mp4", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".pem", ".key"}
SECRET = re.compile(
    rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}"
    rb"|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def private_path(name: str) -> bool:
    path = Path(name)
    return (
        path.parts[0] in {"demo", "data", ".venv", "node_modules"}
        or (path.name.startswith(".env") and path.name != ".env.example")
        or path.suffix.lower() in MEDIA
    )


def main() -> None:
    known_keys = []
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, value = line.partition("=")
            value = value.strip().strip("\"'")
            if sep and name.strip().endswith(("_API_KEY", "_TOKEN", "_SECRET")):
                if len(value) >= 12 and not value.startswith("your-"):
                    known_keys.append(value.encode())
    failures: set[str] = set()

    def inspect(name: str, data: bytes, source: str) -> None:
        if private_path(name):
            failures.add(f"{source}: private/artifact path {name}")
        if SECRET.search(data) or any(key in data for key in known_keys):
            failures.add(f"{source}: possible credential in {name}")
        if len(data) > 10 * 1024 * 1024:
            failures.add(f"{source}: file exceeds 10 MiB: {name}")

    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    count = 0
    for raw in set(names.split(b"\0")) - {b""}:
        name = raw.decode()
        path = ROOT / name
        if path.is_file():
            inspect(name, path.read_bytes(), "working tree")
            count += 1
    commits = git("rev-list", "--all").decode().splitlines()
    for commit in commits:
        with tarfile.open(fileobj=io.BytesIO(git("archive", commit))) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    stream = archive.extractfile(member)
                    if stream is not None:
                        inspect(member.name, stream.read(), f"history {commit[:8]}")
    for name in [".env", "data/probe.sqlite", "demo/probe.txt", "probe.mp4"]:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", name], cwd=ROOT, check=False
        )
        if result.returncode != 0:
            failures.add(f"ignore protection missing: {name}")
    if failures:
        for failure in sorted(failures):
            print(failure)
        raise SystemExit("Publication audit failed; resolve listed paths before staging.")
    print(f"Publication audit passed: {count} files and {len(commits)} history commits.")
    print("Local credentials, data, and artifacts are excluded; no key values were displayed.")


if __name__ == "__main__":
    main()
