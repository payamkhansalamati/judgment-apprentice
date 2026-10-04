"""Request metadata only: never log bodies, headers, credentials, or provider responses."""

import json
import logging

logger = logging.getLogger("judgment_apprentice")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def request_completed(method: str, path: str, status: int, elapsed_ms: int) -> None:
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "method": method,
                "path": path,
                "status": status,
                "elapsed_ms": elapsed_ms,
            }
        )
    )
