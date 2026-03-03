from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass


@dataclass
class WebhookVerificationResult:
    valid: bool
    reason: str | None = None
    provider: str | None = None
    timestamp: int | None = None


def _provider_secret(provider: str) -> str:
    normalized = str(provider or "generic").strip().upper().replace("-", "_")
    return str(
        os.getenv(f"WEBHOOK_SECRET_{normalized}")
        or os.getenv("COACHING_WEBHOOK_SECRET")
        or ""
    ).strip()


def _extract_timestamp_and_signature(provider: str, headers: dict[str, str]) -> tuple[int | None, str | None]:
    lower = {str(k).lower(): str(v) for k, v in (headers or {}).items()}

    if "stripe-signature" in lower:
        raw = lower.get("stripe-signature") or ""
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        ts = None
        sig = None
        for p in parts:
            if p.startswith("t="):
                try:
                    ts = int(p.split("=", 1)[1].strip())
                except Exception:
                    ts = None
            if p.startswith("v1="):
                sig = p.split("=", 1)[1].strip()
        return ts, sig

    ts_header_candidates = [
        "x-webhook-timestamp",
        "x-signature-timestamp",
        "x-squarespace-request-timestamp",
    ]
    sig_header_candidates = [
        "x-webhook-signature",
        "x-signature",
        "x-squarespace-signature",
    ]

    ts = None
    for name in ts_header_candidates:
        if name in lower:
            try:
                ts = int(str(lower.get(name) or "").strip())
            except Exception:
                ts = None
            break

    sig = None
    for name in sig_header_candidates:
        if name in lower:
            sig = str(lower.get(name) or "").strip()
            break

    return ts, sig


def verify_webhook_signature(*, provider: str, body_bytes: bytes, headers: dict[str, str], tolerance_seconds: int = 300, now_ts: int | None = None) -> WebhookVerificationResult:
    provider_name = str(provider or "generic").strip().lower()
    secret = _provider_secret(provider_name)
    if not secret:
        return WebhookVerificationResult(valid=False, reason="secret_missing", provider=provider_name)

    timestamp, incoming_signature = _extract_timestamp_and_signature(provider_name, headers)
    if timestamp is None:
        return WebhookVerificationResult(valid=False, reason="timestamp_missing", provider=provider_name)
    if not incoming_signature:
        return WebhookVerificationResult(valid=False, reason="signature_missing", provider=provider_name)

    ts_now = int(now_ts if now_ts is not None else time.time())
    if abs(ts_now - int(timestamp)) > int(tolerance_seconds):
        return WebhookVerificationResult(valid=False, reason="timestamp_out_of_tolerance", provider=provider_name, timestamp=timestamp)

    signed_payload = f"{timestamp}.".encode("utf-8") + (body_bytes or b"")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(incoming_signature, digest):
        return WebhookVerificationResult(valid=False, reason="invalid_signature", provider=provider_name, timestamp=timestamp)

    return WebhookVerificationResult(valid=True, provider=provider_name, timestamp=timestamp)


def parse_webhook_body(raw: bytes) -> dict:
    try:
        payload = json.loads((raw or b"{}").decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
