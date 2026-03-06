from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque


class InvalidWebhookSignatureTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: dict[tuple[str, str, str], deque[int]] = defaultdict(deque)

    def record_attempt(self, *, provider: str, source_ip: str, route: str, now_ts: int | None = None) -> tuple[bool, int]:
        threshold = max(1, int(os.getenv("WEBHOOK_INVALID_SIG_ALERT_THRESHOLD", "5") or 5))
        window_seconds = max(1, int(os.getenv("WEBHOOK_INVALID_SIG_ALERT_WINDOW_SECONDS", "300") or 300))
        now = int(now_ts if now_ts is not None else time.time())

        key = ((provider or "generic").strip().lower(), (source_ip or "unknown").strip() or "unknown", (route or "unknown").strip())
        with self._lock:
            bucket = self._attempts[key]
            cutoff = now - window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)
            count = len(bucket)
            triggered = count == threshold
            return triggered, count


INVALID_WEBHOOK_SIGNATURE_TRACKER = InvalidWebhookSignatureTracker()
