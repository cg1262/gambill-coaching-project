from __future__ import annotations

import os
from copy import deepcopy
from typing import Any


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except Exception:
        return default


def _env_text(name: str, default: str) -> str:
    raw = str(os.getenv(name) or "").strip()
    return raw or default


_RUNTIME_RATE_LIMIT_CONFIG_DEFAULT: dict[str, Any] = {
    "web_runtime": {
        "required_node_min": _env_text("WEB_RUNTIME_NODE_MIN", "20.11.1"),
        "required_node_max_major_exclusive": _env_int("WEB_RUNTIME_NODE_MAX_MAJOR_EXCLUSIVE", 21),
        "required_npm_major": _env_int("WEB_RUNTIME_NPM_MAJOR", 10),
        "preflight_scripts": ["dev", "typecheck", "build", "build:clean"],
        "enforced_by": "apps/web/scripts/require-runtime.cjs",
        "notes": "Frontend runtime parity guard for deterministic Next build behavior.",
    },
    "rate_limit_ui": {
        "default_retry_seconds": _env_int("RATE_LIMIT_UI_DEFAULT_RETRY_SECONDS", 30),
        "helper_message": _env_text(
            "RATE_LIMIT_UI_HELPER_MESSAGE",
            "If retries keep failing, wait a minute, then try again or contact support with the exact action.",
        ),
    },
}

_RUNTIME_RATE_LIMIT_CONFIG = deepcopy(_RUNTIME_RATE_LIMIT_CONFIG_DEFAULT)


def runtime_rate_limit_snapshot() -> dict[str, Any]:
    data = deepcopy(_RUNTIME_RATE_LIMIT_CONFIG)
    ui = data.get("rate_limit_ui", {})
    # frontend parity convenience aliases
    ui["defaultRetrySeconds"] = int(ui.get("default_retry_seconds") or 30)
    ui["helperMessage"] = str(ui.get("helper_message") or "")
    return {
        "ok": True,
        "admin_editable": True,
        "source": "in_memory_with_env_defaults",
        **data,
    }


def runtime_rate_limit_update(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return runtime_rate_limit_snapshot()

    web_runtime = payload.get("web_runtime")
    if isinstance(web_runtime, dict):
        current = _RUNTIME_RATE_LIMIT_CONFIG["web_runtime"]
        if "required_node_min" in web_runtime:
            txt = str(web_runtime.get("required_node_min") or "").strip()
            if txt:
                current["required_node_min"] = txt
        if "required_node_max_major_exclusive" in web_runtime:
            try:
                current["required_node_max_major_exclusive"] = max(1, int(web_runtime["required_node_max_major_exclusive"]))
            except Exception:
                pass
        if "required_npm_major" in web_runtime:
            try:
                current["required_npm_major"] = max(1, int(web_runtime["required_npm_major"]))
            except Exception:
                pass
        if isinstance(web_runtime.get("preflight_scripts"), list):
            scripts = [str(x).strip() for x in web_runtime["preflight_scripts"] if str(x).strip()]
            if scripts:
                current["preflight_scripts"] = scripts
        if "notes" in web_runtime:
            notes = str(web_runtime.get("notes") or "").strip()
            if notes:
                current["notes"] = notes

    rate_limit_ui = payload.get("rate_limit_ui")
    if isinstance(rate_limit_ui, dict):
        current_ui = _RUNTIME_RATE_LIMIT_CONFIG["rate_limit_ui"]
        retry_val = rate_limit_ui.get("default_retry_seconds", rate_limit_ui.get("defaultRetrySeconds"))
        if retry_val is not None:
            try:
                current_ui["default_retry_seconds"] = max(1, int(retry_val))
            except Exception:
                pass
        helper_val = rate_limit_ui.get("helper_message", rate_limit_ui.get("helperMessage"))
        if helper_val is not None:
            helper_txt = str(helper_val).strip()
            if helper_txt:
                current_ui["helper_message"] = helper_txt

    return runtime_rate_limit_snapshot()
