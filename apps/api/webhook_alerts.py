from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InvalidSignatureAlertEvent:
    provider: str
    source_ip: str
    route: str
    reason: str
    attempt_count: int
    threshold: int
    window_seconds: int
    actor: str | None
    role: str | None
    created_at: int


class InvalidWebhookSignatureTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: dict[tuple[str, str, str], deque[int]] = defaultdict(deque)
        self._alerts: deque[dict[str, Any]] = deque(maxlen=200)

    @staticmethod
    def _normalize_key(provider: str, source_ip: str, route: str) -> tuple[str, str, str]:
        return (
            (provider or "generic").strip().lower(),
            (source_ip or "unknown").strip() or "unknown",
            (route or "unknown").strip(),
        )

    def record_attempt(
        self,
        *,
        provider: str,
        source_ip: str,
        route: str,
        threshold: int = 5,
        window_seconds: int = 300,
        now_ts: int | None = None,
    ) -> tuple[bool, int]:
        threshold = max(1, int(threshold or 5))
        window_seconds = max(1, int(window_seconds or 300))
        now = int(now_ts if now_ts is not None else time.time())

        key = self._normalize_key(provider, source_ip, route)
        with self._lock:
            bucket = self._attempts[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)
            count = len(bucket)
            triggered = count == threshold
            return triggered, count

    def record_alert(self, event: InvalidSignatureAlertEvent) -> dict[str, Any]:
        payload: dict[str, Any] = asdict(event)
        with self._lock:
            self._alerts.appendleft(payload)
        return payload

    def recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit or 50), 200))
        with self._lock:
            return list(self._alerts)[:lim]


def dispatch_invalid_webhook_signature_alert(alert_payload: dict[str, Any]) -> bool:
    """Best-effort operational routing.

    If WEBHOOK_INVALID_SIG_ALERT_WEBHOOK_URL is configured, POST JSON payload.
    Returns True on successful 2xx webhook dispatch, False otherwise.
    """
    url = str(os.getenv("WEBHOOK_INVALID_SIG_ALERT_WEBHOOK_URL") or "").strip()
    if not url:
        return False
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(alert_payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310 - controlled by operator env var
            return int(getattr(resp, "status", 500)) < 300
    except Exception:
        return False


INVALID_WEBHOOK_SIGNATURE_TRACKER = InvalidWebhookSignatureTracker()
