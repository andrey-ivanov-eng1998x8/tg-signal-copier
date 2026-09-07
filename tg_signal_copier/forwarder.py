import json
import logging
import time
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


class Forwarder:
    """Pushes normalized signal payloads to a configured HTTP webhook endpoint."""

    def __init__(
        self,
        target_url: str,
        auth_token: Optional[str] = None,
        timeout_sec: float = 8.0,
        max_attempts: int = 4,
    ):
        self.target_url = target_url
        self.auth_token = auth_token
        self.timeout = timeout_sec
        self.max_attempts = max_attempts
        self.client = httpx.Client(timeout=self.timeout)

    def forward(self, payload: Dict[str, Any]) -> bool:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "tg-signal-copier/0.1",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        start_ts = time.perf_counter()
        payload_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self.client.post(self.target_url, content=payload_bytes, headers=headers)
                elapsed_ms = (time.perf_counter() - start_ts) * 1000

                if resp.status_code in (200, 201, 202, 204):
                    logger.info(
                        "forwarded signal %s in %.1fms (attempt %d)",
                        payload.get("signal_id", "unknown"),
                        elapsed_ms,
                        attempt,
                    )
                    return True

                logger.warning(
                    "target returned %d on attempt %d: %s",
                    resp.status_code,
                    attempt,
                    resp.text[:120],
                )
            except httpx.RequestError as exc:
                logger.warning("network error on attempt %d: %s", attempt, exc)

            if attempt < self.max_attempts:
                # fixed linear delay for now
                time.sleep(0.5 * attempt)

        logger.error("failed to deliver signal %s after %d tries", payload.get("signal_id"), self.max_attempts)
        return False

    def close(self):
        self.client.close()
