from __future__ import annotations

import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from security import mask_secrets_in_text


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_private_or_loopback_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if not value:
        return True
    if value in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(value)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(value, None)
    except Exception:
        return True
    for info in infos:
        ip_txt = str(info[4][0])
        try:
            ip = ipaddress.ip_address(ip_txt)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            return True
    return False


def _validate_safe_url(url: str) -> tuple[bool, str | None]:
    raw = str(url or "").strip()
    if not raw:
        return False, "missing_url"
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"javascript", "data"}:
        return False, f"blocked_scheme:{scheme}"
    if scheme not in {"http", "https"}:
        return False, f"unsupported_scheme:{scheme or 'none'}"
    if not parsed.netloc:
        return False, "missing_host"
    if _is_private_or_loopback_host(parsed.hostname or ""):
        return False, "blocked_private_host"
    return True, None


def _is_valid_non_placeholder_url(url: str) -> bool:
    s = str(url or "").strip().lower()
    if not (s.startswith("http://") or s.startswith("https://")):
        return False
    blocked = ["example.com", "localhost", "127.0.0.1", "placeholder", "your-link", "tbd"]
    return not any(b in s for b in blocked)


def _mask_if_str(value: Any) -> Any:
    return mask_secrets_in_text(value) if isinstance(value, str) else value


def _mask_strings_deep(value: Any) -> Any:
    if isinstance(value, str):
        return mask_secrets_in_text(value)
    if isinstance(value, dict):
        return {k: _mask_strings_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_strings_deep(v) for v in value]
    return value


def sanitize_generated_sow(sow: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    out = json.loads(json.dumps(sow or {}))
    findings: list[dict[str, str]] = []

    if "project_title" in out:
        out["project_title"] = _mask_if_str(out.get("project_title"))

    if "project_story" in out:
        out["project_story"] = _mask_strings_deep(out.get("project_story"))

    resources = out.get("resource_plan") or {}
    for bucket in ["required", "recommended", "optional"]:
        cleaned_items = []
        for item in (resources.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if isinstance(row.get("title"), str):
                row["title"] = mask_secrets_in_text(row["title"])
            if isinstance(row.get("reason"), str):
                row["reason"] = mask_secrets_in_text(row["reason"])
            ok, reason = _validate_safe_url(str(row.get("url") or ""))
            if not ok:
                findings.append(
                    {
                        "code": "UNSAFE_RESOURCE_URL",
                        "message": f"Blocked unsafe resource_plan.{bucket} URL ({reason}).",
                    }
                )
                row["url"] = ""
                row["safety_flag"] = "blocked_unsafe_url"
            cleaned_items.append(row)
        resources[bucket] = cleaned_items

    for text_key in ["affiliate_disclosure", "trust_language"]:
        if isinstance(resources.get(text_key), str):
            resources[text_key] = mask_secrets_in_text(resources[text_key])
    out["resource_plan"] = resources

    mentoring = out.get("mentoring_cta") or {}
    for text_key in ["reason", "offer", "pricing", "timeline", "cta_text", "trust_language"]:
        if isinstance(mentoring.get(text_key), str):
            mentoring[text_key] = mask_secrets_in_text(mentoring[text_key])
    if "program_url" in mentoring:
        ok, reason = _validate_safe_url(str(mentoring.get("program_url") or ""))
        if not ok:
            findings.append({"code": "UNSAFE_PROGRAM_URL", "message": f"Blocked unsafe mentoring_cta.program_url ({reason})."})
            mentoring["program_url"] = ""
            mentoring["safety_flag"] = "blocked_unsafe_url"
    out["mentoring_cta"] = mentoring

    business_outcome = out.get("business_outcome") or {}
    for text_key in ["problem_statement", "target_users", "success_metric", "constraints"]:
        if text_key in business_outcome:
            business_outcome[text_key] = _mask_if_str(business_outcome.get(text_key))
    out["business_outcome"] = business_outcome

    for ms in (out.get("milestones") or []):
        if not isinstance(ms, dict):
            continue
        for text_key in ["name", "execution_plan", "expected_deliverable", "business_why"]:
            if text_key in ms:
                ms[text_key] = _mask_if_str(ms.get(text_key))
        if isinstance(ms.get("deliverables"), list):
            ms["deliverables"] = [_mask_if_str(x) for x in (ms.get("deliverables") or [])]

    return out, findings
