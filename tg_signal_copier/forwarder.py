import json
import logging
import os
import time
from typing import Any, Dict, Optional
import httpx

from tg_signal_copier.metrics import METRICS

logger = logging.getLogger(__name__)


class Forwarder:
    """Pushes normalized signal payloads to a configured HTTP webhook endpoint."""

    def __init__(
        self,
        target_url: str,
        auth_token: Optional[str] = None,
        secret_header: Optional[str] = None,
        timeout_sec: float = 6.0,
        max_attempts: int = 4,
        dead_letter_path: str = "dead_letter.jsonl",
    ):
        self.target_url = target_url
        self.auth_token = auth_token
        self.secret_header = secret_header
        self.timeout = timeout_sec
        self.max_attempts = max_attempts
        self.dead_letter_path = dead_letter_path
        self.client = httpx.Client(timeout=self.timeout)

    def _dump_dead_letter(self, payload: Dict[str, Any], last_error: str) -> None:
        entry = {
            "failed_at": time.time(),
            "target": self.target_url,
            "reason": last_error,
            "payload": payload,
        }
        try:
            with open(self.dead_letter_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            # If disk write fails here there's not much else we can do
            logger.critical("unable to write dead-letter record: %s", e)

    def forward(self, payload: Dict[str, Any]) -> bool:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "tg-signal-copier/0.3",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.secret_header:
            headers["X-Signature-Key"] = self.secret_header

        sig_id = payload.get("signal_id", "unknown")
        payload_bytes = json.dumps(payload).encode("utf-8")
        last_err = "unknown"

        for attempt in range(1, self.max_attempts + 1):
            call_start = time.perf_counter()
            # print(f"DEBUG: posting {sig_id} to {self.target_url}")
            try:
                resp = self.client.post(self.target_url, content=payload_bytes, headers=headers)
                elapsed_ms = (time.perf_counter() - call_start) * 1000
                METRICS.observe_latency("forward_webhook_ms", elapsed_ms)

                if resp.status_code in (200, 201, 202, 204):
                    METRICS.inc("signals_delivered_total")
                    logger.info(
                        "forwarded signal %s in %.1fms (attempt %d)",
                        sig_id,
                        elapsed_ms,
                        attempt,
                    )
                    return True

                last_err = f"http_{resp.status_code}_{resp.text[:80]}"
                logger.warning(
                    "target returned %d for %s (attempt %d)",
                    resp.status_code,
                    sig_id,
                    attempt,
                )

                # respect 429 Retry-After if present
                if resp.status_code == 429:
                    retry_header = resp.headers.get("Retry-After")
                    if retry_header and retry_header.isdigit():
                        sleep_time = min(float(retry_header), 10.0)
                        time.sleep(sleep_time)
                        continue

            except httpx.RequestError as exc:
                last_err = f"net_{type(exc).__name__}"
                logger.warning("network error sending %s on attempt %d: %s", sig_id, attempt, exc)

            if attempt < self.max_attempts:
                # simple exponential backoff: 0.4s, 0.8s, 1.6s
                backoff = 0.4 * (2 ** (attempt - 1))
                time.sleep(backoff)

        METRICS.inc("signals_failed_total")
        logger.error("giving up on %s after %d tries, dumping to dead-letter", sig_id, self.max_attempts)
        self._dump_dead_letter(payload, last_err)
        return False

    def close(self) -> None:
        self.client.close()
