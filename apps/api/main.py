from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, File, Form
from uuid import uuid4
from pathlib import Path
import json
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
import base64
from datetime import datetime, timezone, timedelta
import json as _json_stdlib
import logging
import logging.config
import os
import hashlib
import hmac
import time
import io
import zipfile
import xml.etree.ElementTree as ET
import re
from typing import Any

from models import CanvasAST, ValidationResult, ImpactResult, CoachingSowDraft
from services import (
    run_deterministic_validation,
    run_probabilistic_validation,
    run_deterministic_impact,
    run_probabilistic_impact,
)
from coaching import (
    fetch_job_text,
    extract_job_signals,
    build_sow_skeleton,
    generate_sow_with_llm,
    validate_sow_payload,
    auto_revise_sow_once,
    match_resources_for_sow,
    compose_demo_project_package,
    sanitize_generated_sow,
    compute_sow_quality_score,
    build_quality_diagnostics,
    ensure_interview_ready_package,
    enforce_required_section_order,
    extract_resume_signals,
)
from db_lakebase import (
    healthcheck as lakebase_health,
    bootstrap_status as lakebase_bootstrap_status,
    get_connection_settings,
    upsert_connection_settings,
    save_dependency_mapping,
    save_policy_document,
    save_policy_chunks,
    search_policy_chunks,
    list_policy_documents,
    upsert_workspace_policy_config,
    get_workspace_policy_config,
    upsert_finding_status,
    get_finding_statuses,
    get_finding_status_audit,
    get_run_history,
    list_users,
    upsert_user,
    is_configured as lakebase_is_configured,
    save_coaching_intake_submission,
    get_coaching_intake_submission,
    list_coaching_intake_submissions,
    update_coaching_intake_preferences,
    save_coaching_generation_run,
    get_latest_coaching_generation_run,
    list_coaching_generation_runs,
    update_coaching_review_status,
    upsert_coaching_job_parse_cache,
    get_coaching_job_parse_cache,
    upsert_coaching_account_subscription,
    get_coaching_account_subscription,
    save_coaching_subscription_event,
    get_coaching_subscription_event,
    list_recent_coaching_subscription_events,
    save_coaching_conversion_event,
    list_recent_coaching_conversion_events,
    list_coaching_conversion_events_window,
    save_coaching_feedback_event,
    list_recent_coaching_feedback_events,
)
from uc_client import healthcheck as uc_health, fetch_information_schema, fetch_schemas
from git_ops import git_status, save_and_push_ast, set_git_config
from db_lakebase import get_user_auth
from auth import Session, get_current_session, get_current_user, issue_token, whoami, assert_role, revoke_token, revoke_user_sessions, session_stats
from security import (
    DEFAULT_MAX_RESUME_BYTES,
    FileValidationError,
    build_safe_resume_path,
    mask_secrets_in_text,
    mask_sensitive_dict,
    pii_safe_auth_log_payload,
    pii_safe_coaching_log_payload,
    pii_safe_subscription_log_payload,
    validate_resume_metadata,
)
from rate_limits import RateLimitExceeded, enforce_rate_limit, policy_snapshot as rate_limit_policy_snapshot, policy_update as rate_limit_policy_update
from webhook_security import parse_webhook_body, verify_webhook_signature
from webhook_alerts import INVALID_WEBHOOK_SIGNATURE_TRACKER, InvalidSignatureAlertEvent, dispatch_invalid_webhook_signature_alert
from admin_runtime_config import runtime_rate_limit_snapshot, runtime_rate_limit_update

class _JsonFormatter(logging.Formatter):
    """JSON log formatter — no extra packages required."""

    _RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                base[k] = v
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return _json_stdlib.dumps(base, default=str)


logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": _JsonFormatter}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        "gambill_coaching.api": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
})

logger = logging.getLogger("gambill_coaching.api")
RESOURCE_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "docs" / "coaching-project" / "RESOURCE_LIBRARY.json"
DOCX_EXPORT_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1"))
    if web_concurrency > 1:
        logger.warning(
            "multi_worker_in_memory_state",
            extra={
                "event": "startup_warning",
                "web_concurrency": web_concurrency,
                "detail": (
                    f"WEB_CONCURRENCY={web_concurrency}: in-memory session store (auth.py) "
                    "and rate limit store (rate_limits.py) are NOT shared across workers. "
                    "A Redis backend is required for production multi-worker deployments."
                ),
            },
        )
    yield


app = FastAPI(
    title="Gambill Coaching API",
    version="0.2.0",
    description="AI-powered data engineering coaching platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)


def _client_ip(request: Request) -> str:
    xff = str(request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return str((request.client.host if request.client else "unknown") or "unknown")


def _apply_rate_limit(*, policy_name: str, request: Request, session: Session | None = None, workspace_id: str | None = None) -> None:
    try:
        enforce_rate_limit(
            policy_name,
            ip=_client_ip(request),
            user=(session.username if session else None),
            workspace=workspace_id,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "ok": False,
                "code": "rate_limit_exceeded",
                "policy": exc.policy,
                "rule": exc.rule,
                "retry_after_seconds": exc.retry_after_seconds,
                "message": "Too many requests. Please retry later.",
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    is_coaching_or_auth_route = request.url.path.startswith("/coaching") or request.url.path.startswith("/auth")
    if is_coaching_or_auth_route and exc.status_code in {401, 403, 429}:
        detail = exc.detail if isinstance(exc.detail, dict) else None
        is_rate_limited = exc.status_code == 429
        is_subscription = (not is_rate_limited) and (bool(detail and detail.get("subscription_required")) or "subscription" in str(exc.detail).lower())
        message = (
            "Too many requests. Please wait and retry."
            if is_rate_limited
            else (
                "Active coaching subscription required. Sync membership or reactivate subscription before retrying."
                if is_subscription
                else "Authentication required. Send Authorization: Bearer <token> and ensure your role has access."
            )
        )
        payload = {
            "ok": False,
            "code": "rate_limited" if is_rate_limited else ("subscription_required" if is_subscription else ("auth_required" if exc.status_code == 401 else "forbidden")),
            "auth_required": exc.status_code == 401,
            "subscription_required": is_subscription,
            "message": message,
        }
        return JSONResponse(status_code=exc.status_code, content=payload)

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def _chunk_text(content: str, max_len: int = 800) -> list[str]:
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    chunks: list[str] = []
    current = ""
    for line in lines:
        nxt = f"{current}\n{line}".strip()
        if len(nxt) <= max_len:
            current = nxt
        else:
            if current:
                chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks


def _redact_settings(connection_type: str, settings: dict) -> dict:
    secret_key_map = {
        "databricks_uc": {"token", "connection_string"},
        "information_schema": {"password"},
        "power_bi": {"client_secret"},
    }
    return mask_sensitive_dict(dict(settings or {}), secret_keys=secret_key_map.get(connection_type, set()))


def _extract_text_from_docx_bytes(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
        return " ".join(texts)
    except Exception:
        return ""


def _extract_text_from_pdf_bytes(content: bytes) -> str:
    try:
        decoded = content.decode("latin-1", errors="ignore")
    except Exception:
        return ""
    chunks = []
    for match in re.findall(r"\(([^\)]{2,})\)", decoded):
        txt = re.sub(r"\\[nrt]", " ", match)
        txt = re.sub(r"\\\d{1,3}", "", txt)
        if re.search(r"[A-Za-z]{3,}", txt):
            chunks.append(txt)
    return " ".join(chunks)[:20000]


def _extract_resume_text(filename: str, content: bytes) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext == ".txt":
        return content.decode("utf-8", errors="ignore"), "txt"
    if ext == ".docx":
        parsed = _extract_text_from_docx_bytes(content)
        return parsed, "docx_xml"
    if ext == ".pdf":
        parsed = _extract_text_from_pdf_bytes(content)
        return parsed, "pdf_heuristic"
    return "", "unsupported"


def _safe_generation_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    src = dict(meta or {})
    usage_src = src.get("usage") if isinstance(src.get("usage"), dict) else {}
    safe_usage = {
        key: int(value)
        for key, value in usage_src.items()
        if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and isinstance(value, (int, float))
    }
    out: dict[str, Any] = {
        "provider": str(src.get("provider") or "unknown"),
        "model": str(src.get("model") or "unknown"),
        "attempts": int(src.get("attempts") or 0),
        "error_type": src.get("error_type") if src.get("error_type") in {"provider", "network", "timeout", "schema", None} else "provider",
    }
    reason_code = str(src.get("reason_code") or "").strip().upper()
    if reason_code:
        out["reason_code"] = reason_code
    if src.get("finish_reason"):
        out["finish_reason"] = str(src.get("finish_reason"))
    if safe_usage:
        out["usage"] = safe_usage
    return out


def _latency_band(latency_ms: int) -> str:
    if latency_ms < 1500:
        return "fast"
    if latency_ms < 5000:
        return "moderate"
    return "slow"


def _cost_band(total_tokens: int) -> str:
    if total_tokens < 2500:
        return "low"
    if total_tokens < 8000:
        return "medium"
    return "high"


def _track_conversion_event(
    *,
    workspace_id: str,
    submission_id: str | None,
    event_name: str,
    actor_user: str,
    payload: dict[str, Any] | None = None,
) -> None:
    try:
        save_coaching_conversion_event(
            event_id=str(uuid4()),
            workspace_id=workspace_id,
            submission_id=submission_id,
            event_name=event_name,
            actor_user=actor_user,
            event_payload=payload or {},
        )
    except Exception:
        pass


def _to_canvas_data_type(databricks_type: str) -> str:
    t = (databricks_type or "").lower()
    if any(x in t for x in ["int", "tinyint", "smallint"]):
        return "int"
    if "bigint" in t or "long" in t:
        return "bigint"
    if any(x in t for x in ["decimal", "numeric", "double", "float"]):
        return "decimal"
    if "bool" in t:
        return "boolean"
    if t in {"date"}:
        return "date"
    if any(x in t for x in ["timestamp", "time"]):
        return "timestamp"
    if "array" in t:
        return "array"
    if "struct" in t or "map" in t:
        return "struct"
    if "json" in t:
        return "json"
    return "string"


class GitPushAstRequest(BaseModel):
    ast: CanvasAST
    commit_message: str | None = None
    push: bool = True


class GitConfigRequest(BaseModel):
    workspace_id: str
    repo_path: str
    branch: str
    remote: str = "origin"


class LoginRequest(BaseModel):
    username: str
    password: str


class ConnectionSettingsRequest(BaseModel):
    workspace_id: str
    connection_type: str  # databricks_uc | information_schema | git | power_bi
    settings: dict


class DependencyMappingRequest(BaseModel):
    workspace_id: str
    source_object: str
    target_object: str
    dependency_type: str = "pipeline"
    confidence: float = 85.0
    source_system: str = "manual"
    notes: str | None = None


class PolicyUploadRequest(BaseModel):
    workspace_id: str
    doc_name: str
    doc_type: str  # standards | regulatory | custom
    content_text: str


class UserUpsertRequest(BaseModel):
    username: str
    role: str
    active: bool = True
    password: str | None = None


class PolicyConfigRequest(BaseModel):
    workspace_id: str
    standards_template_name: str
    standards_template_version: str = "1.0"
    regulatory_template_name: str
    regulatory_template_version: str = "1.0"


class FindingStatusRequest(BaseModel):
    workspace_id: str
    finding_key: str
    status: str  # open | accepted-risk | remediated | false-positive
    note: str | None = None


class FindingBulkStatusRequest(BaseModel):
    workspace_id: str
    finding_keys: list[str]
    status: str
    note: str | None = None


class PrWebhookRequest(BaseModel):
    webhook_url: str
    markdown: str


class ProviderPrCommentRequest(BaseModel):
    provider: str  # github | gitlab
    api_url: str
    token: str
    repo: str | None = None
    pr_number: int | None = None
    project_id: str | None = None
    merge_request_iid: int | None = None
    markdown: str


class GithubArtifactsRequest(BaseModel):
    api_url: str = "https://api.github.com"
    token: str
    repo: str
    branch: str = "main"
    base_path: str = "governance-reports"
    ast: dict
    findings: list[dict]


class DatabricksConnectionValidateRequest(BaseModel):
    workspace_id: str
    settings: dict
    run_live_test: bool = False


class DatabricksSchemaSyncRequest(BaseModel):
    workspace_id: str
    limit_tables: int = 300
    limit_columns: int = 4000
    settings: dict | None = None


class DatabricksSchemasRequest(BaseModel):
    workspace_id: str
    settings: dict | None = None


class CoachingJobLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=80)


class CoachingIntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1, max_length=120)
    applicant_name: str = Field(min_length=1, max_length=120)
    applicant_email: str | None = Field(default=None, max_length=254)
    resume_text: str = Field(default="", max_length=12000)
    self_assessment_text: str = Field(default="", max_length=12000)
    self_assessment: dict[str, Any] = Field(default_factory=dict)
    resume_parse_summary: dict[str, Any] = Field(default_factory=dict)
    stack_preferences: list[str] = Field(default_factory=list, max_length=25)
    tool_preferences: list[str] = Field(default_factory=list, max_length=40)
    job_links: list[str | CoachingJobLinkInput] = Field(default_factory=list, max_length=20)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("stack_preferences", "tool_preferences")
    @classmethod
    def validate_checkbox_values(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            txt = str(item or "").strip()
            if not txt:
                continue
            if len(txt) > 80:
                raise ValueError("Stack/tool entries must be 80 chars or fewer")
            cleaned.append(txt)
        return cleaned

    @field_validator("self_assessment")
    @classmethod
    def validate_self_assessment(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "career_clarity",
            "sql_confidence",
            "python_confidence",
            "data_modeling_confidence",
            "etl_pipeline_confidence",
            "cloud_platform_confidence",
            "analytics_storytelling_confidence",
            "job_search_execution",
            "interview_readiness",
            "portfolio_readiness",
            "notes",
        }
        for key in value.keys():
            if key not in allowed_keys:
                raise ValueError(f"Unsupported self_assessment field: {key}")
        return value

    @field_validator("resume_parse_summary")
    @classmethod
    def validate_resume_parse_summary(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "role_level",
            "tools",
            "domains",
            "project_experience_keywords",
            "strengths",
            "gaps",
            "years_experience_hint",
            "role_evidence",
            "parse_confidence",
            "parse_confidence_explainability",
            "parse_strategy",
            "fallback_used",
            "parse_warning",
            "filename",
        }
        for key in value.keys():
            if key not in allowed_keys:
                raise ValueError(f"Unsupported resume_parse_summary field: {key}")
        return value

    @field_validator("job_links")
    @classmethod
    def validate_job_links(cls, value: list[str | CoachingJobLinkInput]) -> list[CoachingJobLinkInput]:
        normalized: list[CoachingJobLinkInput] = []
        for idx, raw in enumerate(value):
            link_obj = CoachingJobLinkInput(url=raw) if isinstance(raw, str) else raw
            link = str(link_obj.url or "").strip()
            if not link:
                continue
            parsed = urlparse(link)
            scheme = (parsed.scheme or "").lower()
            if scheme not in {"http", "https"}:
                raise ValueError(f"job_links[{idx}].url must start with http:// or https://")
            if not parsed.netloc:
                raise ValueError(f"job_links[{idx}].url must be a fully-qualified URL")
            normalized.append(CoachingJobLinkInput(url=link, title=link_obj.title, source=link_obj.source))
        return normalized

    @field_validator("preferences")
    @classmethod
    def validate_preferences(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "target_role",
            "preferred_stack",
            "timeline_weeks",
            "resume_profile",
            "combined_profile",
            "profile_overrides",
            "stack_preferences",
            "tool_preferences",
            "resume_parse_summary",
        }
        for key in value.keys():
            if key not in allowed_keys:
                raise ValueError(f"Unsupported preference field: {key}")

        target_role = value.get("target_role")
        if target_role is not None and len(str(target_role).strip()) > 120:
            raise ValueError("preferences.target_role must be 120 chars or fewer")

        preferred_stack = value.get("preferred_stack")
        if preferred_stack is not None and len(str(preferred_stack).strip()) > 120:
            raise ValueError("preferences.preferred_stack must be 120 chars or fewer")

        timeline = value.get("timeline_weeks")
        if timeline is not None:
            if isinstance(timeline, bool) or not isinstance(timeline, int):
                raise ValueError("preferences.timeline_weeks must be an integer")
            if timeline < 1 or timeline > 104:
                raise ValueError("preferences.timeline_weeks must be between 1 and 104")

        for key in ["resume_profile", "combined_profile", "profile_overrides", "resume_parse_summary"]:
            if key in value and value.get(key) is not None and not isinstance(value.get(key), dict):
                raise ValueError(f"preferences.{key} must be an object")

        for key in ["stack_preferences", "tool_preferences"]:
            if key in value and value.get(key) is not None and not isinstance(value.get(key), list):
                raise ValueError(f"preferences.{key} must be a list")

        return value


class CoachingJobParseRequest(BaseModel):
    workspace_id: str
    submission_id: str
    force_refresh: bool = False


class CoachingRecommendStackToolsRequest(BaseModel):
    workspace_id: str
    submission_id: str | None = None
    job_links: list[str | CoachingJobLinkInput] = Field(default_factory=list)


class CoachingGenerateSowRequest(BaseModel):
    workspace_id: str
    submission_id: str
    parsed_jobs: list[dict] | None = None
    regenerate_with_improvements: bool = False


class CoachingValidateLoopRequest(BaseModel):
    workspace_id: str
    submission_id: str
    sow: dict
    auto_revise_once: bool = True


class CoachingSowValidateRequest(BaseModel):
    workspace_id: str
    submission_id: str
    sow: CoachingSowDraft


class CoachingResourceMatchRequest(BaseModel):
    workspace_id: str
    sow: CoachingSowDraft


class CoachingDemoSeedRequest(BaseModel):
    workspace_id: str
    applicant_name: str = "Demo Candidate"


class ResumeUploadValidationRequest(BaseModel):
    workspace_id: str
    filename: str
    content_type: str | None = None
    size_bytes: int


class CoachingSubscriptionSyncRequest(BaseModel):
    workspace_id: str
    provider: str = "squarespace"
    event_type: str = "subscription.updated"
    email: str
    username: str | None = None
    plan_tier: str = "coaching-core"
    subscription_status: str
    renewal_date: str | None = None
    provider_customer_id: str | None = None
    provider_subscription_id: str | None = None
    webhook_signature: str | None = None
    webhook_timestamp: int | None = None
    raw_event: dict | None = None


def _verify_subscription_webhook_signature(req: CoachingSubscriptionSyncRequest):
    provider = str(req.provider or "generic").strip().lower()
    provider_secret = str(os.getenv(f"WEBHOOK_SECRET_{provider.upper().replace('-', '_')}") or "").strip()
    shared_secret = str(os.getenv("COACHING_WEBHOOK_SECRET") or "").strip()
    if not (provider_secret or shared_secret):
        return type("_Result", (), {"valid": True, "reason": "not_configured"})()

    payload_json = req.model_dump(mode="json", exclude={"webhook_signature", "webhook_timestamp"})
    body_bytes = json.dumps(payload_json, separators=(",", ":"), sort_keys=True).encode("utf-8")

    headers: dict[str, str] = {}
    if req.webhook_timestamp is not None:
        headers["x-webhook-timestamp"] = str(req.webhook_timestamp)
    if req.webhook_signature:
        headers["x-webhook-signature"] = str(req.webhook_signature)

    return verify_webhook_signature(provider=provider, body_bytes=body_bytes, headers=headers)


def _record_invalid_webhook_signature_attempt(*, provider: str, source_ip: str, route: str, reason: str, actor: str | None = None, role: str | None = None) -> None:
    threshold = max(1, int(os.getenv("WEBHOOK_INVALID_SIG_ALERT_THRESHOLD", "5") or 5))
    window_seconds = max(1, int(os.getenv("WEBHOOK_INVALID_SIG_ALERT_WINDOW_SECONDS", "300") or 300))
    triggered, attempt_count = INVALID_WEBHOOK_SIGNATURE_TRACKER.record_attempt(
        provider=provider,
        source_ip=source_ip,
        route=route,
        threshold=threshold,
        window_seconds=window_seconds,
    )
    if not triggered:
        return

    event = InvalidSignatureAlertEvent(
        provider=provider,
        source_ip=source_ip,
        route=route,
        reason=reason,
        attempt_count=attempt_count,
        threshold=threshold,
        window_seconds=window_seconds,
        actor=actor,
        role=role,
        created_at=int(time.time()),
    )
    alert_payload = INVALID_WEBHOOK_SIGNATURE_TRACKER.record_alert(event)
    routed = dispatch_invalid_webhook_signature_alert(alert_payload)
    logger.error(
        "coaching_webhook_invalid_signature_alert",
        extra={**alert_payload, "routed": routed},
    )


def _derive_subscription_event_id(*, raw_event: dict[str, Any] | None, provider: str, workspace_id: str, email: str, event_type: str, status: str) -> tuple[str, bool]:
    incoming_event_id = str((raw_event or {}).get("id") or "").strip()
    if incoming_event_id:
        return incoming_event_id, False

    digest_payload = {
        "provider": str(provider or "").strip().lower(),
        "workspace_id": str(workspace_id or "").strip(),
        "email": str(email or "").strip().lower(),
        "event_type": str(event_type or "").strip(),
        "status": _normalize_subscription_status(status),
        "raw_event": raw_event or {},
    }
    digest = hashlib.sha256(json.dumps(digest_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()[:24]
    return f"derived_{digest}", True


def _normalize_subscription_status(status: str) -> str:
    s = (status or "").strip().lower()
    if s in {"active", "trialing", "paid", "current"}:
        return "active"
    if s in {"past_due", "past-due", "incomplete", "unpaid"}:
        return "past_due"
    if s in {"canceled", "cancelled", "expired", "inactive", "ended"}:
        return "inactive"
    return s or "unknown"


def _is_active_subscription(status: str) -> bool:
    return _normalize_subscription_status(status) == "active"


def _require_active_subscription(
    *,
    workspace_id: str,
    session,
    member_email: str | None = None,
) -> None:
    account = get_coaching_account_subscription(
        workspace_id=workspace_id,
        username=session.username,
        email=member_email,
    )
    status = _normalize_subscription_status(str((account or {}).get("subscription_status") or ""))
    can_access = bool(account) and _is_active_subscription(status)
    if can_access:
        return

    logger.warning(
        "coaching_subscription_access_denied",
        extra={
            "actor": session.username,
            "role": session.role,
            "payload": pii_safe_subscription_log_payload(
                workspace_id=workspace_id,
                member_email=member_email or "",
                subscription_status=status,
                plan_tier=str((account or {}).get("plan_tier") or "unknown"),
                launch_token=None,
                can_access=False,
            ),
        },
    )
    raise HTTPException(status_code=403, detail="Active coaching subscription required")


class CoachingSubscriptionStatusRequest(BaseModel):
    workspace_id: str
    member_email: str
    subscription_status: str = "active"
    plan_tier: str = "core"
    launch_token: str | None = None


class CoachingSowExportRequest(BaseModel):
    workspace_id: str
    submission_id: str
    sow: CoachingSowDraft
    format: str = "markdown"  # markdown | json


class CoachingReviewStatusUpdateRequest(BaseModel):
    workspace_id: str
    submission_id: str
    coach_review_status: str
    coach_notes: str | None = None


class CoachingReviewApproveSendRequest(BaseModel):
    workspace_id: str
    submission_id: str
    coach_notes: str | None = None


class CoachingLaunchTokenVerifyRequest(BaseModel):
    workspace_id: str
    submission_id: str
    launch_token: str


class CoachingFeedbackCaptureRequest(BaseModel):
    workspace_id: str
    submission_id: str
    run_id: str | None = None
    review_tags: list[str] = Field(default_factory=list, max_length=25)
    coach_notes: str | None = Field(default=None, max_length=2000)
    regeneration_hints: list[str] = Field(default_factory=list, max_length=20)


class CoachingMentoringIntentRequest(BaseModel):
    workspace_id: str
    submission_id: str
    intent_type: str = "mentoring_intent"  # mentoring_intent | cta_click
    cta_context: str | None = None


class CoachingBatchReviewStatusUpdateRequest(BaseModel):
    workspace_id: str
    submission_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)
    coach_review_status: str
    coach_notes: str | None = None


class CoachingBatchRegenerateRequest(BaseModel):
    workspace_id: str
    submission_ids: list[str] = Field(default_factory=list, min_length=1, max_length=50)
    parsed_jobs: list[dict] = Field(default_factory=list)
    regenerate_with_improvements: bool = True


def _require_active_coaching_subscription(workspace_id: str, session: Session, email: str | None = None) -> dict:
    account = get_coaching_account_subscription(
        workspace_id=workspace_id,
        username=session.username,
        email=email,
    )
    if not account:
        raise HTTPException(
            status_code=403,
            detail={"code": "subscription_required", "subscription_required": True, "message": "Active coaching subscription required."},
        )

    status = _normalize_subscription_status(str(account.get("subscription_status") or ""))
    if not _is_active_subscription(status):
        raise HTTPException(
            status_code=403,
            detail={"code": "subscription_required", "subscription_required": True, "message": "Active coaching subscription required."},
        )
    return account


def _require_coaching_session(authorization: str | None) -> Session:
    return get_current_session(authorization)


def _require_coaching_role(session: Session, allowed_roles: set[str]) -> None:
    assert_role(session, allowed_roles)


def _require_coaching_subscription(*, workspace_id: str, session: Session, email: str | None = None) -> dict:
    return _require_active_coaching_subscription(workspace_id=workspace_id, session=session, email=email)


def _persist_review_state_with_retry(
    *,
    submission_id: str,
    coach_review_status: str,
    coach_notes: str | None,
    max_attempts: int = 3,
    backoff_sec: float = 0.15,
) -> dict[str, Any]:
    normalized_notes = coach_notes or ""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            update_coaching_review_status(
                submission_id=submission_id,
                coach_review_status=coach_review_status,
                coach_notes=normalized_notes,
            )
            persisted = get_coaching_intake_submission(submission_id)
            persisted_status = str((persisted or {}).get("coach_review_status") or "")
            persisted_notes = str((persisted or {}).get("coach_notes") or "")
            if persisted and persisted_status == coach_review_status and persisted_notes == normalized_notes:
                return {
                    "ok": True,
                    "submission": persisted,
                    "attempts": attempt,
                }
            last_error = RuntimeError("review state consistency check failed")
        except Exception as exc:
            last_error = exc

        if attempt < max_attempts:
            time.sleep(backoff_sec * attempt)

    return {
        "ok": False,
        "submission": get_coaching_intake_submission(submission_id),
        "attempts": max_attempts,
        "error": str(last_error) if last_error else "review state update failed",
    }


def _check_llm_provider_reachability(base_url: str, api_key: str, timeout_sec: int = 4) -> tuple[bool, str]:
    if not api_key:
        return False, "api_key_missing"
    try:
        req = urlrequest.Request(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urlrequest.urlopen(req, timeout=timeout_sec) as resp:
            code = int(getattr(resp, "status", 200))
            return 200 <= code < 300, f"HTTP {code}"
    except HTTPError as e:
        return False, f"HTTPError {e.code}"
    except URLError as e:
        return False, f"URLError {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def _safe_export_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or "coaching-sow"


def _xml_escape_text(value: str) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _docx_paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t xml:space=\"preserve\">{_xml_escape_text(text)}</w:t></w:r></w:p>"


def _render_sow_markdown(sow: dict[str, Any]) -> str:
    milestones = sow.get("milestones") or []
    milestone_lines = "\n".join([f"- **{m.get('name', 'Milestone')}** ({m.get('duration_weeks', '?')}w): {', '.join(m.get('deliverables') or [])}" for m in milestones])
    interview = sow.get("interview_ready_package") or {}
    star_lines = "\n".join([f"- {x}" for x in (interview.get("star_bullets") or [])])
    checklist_lines = "\n".join([f"- [ ] {x}" for x in (interview.get("portfolio_checklist") or [])])
    recruiter_mapping = json.dumps(interview.get("recruiter_mapping") or {}, indent=2)
    return "\n".join(
        [
            f"# {sow.get('project_title', 'Coaching SOW')}",
            "",
            "## Business Outcome",
            str((sow.get("business_outcome") or {}).get("problem_statement") or ""),
            "",
            "## Milestones",
            milestone_lines or "- None",
            "",
            "## Interview-ready STAR Bullets",
            star_lines or "- None",
            "",
            "## Portfolio Checklist",
            checklist_lines or "- [ ] None",
            "",
            "## Recruiter Mapping",
            recruiter_mapping,
            "",
            "## Architecture",
            json.dumps((sow.get("solution_architecture") or {}).get("medallion_plan") or {}, indent=2),
        ]
    )


def _render_sow_docx_bytes(sow: dict[str, Any]) -> bytes:
    paragraphs = [_docx_paragraph(line if line.strip() else " ") for line in _render_sow_markdown(sow).splitlines()]
    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>"
        f"{''.join(paragraphs)}"
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr>"
        "</w:body>"
        "</w:document>"
    )
    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )
    rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def _launch_token_secret() -> str:
    return str(os.getenv("COACHING_LAUNCH_TOKEN_SECRET") or os.getenv("JWT_SECRET") or "dev-coaching-launch-secret")


def _mint_launch_token(*, workspace_id: str, submission_id: str, email: str | None = None) -> str:
    payload = {
        "workspace_id": workspace_id,
        "submission_id": submission_id,
        "email": str(email or "").strip().lower(),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_launch_token_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    encoded = base64.urlsafe_b64encode(body.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{encoded}.{sig}"


def _verify_launch_token(*, workspace_id: str, submission_id: str, token: str) -> dict[str, Any]:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return {"valid": False, "reason": "invalid_format"}
    encoded, sig = raw.rsplit(".", 1)
    try:
        padded = encoded + ("=" * ((4 - len(encoded) % 4) % 4))
        body = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        expected = hmac.new(_launch_token_secret().encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return {"valid": False, "reason": "invalid_signature"}
        payload = json.loads(body)
    except Exception:
        return {"valid": False, "reason": "decode_error"}

    if str(payload.get("workspace_id") or "") != str(workspace_id or ""):
        return {"valid": False, "reason": "workspace_mismatch"}
    if str(payload.get("submission_id") or "") != str(submission_id or ""):
        return {"valid": False, "reason": "submission_mismatch"}
    return {"valid": True, "payload": payload}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    lb_ok, lb_msg = lakebase_health()
    uc_ok, uc_msg = uc_health()

    return {
        "status": "ok",
        "connectors": {
            "lakebase": {"ok": lb_ok, "message": lb_msg},
            "unity_catalog": {"ok": uc_ok, "message": uc_msg},
        },
    }


@app.get("/coaching/health/llm-readiness")
def coaching_llm_readiness(session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    api_key = str(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    base_url = str(os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    provider_ok, provider_message = _check_llm_provider_reachability(base_url=base_url, api_key=api_key)
    ready = bool(api_key) and provider_ok
    return {
        "ok": True,
        "readiness": {
            "ready": ready,
            "api_key_present": bool(api_key),
            "provider_reachable": provider_ok,
            "provider_message": provider_message,
            "base_url": base_url,
        },
    }


@app.post("/auth/login")
def auth_login(req: LoginRequest, request: Request) -> dict:
    _apply_rate_limit(policy_name="auth", request=request)
    user = get_user_auth(req.username, req.password)

    # Local-safe fallback when backend is pointed to unconfigured Postgres.
    if (not user) and (not lakebase_is_configured()):
        if req.username == "admin" and req.password == "admin123":
            token = issue_token("admin", "admin")
            logger.info(
                "auth_login_completed",
                extra={
                    "event": "auth_login_completed",
                    "payload": pii_safe_auth_log_payload(username=req.username, success=True, role="admin", used_fallback=True),
                },
            )
            return {"ok": True, "token": token, "username": "admin", "role": "admin", "fallback": True}

    if not user:
        logger.info(
            "auth_login_completed",
            extra={
                "event": "auth_login_completed",
                "payload": pii_safe_auth_log_payload(username=req.username, success=False, role=None, used_fallback=False),
            },
        )
        if not lakebase_is_configured():
            return {"ok": False, "message": "Invalid credentials (backend not configured: set LAKEBASE_BACKEND=duckdb for local dev or configure Postgres)"}
        return {"ok": False, "message": "Invalid credentials"}
    token = issue_token(user["username"], user["role"])
    logger.info(
        "auth_login_completed",
        extra={
            "event": "auth_login_completed",
            "payload": pii_safe_auth_log_payload(username=user["username"], success=True, role=user["role"], used_fallback=False),
        },
    )
    return {"ok": True, "token": token, "username": user["username"], "role": user["role"]}


@app.get("/auth/me")
def auth_me(request: Request, authorization: str | None = Header(default=None)) -> dict:
    _apply_rate_limit(policy_name="auth", request=request)
    return whoami(authorization)


@app.post("/auth/refresh")
def auth_refresh(request: Request, session=Depends(get_current_session)) -> dict:
    _apply_rate_limit(policy_name="auth", request=request)
    token = issue_token(session.username, session.role)
    logger.info(
        "auth_refresh_completed",
        extra={
            "event": "auth_refresh_completed",
            "payload": pii_safe_auth_log_payload(username=session.username, success=True, role=session.role, used_fallback=False),
        },
    )
    return {"ok": True, "token": token, "username": session.username, "role": session.role}


@app.post("/auth/logout")
def auth_logout(request: Request, authorization: str | None = Header(default=None)) -> dict:
    _apply_rate_limit(policy_name="auth", request=request)
    return revoke_token(authorization)


@app.get("/auth/session-stats")
def auth_session_stats(session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    return session_stats()


@app.post("/coaching/subscription/status")
def coaching_subscription_status(req: CoachingSubscriptionStatusRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=req.workspace_id)
    normalized_status = str(req.subscription_status or "").strip().lower()
    can_access = normalized_status in {"active", "trialing"}
    logger.info(
        "coaching_subscription_status_checked",
        extra={
            "event": "coaching_subscription_status_checked",
            "payload": pii_safe_subscription_log_payload(
                workspace_id=req.workspace_id,
                member_email=req.member_email,
                subscription_status=normalized_status,
                plan_tier=req.plan_tier,
                launch_token=req.launch_token,
                can_access=can_access,
            ),
        },
    )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "member": {"email_present": bool(str(req.member_email or "").strip())},
        "subscription": {"status": normalized_status, "plan_tier": req.plan_tier},
        "can_access": can_access,
    }


@app.post("/validate/deterministic", response_model=ValidationResult)
def validate_deterministic(ast: CanvasAST, user: str = Depends(get_current_user)) -> ValidationResult:
    return run_deterministic_validation(ast, actor_user=user)


@app.post("/validate/probabilistic", response_model=ValidationResult)
def validate_probabilistic(ast: CanvasAST, user: str = Depends(get_current_user)) -> ValidationResult:
    return run_probabilistic_validation(ast, actor_user=user)


@app.post("/impact/deterministic", response_model=ImpactResult)
def impact_deterministic(ast: CanvasAST, user: str = Depends(get_current_user)) -> ImpactResult:
    return run_deterministic_impact(ast, actor_user=user)


@app.post("/impact/probabilistic", response_model=ImpactResult)
def impact_probabilistic(ast: CanvasAST, user: str = Depends(get_current_user)) -> ImpactResult:
    return run_probabilistic_impact(ast, actor_user=user)


@app.get("/admin/bootstrap-status")
def admin_bootstrap_status() -> dict:
    return {
        "status": "ok",
        "lakebase": lakebase_bootstrap_status(),
    }


@app.get("/git/status")
def get_git_status(workspace_id: str, user: str = Depends(get_current_user)) -> dict:
    _ = user
    return git_status(workspace_id)


@app.post("/git/config")
def post_git_config(req: GitConfigRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    return set_git_config(
        workspace_id=req.workspace_id,
        repo_path=req.repo_path,
        branch=req.branch,
        remote=req.remote,
        actor_user=session.username,
    )


@app.post("/git/push-ast")
def post_git_push_ast(req: GitPushAstRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    return save_and_push_ast(
        ast_payload=req.ast.model_dump(mode="json", by_alias=True),
        workspace_id=req.ast.workspace_id,
        commit_message=req.commit_message,
        push=req.push,
    )


@app.get("/connections/templates")
def get_connection_templates(user: str = Depends(get_current_user)) -> dict:
    _ = user
    return {
        "templates": {
            "databricks_uc": {
                "profile_name": "customer-default",
                "host": "",
                "token": "",
                "warehouse_id": "",
                "http_path": "",
                "connection_string": "",
                "catalog": "",
                "schema": "",
                "lineage_mode": "unity_catalog",
            },
            "information_schema": {
                "engine": "postgres",
                "host": "",
                "port": 5432,
                "database": "",
                "username": "",
                "password": "",
                "schema": "public",
            },
            "git": {
                "repo_path": "",
                "branch": "main",
                "remote": "origin",
                "ast_subdir": "ast",
            },
            "power_bi": {
                "tenant_id": "",
                "client_id": "",
                "client_secret": "",
                "workspace_id": "",
                "dataset_ids": [],
                "report_ids": [],
                "mapping_mode": "dataset_lineage",
            },
        }
    }


@app.get("/connections/settings")
def get_connections_settings(workspace_id: str, connection_type: str | None = None, user: str = Depends(get_current_user)) -> dict:
    _ = user
    rows = get_connection_settings(workspace_id, connection_type)
    for r in rows:
        payload = r.get("settings_json")
        parsed = json.loads(payload) if isinstance(payload, str) else (payload or {})
        r["settings_json"] = _redact_settings(str(r.get("connection_type") or ""), parsed)
    return {"workspace_id": workspace_id, "connections": rows}


@app.post("/coaching/intake/resume/validate")
def coaching_resume_validate(req: ResumeUploadValidationRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=req.workspace_id)
    try:
        result = validate_resume_metadata(
            filename=req.filename,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            max_size_bytes=DEFAULT_MAX_RESUME_BYTES,
        )
        safe_path = build_safe_resume_path(
            base_dir=Path(__file__).resolve().parents[2] / "storage" / "coaching" / "resumes",
            workspace_id=req.workspace_id,
            filename=req.filename,
        )
        safe_result = dict(result)
        safe_result["filename"] = mask_secrets_in_text(str(safe_result.get("filename") or ""))
        return {
            "ok": True,
            "workspace_id": req.workspace_id,
            "validation": safe_result,
            "safe_storage_path": mask_secrets_in_text(str(safe_path)),
        }
    except FileValidationError as e:
        return {"ok": False, "workspace_id": req.workspace_id, "message": mask_secrets_in_text(str(e))}


@app.post("/coaching/intake/resume/upload")
async def coaching_resume_upload(
    workspace_id: str = Form(...),
    submission_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    session=Depends(get_current_session),
) -> dict:
    assert_role(session, {"admin", "editor"})

    data = await file.read()
    filename = str(file.filename or "resume.txt")
    try:
        validation = validate_resume_metadata(
            filename=filename,
            content_type=file.content_type,
            size_bytes=len(data),
            max_size_bytes=DEFAULT_MAX_RESUME_BYTES,
        )
    except FileValidationError as e:
        return {"ok": False, "workspace_id": workspace_id, "message": mask_secrets_in_text(str(e))}

    resume_text, strategy = _extract_resume_text(filename, data)
    parsed_summary = extract_resume_signals(resume_text)
    parsed_summary.update({"filename": mask_secrets_in_text(filename), "parse_strategy": strategy})
    if not str(resume_text or "").strip():
        parsed_summary["fallback_used"] = True
        parsed_summary["parse_warning"] = "Could not reliably extract text; provide pasted resume_text fallback in intake."
    else:
        parsed_summary["fallback_used"] = False

    if submission_id:
        intake = get_coaching_intake_submission(submission_id)
        if intake and str(intake.get("workspace_id") or "") == str(workspace_id):
            merged_preferences = dict(intake.get("preferences_json") or {})
            merged_preferences["resume_parse_summary"] = parsed_summary
            update_coaching_intake_preferences(submission_id=submission_id, preferences=merged_preferences)

    return {
        "ok": True,
        "workspace_id": workspace_id,
        "submission_id": submission_id,
        "validation": validation,
        "resume_text": str(resume_text or "")[:12000],
        "resume_parse_summary": parsed_summary,
    }


@app.post("/connections/settings")
def post_connections_settings(req: ConnectionSettingsRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    upsert_connection_settings(
        workspace_id=req.workspace_id,
        connection_type=req.connection_type,
        settings_payload=req.settings,
        updated_by=session.username,
    )
    return {"ok": True, "workspace_id": req.workspace_id, "connection_type": req.connection_type}


@app.post("/connections/validate/databricks-uc")
def validate_databricks_uc(req: DatabricksConnectionValidateRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    s = req.settings or {}
    has_conn_str = bool(str(s.get("connection_string") or "").strip())
    has_fields = bool(str(s.get("host") or "").strip()) and bool(str(s.get("token") or "").strip())
    if not (has_conn_str or has_fields):
        return {"ok": False, "message": "Provide either connection_string OR host+token.", "workspace_id": req.workspace_id}

    host = str(s.get("host") or "").strip()
    token = str(s.get("token") or "").strip()
    conn_str_preview = str(s.get("connection_string") or "").strip()
    if conn_str_preview and "token=" in conn_str_preview.lower():
        conn_str_preview = conn_str_preview.split("token=")[0] + "token=***"

    live_test = {"attempted": False, "ok": None, "message": "not requested"}
    if req.run_live_test and host and token:
        live_test["attempted"] = True
        url = host.rstrip("/") + "/api/2.0/clusters/list"
        http_req = urlrequest.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urlrequest.urlopen(http_req, timeout=6) as resp:
                code = getattr(resp, "status", 200)
                live_test["ok"] = 200 <= int(code) < 300
                live_test["message"] = f"HTTP {code}"
        except HTTPError as e:
            live_test["ok"] = False
            live_test["message"] = f"HTTPError {e.code}"
        except URLError as e:
            live_test["ok"] = False
            live_test["message"] = f"URLError {e.reason}"
        except Exception as e:
            live_test["ok"] = False
            live_test["message"] = f"Error: {e}"

    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "message": "Databricks UC connection settings look structurally valid.",
        "mode": "connection_string" if has_conn_str else "host_token",
        "host": host,
        "connection_string_preview": conn_str_preview,
        "live_test": live_test,
    }


@app.post("/connections/databricks/schemas")
def list_databricks_schemas(req: DatabricksSchemasRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})

    conn_payload = req.settings or {}
    if not conn_payload:
        rows = get_connection_settings(req.workspace_id, "databricks_uc")
        if not rows:
            return {"ok": False, "message": f"No Databricks connection found for workspace '{req.workspace_id}'", "workspace_id": req.workspace_id}
        conn_payload = rows[0].get("settings_json") or {}
        if isinstance(conn_payload, str):
            conn_payload = json.loads(conn_payload)

    try:
        schemas = fetch_schemas(conn_payload)
        return {"ok": True, "workspace_id": req.workspace_id, "schemas": schemas}
    except Exception as e:
        return {"ok": False, "workspace_id": req.workspace_id, "message": str(e), "schemas": []}


@app.post("/connections/sync/databricks-schema")
def sync_databricks_schema(req: DatabricksSchemaSyncRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})

    conn_payload = req.settings or {}
    if not conn_payload:
        rows = get_connection_settings(req.workspace_id, "databricks_uc")
        if not rows:
            return {"ok": False, "message": f"No Databricks connection found for workspace '{req.workspace_id}'", "workspace_id": req.workspace_id}
        conn_payload = rows[0].get("settings_json") or {}
        if isinstance(conn_payload, str):
            conn_payload = json.loads(conn_payload)

    try:
        meta = fetch_information_schema(
            conn_payload,
            limit_tables=req.limit_tables,
            limit_columns=req.limit_columns,
        )
    except Exception as e:
        return {"ok": False, "message": str(e), "workspace_id": req.workspace_id}

    tables = meta.get("tables", [])
    columns = meta.get("columns", [])

    columns_by_table: dict[str, list[dict]] = {}
    for c in columns:
        key = f"{c.get('table_catalog')}.{c.get('table_schema')}.{c.get('table_name')}"
        columns_by_table.setdefault(key, []).append(c)

    ast_tables: list[dict] = []
    x = 80
    y = 80
    for i, t in enumerate(tables):
        key = f"{t.get('table_catalog')}.{t.get('table_schema')}.{t.get('table_name')}"
        col_defs = []
        for c in columns_by_table.get(key, []):
            col_defs.append(
                {
                    "name": str(c.get("column_name") or ""),
                    "data_type": _to_canvas_data_type(str(c.get("data_type") or "string")),
                    "nullable": str(c.get("is_nullable") or "YES").upper() == "YES",
                    "is_primary_key": False,
                }
            )

        if not col_defs:
            col_defs = [{"name": "id", "data_type": "string", "nullable": False, "is_primary_key": True}]

        ast_tables.append(
            {
                "id": f"{t.get('table_schema')}.{t.get('table_name')}",
                "catalog": str(t.get("table_catalog") or ""),
                "schema": str(t.get("table_schema") or "default"),
                "table": str(t.get("table_name") or "unknown"),
                "description": None,
                "columns": col_defs,
                "position": {"x": x + (i % 4) * 320, "y": y + (i // 4) * 220},
                "source": "unity_catalog",
            }
        )

    ast_payload = {
        "version": "1.0",
        "workspace_id": req.workspace_id,
        "tables": ast_tables,
        "relationships": [],
        "modified_table_ids": [t["id"] for t in ast_tables[:1]],
    }

    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "table_count": len(ast_tables),
        "column_count": len(columns),
        "ast": ast_payload,
    }


@app.post("/impact/mappings")
def post_dependency_mapping(req: DependencyMappingRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    save_dependency_mapping(
        workspace_id=req.workspace_id,
        source_object=req.source_object,
        target_object=req.target_object,
        dependency_type=req.dependency_type,
        confidence=req.confidence,
        source_system=req.source_system,
        notes=req.notes,
        updated_by=session.username,
    )
    return {"ok": True}


@app.get("/standards/templates")
def standards_templates(user: str = Depends(get_current_user)) -> dict:
    _ = user
    root = Path(__file__).resolve().parents[2] / "docs" / "templates"
    payload: dict[str, dict] = {}
    for name in ["standards_template_basic.json", "regulatory_template_basic.json"]:
        p = root / name
        if p.exists():
            payload[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return {"templates": payload}


@app.post("/standards/documents")
def post_standards_document(req: PolicyUploadRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    doc_id = str(uuid4())
    save_policy_document(
        document_id=doc_id,
        workspace_id=req.workspace_id,
        doc_name=req.doc_name,
        doc_type=req.doc_type,
        content_text=req.content_text,
        uploaded_by=session.username,
    )

    chunks = _chunk_text(req.content_text)
    save_policy_chunks(
        document_id=doc_id,
        workspace_id=req.workspace_id,
        chunks=[
            {
                "chunk_id": str(uuid4()),
                "chunk_index": i,
                "chunk_text": text,
                "source_ref": f"{req.doc_name}#chunk-{i}",
            }
            for i, text in enumerate(chunks)
        ],
    )

    return {"ok": True, "document_id": doc_id, "chunk_count": len(chunks)}


@app.get("/standards/documents")
def get_standards_documents(workspace_id: str, user: str = Depends(get_current_user)) -> dict:
    _ = user
    return {"workspace_id": workspace_id, "documents": list_policy_documents(workspace_id)}


@app.post("/standards/policy-config")
def post_policy_config(req: PolicyConfigRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    upsert_workspace_policy_config(
        workspace_id=req.workspace_id,
        standards_template_name=req.standards_template_name,
        standards_template_version=req.standards_template_version,
        regulatory_template_name=req.regulatory_template_name,
        regulatory_template_version=req.regulatory_template_version,
        updated_by=session.username,
    )
    return {"ok": True, "workspace_id": req.workspace_id}


@app.get("/standards/policy-config")
def get_policy_config(workspace_id: str, user: str = Depends(get_current_user)) -> dict:
    _ = user
    return {"workspace_id": workspace_id, "config": get_workspace_policy_config(workspace_id)}


@app.post("/standards/finding-status")
def post_finding_status(req: FindingStatusRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    upsert_finding_status(
        workspace_id=req.workspace_id,
        finding_key=req.finding_key,
        status=req.status,
        note=req.note,
        updated_by=session.username,
    )
    return {"ok": True}


@app.post("/standards/finding-status/bulk")
def post_finding_status_bulk(req: FindingBulkStatusRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    for key in req.finding_keys:
        upsert_finding_status(
            workspace_id=req.workspace_id,
            finding_key=key,
            status=req.status,
            note=req.note,
            updated_by=session.username,
        )
    return {"ok": True, "updated": len(req.finding_keys)}


@app.get("/standards/finding-status")
def get_finding_status(workspace_id: str, user: str = Depends(get_current_user)) -> dict:
    _ = user
    return {"workspace_id": workspace_id, "statuses": get_finding_statuses(workspace_id)}


@app.get("/standards/finding-status/audit")
def get_finding_status_audit_route(
    workspace_id: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    updated_by: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user: str = Depends(get_current_user),
) -> dict:
    _ = user
    result = get_finding_status_audit(
        workspace_id,
        page=page,
        page_size=page_size,
        status=status,
        updated_by=updated_by,
        date_from=date_from,
        date_to=date_to,
    )
    return {"workspace_id": workspace_id, "audit": result.get("rows", []), "meta": {k: v for k, v in result.items() if k != "rows"}}


@app.post("/standards/evaluate")
def standards_evaluate(ast: CanvasAST, session=Depends(get_current_session)) -> dict:
    results: list[dict] = []

    templates_root = Path(__file__).resolve().parents[2] / "docs" / "templates"
    standards_template = {}
    regulatory_template = {}
    standards_path = templates_root / "standards_template_basic.json"
    regulatory_path = templates_root / "regulatory_template_basic.json"
    if standards_path.exists():
        standards_template = json.loads(standards_path.read_text(encoding="utf-8"))
    if regulatory_path.exists():
        regulatory_template = json.loads(regulatory_path.read_text(encoding="utf-8"))

    docs = list_policy_documents(ast.workspace_id)
    require_table_desc = bool(
        standards_template.get("sections", {}).get("documentation", {}).get("require_table_description", False)
    )
    require_col_desc = bool(
        standards_template.get("sections", {}).get("documentation", {}).get("require_column_description", False)
    )
    forbid_generic = {
        str(v).lower()
        for v in standards_template.get("sections", {}).get("quality", {}).get("forbid_generic_column_names", [])
    }
    pii_terms = {
        str(v).lower()
        for v in regulatory_template.get("sections", {}).get("pii_controls", {}).get("masking_required_for", ["ssn", "dob", "email", "phone"])
    }

    for d in docs:
        name = str(d.get("doc_name") or "").lower()
        if "standard" in name:
            require_table_desc = True
        if "regulatory" in name:
            pii_terms = pii_terms or {"ssn", "dob", "email", "phone"}

    statuses = get_finding_statuses(ast.workspace_id)

    for table in ast.tables:
        hits = search_policy_chunks(ast.workspace_id, table.table, limit=3)
        for h in hits:
            results.append({
                "table": table.table,
                "finding": f"Policy mention found for table '{table.table}'",
                "source_ref": h.get("source_ref") or f"chunk:{h.get('chunk_index')}",
                "document_id": h.get("document_id"),
                "excerpt": str(h.get("chunk_text") or "")[:180],
                "severity": "LOW",
            })

        if require_table_desc and not (table.description or "").strip():
            results.append({
                "table": table.table,
                "finding": "Table description required by standards template.",
                "source_ref": "standards_template_basic.sections.documentation.require_table_description",
                "document_id": None,
                "excerpt": "",
                "severity": "MED",
            })

        for col in table.columns:
            c_name = col.name.lower()
            if require_col_desc and not (col.description or "").strip():
                results.append({
                    "table": table.table,
                    "finding": f"Column '{col.name}' description required by standards template.",
                    "source_ref": "standards_template_basic.sections.documentation.require_column_description",
                    "document_id": None,
                    "excerpt": "",
                    "severity": "LOW",
                })
            if c_name in forbid_generic:
                results.append({
                    "table": table.table,
                    "finding": f"Generic column name '{col.name}' is forbidden by standards template.",
                    "source_ref": "standards_template_basic.sections.quality.forbid_generic_column_names",
                    "document_id": None,
                    "excerpt": "",
                    "severity": "MED",
                })
            if any(term in c_name for term in pii_terms):
                results.append({
                    "table": table.table,
                    "finding": f"Potential PII column '{col.name}' requires masking/tokenization review.",
                    "source_ref": "regulatory_template_basic.sections.pii_controls.masking_required_for",
                    "document_id": None,
                    "excerpt": "",
                    "severity": "HIGH",
                })

    for r in results:
        key = f"{r.get('table','')}|{r.get('source_ref','')}|{r.get('finding','')}"
        r["finding_key"] = key
        st = statuses.get(key)
        r["status"] = (st or {}).get("status", "open")
        r["status_note"] = (st or {}).get("note")

    return {"workspace_id": ast.workspace_id, "findings": results}


@app.get("/runs/history")
def runs_history(workspace_id: str, limit: int = 50, user: str = Depends(get_current_user)) -> dict:
    _ = user
    return {"workspace_id": workspace_id, "runs": get_run_history(workspace_id, limit=limit)}


@app.get("/demo/readiness")
def demo_readiness(workspace_id: str, user: str = Depends(get_current_user)) -> dict:
    _ = user

    connections = get_connection_settings(workspace_id)
    conn_types = {str(c.get("connection_type") or "") for c in connections}
    has_databricks = "databricks_uc" in conn_types

    docs = list_policy_documents(workspace_id)
    runs = get_run_history(workspace_id, limit=200)

    validation_runs = [r for r in runs if str(r.get("run_type")) == "validation"]
    impact_runs = [r for r in runs if str(r.get("run_type")) == "impact"]

    blockers: list[str] = []
    if not has_databricks:
        blockers.append("Databricks connection not configured for workspace")
    if len(docs) == 0:
        blockers.append("No standards/regulatory documents uploaded")
    if len(validation_runs) == 0:
        blockers.append("No validation run history found")
    if len(impact_runs) == 0:
        blockers.append("No impact run history found")

    return {
        "workspace_id": workspace_id,
        "ready": len(blockers) == 0,
        "summary": {
            "connections_configured": len(connections),
            "connection_types": sorted([c for c in conn_types if c]),
            "databricks_configured": has_databricks,
            "policy_documents": len(docs),
            "validation_runs": len(validation_runs),
            "impact_runs": len(impact_runs),
            "total_runs": len(runs),
        },
        "blockers": blockers,
    }


@app.post("/reports/pr-summary")
def pr_summary(ast: CanvasAST, session=Depends(get_current_session)) -> dict:
    eval_res = standards_evaluate(ast, session=session)
    findings = eval_res.get("findings", [])
    by_sev = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        sev = str(f.get("severity") or "LOW")
        if sev in by_sev:
            by_sev[sev] += 1

    summary_lines = [
        f"### ERD Governance Check ({ast.workspace_id})",
        f"- Findings: {len(findings)} (HIGH: {by_sev['HIGH']}, MED: {by_sev['MED']}, LOW: {by_sev['LOW']})",
        f"- Run history entries: {len(get_run_history(ast.workspace_id, limit=20))}",
        "- Top findings:",
    ]
    for f in findings[:5]:
        summary_lines.append(f"  - [{f.get('severity','LOW')}] {f.get('table')}: {f.get('finding')}")

    return {"workspace_id": ast.workspace_id, "markdown": "\n".join(summary_lines), "findings": findings[:20]}


@app.post("/reports/pr-webhook")
def pr_webhook(req: PrWebhookRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    body = json.dumps({"text": req.markdown}).encode("utf-8")
    http_req = urlrequest.Request(
        req.webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(http_req, timeout=8) as resp:
            code = getattr(resp, "status", 200)
            return {"ok": 200 <= int(code) < 300, "status_code": int(code)}
    except HTTPError as e:
        return {"ok": False, "status_code": e.code, "message": str(e)}
    except URLError as e:
        return {"ok": False, "message": f"URLError: {e.reason}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _github_put_file(api_url: str, token: str, repo: str, branch: str, path: str, content_text: str, message: str) -> dict:
    get_url = f"{api_url.rstrip('/')}/repos/{repo}/contents/{path}?ref={branch}"
    get_req = urlrequest.Request(
        get_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        method="GET",
    )
    sha = None
    try:
        with urlrequest.urlopen(get_req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            sha = payload.get("sha")
    except Exception:
        sha = None

    put_url = f"{api_url.rstrip('/')}/repos/{repo}/contents/{path}"
    body = {
        "message": message,
        "content": base64.b64encode(content_text.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    put_req = urlrequest.Request(
        put_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        method="PUT",
    )
    with urlrequest.urlopen(put_req, timeout=15) as resp:
        code = getattr(resp, "status", 200)
        payload = json.loads(resp.read().decode("utf-8"))
        return {"status_code": int(code), "content": payload.get("content", {})}


@app.post("/reports/pr-comment")
def pr_comment_provider(req: ProviderPrCommentRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})

    provider = req.provider.strip().lower()
    if provider == "github":
        if not req.repo or not req.pr_number:
            return {"ok": False, "message": "GitHub requires repo and pr_number"}
        url = f"{req.api_url.rstrip('/')}/repos/{req.repo}/issues/{req.pr_number}/comments"
        payload = {"body": req.markdown}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {req.token}",
            "Accept": "application/vnd.github+json",
        }
    elif provider == "gitlab":
        if not req.project_id or not req.merge_request_iid:
            return {"ok": False, "message": "GitLab requires project_id and merge_request_iid"}
        url = f"{req.api_url.rstrip('/')}/projects/{req.project_id}/merge_requests/{req.merge_request_iid}/notes"
        payload = {"body": req.markdown}
        headers = {
            "Content-Type": "application/json",
            "PRIVATE-TOKEN": req.token,
        }
    else:
        return {"ok": False, "message": "Unsupported provider"}

    http_req = urlrequest.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlrequest.urlopen(http_req, timeout=10) as resp:
            code = getattr(resp, "status", 200)
            return {"ok": 200 <= int(code) < 300, "status_code": int(code), "provider": provider}
    except HTTPError as e:
        return {"ok": False, "status_code": e.code, "message": str(e), "provider": provider}
    except URLError as e:
        return {"ok": False, "message": f"URLError: {e.reason}", "provider": provider}
    except Exception as e:
        return {"ok": False, "message": str(e), "provider": provider}


@app.post("/reports/github-artifacts")
def github_artifacts(req: GithubArtifactsRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ast_path = f"{req.base_path.rstrip('/')}/ast-{ts}.json"
    findings_path = f"{req.base_path.rstrip('/')}/findings-{ts}.json"

    try:
        ast_result = _github_put_file(
            api_url=req.api_url,
            token=req.token,
            repo=req.repo,
            branch=req.branch,
            path=ast_path,
            content_text=json.dumps(req.ast, indent=2),
            message=f"Add AST artifact {ts}",
        )
        findings_result = _github_put_file(
            api_url=req.api_url,
            token=req.token,
            repo=req.repo,
            branch=req.branch,
            path=findings_path,
            content_text=json.dumps(req.findings, indent=2),
            message=f"Add findings artifact {ts}",
        )
        return {
            "ok": True,
            "repo": req.repo,
            "branch": req.branch,
            "files": [
                {"path": ast_path, "status_code": ast_result.get("status_code")},
                {"path": findings_path, "status_code": findings_result.get("status_code")},
            ],
        }
    except HTTPError as e:
        return {"ok": False, "status_code": e.code, "message": str(e)}
    except URLError as e:
        return {"ok": False, "message": f"URLError: {e.reason}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@app.post("/coaching/intake")
def coaching_intake(req: CoachingIntakeRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(req.applicant_email or "").strip().lower() or None,
    )
    submission_id = str(uuid4())
    normalized_job_links = [item.url if isinstance(item, CoachingJobLinkInput) else str(item) for item in (req.job_links or [])]
    enriched_preferences = dict(req.preferences or {})
    enriched_preferences["self_assessment"] = req.self_assessment or {}
    enriched_preferences["resume_parse_summary"] = req.resume_parse_summary or {}
    enriched_preferences["stack_preferences"] = req.stack_preferences or []
    enriched_preferences["tool_preferences"] = req.tool_preferences or []
    enriched_preferences["job_links_structured"] = [
        item.model_dump(mode="json") if isinstance(item, CoachingJobLinkInput) else {"url": str(item)}
        for item in (req.job_links or [])
    ]

    logger.info(
        "coaching_intake_received",
        extra={
            "actor": session.username,
            "role": session.role,
            "payload": pii_safe_coaching_log_payload(
                workspace_id=req.workspace_id,
                submission_id=submission_id,
                applicant_name=req.applicant_name,
                applicant_email=req.applicant_email,
                resume_text=req.resume_text,
                self_assessment_text=req.self_assessment_text,
                job_links=normalized_job_links,
            ),
        },
    )
    save_coaching_intake_submission(
        submission_id=submission_id,
        workspace_id=req.workspace_id,
        applicant_name=req.applicant_name,
        applicant_email=req.applicant_email or "",
        resume_text=req.resume_text,
        self_assessment_text=req.self_assessment_text,
        job_links=normalized_job_links,
        preferences=enriched_preferences,
        status="submitted",
        submitted_by=session.username,
    )
    _track_conversion_event(
        workspace_id=req.workspace_id,
        submission_id=submission_id,
        event_name="intake_completed",
        actor_user=session.username,
        payload={"job_links_count": len(normalized_job_links)},
    )
    return {"ok": True, "submission_id": submission_id, "workspace_id": req.workspace_id}


@app.get("/coaching/intake/submissions")
def coaching_intake_submissions(workspace_id: str, limit: int = 50, status: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _require_active_coaching_subscription(workspace_id=workspace_id, session=session)
    rows = list_coaching_intake_submissions(workspace_id=workspace_id, limit=limit, review_status=status)
    return {"workspace_id": workspace_id, "status_filter": status, "submissions": rows, "total": len(rows)}


@app.get("/coaching/intake/submissions/{submission_id}")
def coaching_intake_submission_detail(submission_id: str, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    intake = get_coaching_intake_submission(submission_id)
    if intake:
        _require_active_coaching_subscription(
            workspace_id=str(intake.get("workspace_id") or ""),
            session=session,
            email=str(intake.get("applicant_email") or "").strip().lower() or None,
        )
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": submission_id}
    latest_run = get_latest_coaching_generation_run(submission_id)
    return {"ok": True, "submission": intake, "latest_generation_run": latest_run}


@app.get("/coaching/subscription/status")
def coaching_subscription_status(workspace_id: str, request: Request, email: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=workspace_id)
    account = get_coaching_account_subscription(
        workspace_id=workspace_id,
        username=session.username,
        email=email,
    )
    if not account:
        logger.info(
            "coaching_subscription_status_lookup",
            extra={
                "actor": session.username,
                "role": session.role,
                "payload": pii_safe_subscription_log_payload(
                    workspace_id=workspace_id,
                    member_email=email or "",
                    subscription_status="not_found",
                    plan_tier="unknown",
                    launch_token=None,
                    can_access=False,
                ),
            },
        )
        return {
            "ok": True,
            "workspace_id": workspace_id,
            "username": session.username,
            "subscription": None,
            "active": False,
            "status": "not_found",
        }

    status = _normalize_subscription_status(str(account.get("subscription_status") or ""))
    logger.info(
        "coaching_subscription_status_lookup",
        extra={
            "actor": session.username,
            "role": session.role,
            "payload": pii_safe_subscription_log_payload(
                workspace_id=workspace_id,
                member_email=email or str(account.get("email") or ""),
                subscription_status=status,
                plan_tier=str(account.get("plan_tier") or "unknown"),
                launch_token=None,
                can_access=_is_active_subscription(status),
            ),
        },
    )
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "username": session.username,
        "subscription": account,
        "active": _is_active_subscription(status),
        "status": status,
    }


@app.get("/coaching/subscription/lifecycle-readiness")
def coaching_subscription_lifecycle_readiness(workspace_id: str, request: Request, email: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=workspace_id)
    account = get_coaching_account_subscription(workspace_id=workspace_id, username=session.username, email=email)
    events = list_recent_coaching_subscription_events(workspace_id=workspace_id, email=email, limit=10)
    normalized_status = _normalize_subscription_status(str((account or {}).get("subscription_status") or "not_found"))

    last_event_status = None
    if events:
        payload = events[0].get("payload_json") or {}
        if isinstance(payload, dict):
            last_event_status = _normalize_subscription_status(str(payload.get("subscription_status") or ""))

    checks = {
        "event_stream_present": len(events) > 0,
        "status_consistent_with_last_event": (last_event_status is None) or (last_event_status == normalized_status),
    }
    sanitized_events: list[dict[str, Any]] = []
    for evt in events:
        payload = evt.get("payload_json") if isinstance(evt, dict) else None
        payload_status = _normalize_subscription_status(str((payload or {}).get("subscription_status") or "")) if isinstance(payload, dict) else "unknown"
        sanitized_events.append(
            {
                "event_id": evt.get("event_id"),
                "event_type": evt.get("event_type"),
                "provider": evt.get("provider"),
                "received_at": evt.get("received_at"),
                "status": payload_status,
            }
        )
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "email": email,
        "status": normalized_status,
        "checks": checks,
        "recent_events": sanitized_events,
    }


@app.get("/coaching/pilot/launch-readiness")
def coaching_pilot_launch_readiness(workspace_id: str, request: Request, submission_id: str | None = None, email: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=workspace_id)
    account = get_coaching_account_subscription(workspace_id=workspace_id, username=session.username, email=email)
    status = _normalize_subscription_status(str((account or {}).get("subscription_status") or "not_found"))
    events = list_recent_coaching_subscription_events(workspace_id=workspace_id, email=email, limit=10)
    conversion_events = list_recent_coaching_conversion_events(workspace_id=workspace_id, submission_id=submission_id, limit=20)

    checks = {
        "subscription_active": _is_active_subscription(status),
        "subscription_event_stream_present": len(events) > 0,
        "launch_verification_present": any(str(e.get("event_name") or "") == "member_launch_verified" for e in conversion_events),
        "intake_completed_present": any(str(e.get("event_name") or "") == "intake_completed" for e in conversion_events),
    }
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "submission_id": submission_id,
        "status": status,
        "checks": checks,
        "ready": all(checks.values()),
        "recent_conversion_events": conversion_events[:10],
    }


@app.post("/coaching/subscription/sync")
def coaching_subscription_sync(req: CoachingSubscriptionSyncRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="subscription", request=request, session=session, workspace_id=req.workspace_id)
    verification = _verify_subscription_webhook_signature(req)
    if not verification.valid:
        logger.warning(
            "coaching_subscription_sync_rejected",
            extra={
                "actor": session.username,
                "role": session.role,
                "provider": req.provider,
                "event_type": req.event_type,
                "reason": verification.reason,
                "payload": pii_safe_subscription_log_payload(
                    workspace_id=req.workspace_id,
                    member_email=req.email,
                    subscription_status=_normalize_subscription_status(req.subscription_status),
                    plan_tier=req.plan_tier,
                    launch_token=None,
                    can_access=False,
                ),
            },
        )
        _record_invalid_webhook_signature_attempt(
            provider=str(req.provider or "generic").strip().lower(),
            source_ip=str((request.client.host if request.client else "unknown") or "unknown"),
            route="/coaching/subscription/sync",
            reason=str(verification.reason or "invalid_signature"),
            actor=session.username,
            role=session.role,
        )
        raise HTTPException(status_code=403, detail="Invalid webhook authentication")

    normalized_status = _normalize_subscription_status(req.subscription_status)
    event_id, derived_event_id = _derive_subscription_event_id(
        raw_event=req.raw_event,
        provider=req.provider,
        workspace_id=req.workspace_id,
        email=req.email,
        event_type=req.event_type,
        status=normalized_status,
    )

    existing = get_coaching_subscription_event(event_id)
    if existing:
        replay_status = _normalize_subscription_status(str((existing.get("payload_json") or {}).get("subscription_status") or normalized_status))
        return {
            "ok": True,
            "workspace_id": req.workspace_id,
            "event_id": event_id,
            "provider": req.provider,
            "status": replay_status,
            "active": _is_active_subscription(replay_status),
            "idempotent_replay": True,
            "idempotency_key_source": "derived" if derived_event_id else "provider_event_id",
            "message": "Subscription event already processed.",
        }

    logger.info(
        "coaching_subscription_sync_received",
        extra={
            "actor": session.username,
            "role": session.role,
            "provider": req.provider,
            "event_type": req.event_type,
            "payload": pii_safe_subscription_log_payload(
                workspace_id=req.workspace_id,
                member_email=req.email,
                subscription_status=normalized_status,
                plan_tier=req.plan_tier,
                launch_token=None,
                can_access=_is_active_subscription(normalized_status),
            ),
        },
    )
    save_coaching_subscription_event(
        event_id=event_id,
        workspace_id=req.workspace_id,
        provider=req.provider,
        event_type=req.event_type,
        email=req.email,
        provider_customer_id=req.provider_customer_id,
        provider_subscription_id=req.provider_subscription_id,
        payload=req.raw_event or req.model_dump(mode="json"),
        received_by=session.username,
    )
    upsert_coaching_account_subscription(
        workspace_id=req.workspace_id,
        username=str(req.username or session.username or "").strip() or None,
        email=req.email.strip().lower(),
        plan_tier=req.plan_tier,
        subscription_status=normalized_status,
        renewal_date=req.renewal_date,
        provider_customer_id=req.provider_customer_id,
        provider_subscription_id=req.provider_subscription_id,
        provider_source=req.provider,
        updated_by=session.username,
    )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "event_id": event_id,
        "provider": req.provider,
        "status": normalized_status,
        "active": _is_active_subscription(normalized_status),
        "idempotent_replay": False,
        "idempotency_key_source": "derived" if derived_event_id else "provider_event_id",
        "message": "Subscription sync stub accepted and stored.",
    }


@app.post("/coaching/subscription/webhook")
async def coaching_subscription_webhook(request: Request) -> dict:
    _apply_rate_limit(policy_name="subscription", request=request)
    raw_body = await request.body()
    payload = parse_webhook_body(raw_body)
    provider = str(request.headers.get("x-webhook-provider") or payload.get("provider") or "squarespace").strip().lower()
    verification = verify_webhook_signature(provider=provider, body_bytes=raw_body, headers={k: v for k, v in request.headers.items()}, tolerance_seconds=300)
    if not verification.valid:
        logger.warning(
            "coaching_subscription_webhook_rejected",
            extra={
                "provider": provider,
                "reason": verification.reason,
                "source_ip": str((request.client.host if request.client else "unknown") or "unknown"),
            },
        )
        _record_invalid_webhook_signature_attempt(
            provider=provider,
            source_ip=str((request.client.host if request.client else "unknown") or "unknown"),
            route="/coaching/subscription/webhook",
            reason=str(verification.reason or "invalid_signature"),
        )
        raise HTTPException(status_code=403, detail={"code": "invalid_webhook_signature", "reason": verification.reason})

    event_obj = payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
    metadata = event_obj.get("metadata") if isinstance(event_obj, dict) else {}
    req_payload = {
        "workspace_id": str(payload.get("workspace_id") or metadata.get("workspace_id") or "").strip(),
        "provider": provider,
        "event_type": str(payload.get("type") or payload.get("event_type") or "subscription.updated").strip(),
        "email": str(payload.get("email") or event_obj.get("customer_email") or event_obj.get("email") or "").strip().lower(),
        "plan_tier": str(payload.get("plan_tier") or metadata.get("plan_tier") or "coaching-core").strip(),
        "subscription_status": str(payload.get("subscription_status") or event_obj.get("status") or "unknown").strip(),
        "renewal_date": payload.get("renewal_date") or event_obj.get("current_period_end") or event_obj.get("renewal_date"),
        "provider_customer_id": payload.get("provider_customer_id") or event_obj.get("customer") or event_obj.get("customer_id"),
        "provider_subscription_id": payload.get("provider_subscription_id") or event_obj.get("id") or event_obj.get("subscription_id"),
        "raw_event": payload,
    }
    try:
        req = CoachingSubscriptionSyncRequest.model_validate(req_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_webhook_payload", "errors": exc.errors()})

    normalized_status = _normalize_subscription_status(req.subscription_status)
    event_id, derived_event_id = _derive_subscription_event_id(
        raw_event=req.raw_event,
        provider=req.provider,
        workspace_id=req.workspace_id,
        email=req.email,
        event_type=req.event_type,
        status=normalized_status,
    )
    existing = get_coaching_subscription_event(event_id)
    if existing:
        replay_status = _normalize_subscription_status(str((existing.get("payload_json") or {}).get("subscription_status") or normalized_status))
        return {
            "ok": True,
            "workspace_id": req.workspace_id,
            "event_id": event_id,
            "provider": req.provider,
            "status": replay_status,
            "active": _is_active_subscription(replay_status),
            "idempotent_replay": True,
            "idempotency_key_source": "derived" if derived_event_id else "provider_event_id",
            "message": "Subscription event already processed.",
        }

    save_coaching_subscription_event(
        event_id=event_id,
        workspace_id=req.workspace_id,
        provider=req.provider,
        event_type=req.event_type,
        email=req.email,
        provider_customer_id=req.provider_customer_id,
        provider_subscription_id=req.provider_subscription_id,
        payload=req.raw_event or req.model_dump(mode="json"),
        received_by="webhook",
    )
    upsert_coaching_account_subscription(
        workspace_id=req.workspace_id,
        username=None,
        email=req.email.strip().lower(),
        plan_tier=req.plan_tier,
        subscription_status=normalized_status,
        renewal_date=req.renewal_date,
        provider_customer_id=req.provider_customer_id,
        provider_subscription_id=req.provider_subscription_id,
        provider_source=req.provider,
        updated_by="webhook",
    )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "event_id": event_id,
        "provider": req.provider,
        "status": normalized_status,
        "active": _is_active_subscription(normalized_status),
        "idempotent_replay": False,
        "idempotency_key_source": "derived" if derived_event_id else "provider_event_id",
        "message": "Subscription sync stub accepted and stored.",
    }


def _recommend_stack_tools(parsed_jobs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    stack_scores: dict[str, int] = {}
    tool_scores: dict[str, int] = {}

    for job in parsed_jobs:
        signals = job.get("signals") or {}
        for skill in (signals.get("skills") or []):
            key = str(skill or "").strip().lower()
            if not key:
                continue
            stack_scores[key] = stack_scores.get(key, 0) + 1
        for tool in (signals.get("tools") or []):
            key = str(tool or "").strip().lower()
            if not key:
                continue
            tool_scores[key] = tool_scores.get(key, 0) + 1

    top_stack = [{"name": name, "score": score} for name, score in sorted(stack_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    top_tools = [{"name": name, "score": score} for name, score in sorted(tool_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:8]]
    return {"stack": top_stack, "tools": top_tools}


@app.post("/coaching/jobs/recommendations")
def coaching_jobs_recommendations(req: CoachingRecommendStackToolsRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})

    links: list[str] = []
    if req.submission_id:
        intake = get_coaching_intake_submission(req.submission_id)
        if not intake:
            return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}
        _require_active_coaching_subscription(
            workspace_id=req.workspace_id,
            session=session,
            email=str(intake.get("applicant_email") or "").strip().lower() or None,
        )
        links.extend([str(x or "").strip() for x in (intake.get("job_links_json") or []) if str(x or "").strip()])

    for item in req.job_links:
        link = item.url if isinstance(item, CoachingJobLinkInput) else str(item or "").strip()
        if link:
            links.append(link)

    dedup_links = list(dict.fromkeys(links))
    if not dedup_links:
        return {"ok": True, "workspace_id": req.workspace_id, "parsed_jobs": [], "recommendations": {"stack": [], "tools": []}}

    parsed_jobs: list[dict[str, Any]] = []
    for link in dedup_links[:20]:
        fetched = fetch_job_text(link)
        signals = extract_job_signals(fetched.get("text") or "") if fetched.get("ok") else {}
        parsed_jobs.append(
            {
                "url": link,
                "ok": bool(fetched.get("ok")),
                "error": fetched.get("error"),
                "signals": signals,
            }
        )

    recommendations = _recommend_stack_tools(parsed_jobs)
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "parsed_jobs": parsed_jobs,
        "recommendations": recommendations,
    }


@app.post("/coaching/jobs/parse")
def coaching_jobs_parse(req: CoachingJobParseRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    logger.info(
        "coaching_jobs_parse_requested",
        extra={
            "actor": session.username,
            "role": session.role,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "force_refresh": req.force_refresh,
        },
    )
    intake = get_coaching_intake_submission(req.submission_id)
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    parsed_jobs: list[dict] = []
    for link in (intake.get("job_links_json") or []):
        cache_key = f"{req.submission_id}:{link}".strip().lower()
        cached = None if req.force_refresh else get_coaching_job_parse_cache(cache_key)
        if cached:
            parsed_jobs.append({
                "url": link,
                "source": "cache",
                "text_excerpt": str(cached.get("parsed_text") or "")[:400],
                "signals": cached.get("parsed_json") or {},
            })
            continue

        fetched = fetch_job_text(link)
        signals = extract_job_signals(fetched.get("text") or "") if fetched.get("ok") else {}
        upsert_coaching_job_parse_cache(
            cache_key=cache_key,
            source_url=link,
            parsed_text=fetched.get("text") or "",
            parsed_json=signals,
        )
        parsed_jobs.append({
            "url": link,
            "source": "live",
            "ok": fetched.get("ok"),
            "error": fetched.get("error"),
            "text_excerpt": str(fetched.get("text") or "")[:400],
            "signals": signals,
        })

    logger.info(
        "coaching_jobs_parse_completed",
        extra={
            "actor": session.username,
            "role": session.role,
            "payload": pii_safe_coaching_log_payload(
                workspace_id=req.workspace_id,
                submission_id=req.submission_id,
                job_links=intake.get("job_links_json") or [],
                parsed_jobs=parsed_jobs,
            ),
        },
    )
    return {"ok": True, "submission_id": req.submission_id, "parsed_jobs": parsed_jobs}


@app.post("/coaching/sow/generate")
def coaching_generate_sow(req: CoachingGenerateSowRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="generation", request=request, session=session, workspace_id=req.workspace_id)
    logger.info(
        "coaching_sow_generate_requested",
        extra={
            "actor": session.username,
            "role": session.role,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "parsed_jobs_count": len(req.parsed_jobs or []),
        },
    )
    intake = get_coaching_intake_submission(req.submission_id)
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(intake.get("applicant_email") or "").strip().lower() or None,
    )

    parsed_jobs = req.parsed_jobs or []
    generation_started_at = time.perf_counter()
    feedback_events = list_recent_coaching_feedback_events(req.submission_id, limit=3)
    feedback_hints = [
        str(h).strip()
        for event in feedback_events
        for h in (event.get("regeneration_hints_json") or [])
        if str(h).strip()
    ][:8]
    masked_feedback_hints = [mask_secrets_in_text(str(h or "")) for h in feedback_hints if str(h or "").strip()]

    llm_result = generate_sow_with_llm(
        intake={
            "applicant_name": intake.get("applicant_name"),
            "preferences": intake.get("preferences_json") or {},
            "resume_text": intake.get("resume_text") or "",
            "self_assessment_text": intake.get("self_assessment_text") or "",
        },
        parsed_jobs=parsed_jobs,
    )
    sow = llm_result.get("sow") or build_sow_skeleton(
        intake={
            "applicant_name": intake.get("applicant_name"),
            "preferences": intake.get("preferences_json") or {},
        },
        parsed_jobs=parsed_jobs,
    )

    quality_floor_score = 80
    first_findings = validate_sow_payload(sow)
    auto_revised = False
    retried_after_validation = False
    auto_regenerated_for_quality_floor = False
    hard_quality_gate_triggered = False
    if first_findings:
        sow = auto_revise_sow_once(sow, first_findings)
        auto_revised = True
        retried_after_validation = True

    strict_sow = CoachingSowDraft.model_validate(ensure_interview_ready_package(sow)).model_dump(mode="json", by_alias=True)
    strict_sow = enforce_required_section_order(strict_sow)
    strict_sow, sanitize_findings = sanitize_generated_sow(strict_sow)
    strict_sow = ensure_interview_ready_package(strict_sow)
    strict_sow = enforce_required_section_order(strict_sow)
    final_findings = validate_sow_payload(strict_sow)
    quality = compute_sow_quality_score(strict_sow, final_findings)

    if int(quality.get("score") or 0) < quality_floor_score:
        strict_sow = auto_revise_sow_once(strict_sow, final_findings)
        strict_sow = CoachingSowDraft.model_validate(ensure_interview_ready_package(strict_sow)).model_dump(mode="json", by_alias=True)
        strict_sow = enforce_required_section_order(strict_sow)
        strict_sow, extra_sanitize_findings = sanitize_generated_sow(strict_sow)
        strict_sow = ensure_interview_ready_package(strict_sow)
        strict_sow = enforce_required_section_order(strict_sow)
        if extra_sanitize_findings:
            sanitize_findings = [*sanitize_findings, *extra_sanitize_findings]
        final_findings = validate_sow_payload(strict_sow)
        quality = compute_sow_quality_score(strict_sow, final_findings)
        auto_regenerated_for_quality_floor = True
        retried_after_validation = True

    # hard quality gate: never ship low-quality output to client payload
    if final_findings or int(quality.get("score") or 0) < quality_floor_score:
        hard_quality_gate_triggered = True
        strict_sow = auto_revise_sow_once(build_sow_skeleton(
            intake={
                "applicant_name": intake.get("applicant_name"),
                "preferences": intake.get("preferences_json") or {},
            },
            parsed_jobs=parsed_jobs,
        ), final_findings)
        strict_sow = CoachingSowDraft.model_validate(ensure_interview_ready_package(strict_sow)).model_dump(mode="json", by_alias=True)
        strict_sow = enforce_required_section_order(strict_sow)
        strict_sow, hard_gate_sanitize = sanitize_generated_sow(strict_sow)
        strict_sow = ensure_interview_ready_package(strict_sow)
        strict_sow = enforce_required_section_order(strict_sow)
        sanitize_findings = [*sanitize_findings, *hard_gate_sanitize]
        final_findings = validate_sow_payload(strict_sow)
        quality = compute_sow_quality_score(strict_sow, final_findings)
        auto_regenerated_for_quality_floor = True

    final_quality_clean = (len(final_findings) == 0) and (int(quality.get("score") or 0) >= quality_floor_score)

    reason_codes: list[str] = []
    upstream_reason = str((llm_result.get("meta") or {}).get("reason_code") or "").strip().upper()
    if not bool(llm_result.get("ok")):
        reason_codes.append(upstream_reason or "LLM_FALLBACK_TRIGGERED")
    if retried_after_validation:
        reason_codes.append("VALIDATION_RETRY_APPLIED")
    if auto_regenerated_for_quality_floor:
        reason_codes.append("QUALITY_FLOOR_REGEN_APPLIED")
    if hard_quality_gate_triggered:
        reason_codes.append("HARD_QUALITY_GATE_TRIGGERED")
    if final_findings:
        reason_codes.append("FINAL_FINDINGS_PRESENT")
    if hard_quality_gate_triggered and final_quality_clean:
        reason_codes.append("HARD_QUALITY_GATE_RESOLVED")

    if not final_quality_clean:
        generation_mode = "fallback_scaffold"
    elif not bool(llm_result.get("ok")):
        generation_mode = "fallback_scaffold"
    elif retried_after_validation or auto_regenerated_for_quality_floor or hard_quality_gate_triggered:
        generation_mode = "revised"
    else:
        generation_mode = "llm"

    reason_codes = list(dict.fromkeys([c for c in reason_codes if c]))

    quality_diagnostics = build_quality_diagnostics(
        quality=quality,
        findings=final_findings,
        floor_score=quality_floor_score,
        auto_regenerated=auto_regenerated_for_quality_floor,
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
    )
    if masked_feedback_hints:
        existing = quality_diagnostics.get("targeted_regeneration_hints") or []
        quality_diagnostics["targeted_regeneration_hints"] = list(dict.fromkeys([*masked_feedback_hints, *existing]))[:10]

    prior_runs = list_coaching_generation_runs(req.submission_id, limit=1)
    prior_score = None
    prior_findings_count = None
    if prior_runs:
        prior_validation = prior_runs[0].get("validation_json") or {}
        prior_score = ((prior_validation.get("quality") or {}).get("score"))
        prior_final_findings = prior_validation.get("final_findings") or []
        if isinstance(prior_final_findings, list):
            prior_findings_count = len(prior_final_findings)
    quality_delta_meta = {
        "before": {
            "score": int(prior_score) if prior_score is not None else None,
            "findings_count": prior_findings_count,
        },
        "after": {
            "score": int(quality.get("score") or 0),
            "findings_count": len(final_findings),
        },
        "score_delta": (quality.get("score") - int(prior_score)) if prior_score is not None else None,
        "findings_delta": (len(final_findings) - int(prior_findings_count)) if prior_findings_count is not None else None,
    }
    generation_meta = _safe_generation_meta(llm_result.get("meta") or {})
    generation_latency_ms = int((time.perf_counter() - generation_started_at) * 1000)
    total_tokens = int(((generation_meta.get("usage") or {}).get("total_tokens") or 0))
    observability = {
        "latency_ms": generation_latency_ms,
        "latency_band": _latency_band(generation_latency_ms),
        "token_usage": total_tokens,
        "cost_band": _cost_band(total_tokens),
    }

    run_id = str(uuid4())
    save_coaching_generation_run(
        run_id=run_id,
        submission_id=req.submission_id,
        workspace_id=req.workspace_id,
        run_status="completed" if len(final_findings) == 0 else "needs_review",
        parsed_jobs=parsed_jobs,
        sow=strict_sow,
        validation={
            "first_pass_findings": first_findings,
            "final_findings": final_findings,
            "sanitize_findings": sanitize_findings,
            "auto_revised": auto_revised,
            "retried_after_validation": retried_after_validation,
            "guardrails": {"strict_schema": True, "auto_revise_once": True},
            "generation_meta": generation_meta,
            "observability": observability,
            "feedback_loop": {
                "feedback_event_count": len(feedback_events),
                "regeneration_hints_used": masked_feedback_hints,
            },
            "quality_flags": {
                "has_required_contract_fields": len(final_findings) == 0,
                "used_llm_provider": generation_meta.get("provider") == "openai-compatible",
                "fallback_used": generation_mode == "fallback_scaffold",
                "generation_mode": generation_mode,
                "reason_codes": reason_codes,
                "auto_regenerated_for_quality_floor": auto_regenerated_for_quality_floor,
                "hard_quality_gate_triggered": hard_quality_gate_triggered,
            },
            "quality": {
                **quality,
                "regenerate_requested": bool(req.regenerate_with_improvements),
                "quality_delta": quality_delta_meta.get("score_delta"),
                "quality_delta_meta": quality_delta_meta,
                "quality_diagnostics": quality_diagnostics,
            },
        },
        error_message=None,
        created_by=session.username,
    )

    _track_conversion_event(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        event_name="sow_regenerated" if req.regenerate_with_improvements else "sow_generated",
        actor_user=session.username,
        payload={
            "run_id": run_id,
            "quality_score": int(quality.get("score") or 0),
            "latency_band": observability.get("latency_band"),
            "cost_band": observability.get("cost_band"),
        },
    )

    logger.info(
        "coaching_sow_generate_completed",
        extra={
            "actor": session.username,
            "role": session.role,
            "payload": pii_safe_coaching_log_payload(
                workspace_id=req.workspace_id,
                submission_id=req.submission_id,
                applicant_name=intake.get("applicant_name"),
                applicant_email=intake.get("applicant_email"),
                resume_text=intake.get("resume_text"),
                self_assessment_text=intake.get("self_assessment_text"),
                job_links=intake.get("job_links_json") or [],
                parsed_jobs=parsed_jobs,
            ),
        },
    )
    return {
        "ok": True,
        "run_id": run_id,
        "submission_id": req.submission_id,
        "workspace_id": req.workspace_id,
        "sow": strict_sow,
        "valid": len(final_findings) == 0,
        "auto_revised": auto_revised,
        "findings": final_findings,
        "generation_meta": generation_meta,
        "generation_mode": generation_mode,
        "generation_reason_codes": reason_codes,
        "observability": observability,
        "quality_flags": {
            "has_required_contract_fields": len(final_findings) == 0,
            "used_llm_provider": generation_meta.get("provider") == "openai-compatible",
            "fallback_used": generation_mode == "fallback_scaffold",
            "generation_mode": generation_mode,
            "reason_codes": reason_codes,
            "retried_after_validation": retried_after_validation,
            "auto_regenerated_for_quality_floor": auto_regenerated_for_quality_floor,
            "hard_quality_gate_triggered": hard_quality_gate_triggered,
        },
        "quality": {
            **quality,
            "regenerate_requested": bool(req.regenerate_with_improvements),
            "quality_delta": quality_delta_meta.get("score_delta"),
            "quality_delta_meta": quality_delta_meta,
            "quality_diagnostics": quality_diagnostics,
        },
        "schema": {
            "schema_version": "0.2",
            "model": "CoachingSowDraft",
            "required_sections": [
                "project_title",
                "business_outcome",
                "solution_architecture",
                "project_story",
                "milestones",
                "roi_dashboard_requirements",
                "resource_plan",
                "mentoring_cta",
                "project_charter",
            ],
            "strict_enforced": True,
        },
    }

@app.post("/coaching/sow/generate-draft")
def coaching_generate_sow_draft(req: CoachingGenerateSowRequest, request: Request, session=Depends(get_current_session)) -> dict:
    return coaching_generate_sow(req, request, session)


@app.post("/coaching/sow/validate")
def coaching_sow_validate(req: CoachingSowValidateRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    intake = get_coaching_intake_submission(req.submission_id)
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(intake.get("applicant_email") or "").strip().lower() or None,
    )

    sow_payload = req.sow.model_dump(mode="json", by_alias=True)
    sow_payload, _ = sanitize_generated_sow(sow_payload)
    findings = validate_sow_payload(sow_payload)
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "valid": len(findings) == 0,
        "findings": findings,
        "sow": sow_payload,
    }


@app.post("/coaching/resources/match")
def coaching_resources_match(req: CoachingResourceMatchRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    match = match_resources_for_sow(req.sow.model_dump(mode="json", by_alias=True), RESOURCE_LIBRARY_PATH)
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "resource_plan": {
            "required": match.get("required") or [],
            "recommended": match.get("recommended") or [],
            "optional": match.get("optional") or [],
        },
        "match_meta": match.get("match_meta") or {},
        "mentoring": match.get("mentoring") or {},
    }


@app.post("/coaching/demo/seed-package")
def coaching_demo_seed_package(req: CoachingDemoSeedRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    sample_intake = {
        "workspace_id": req.workspace_id,
        "applicant_name": req.applicant_name,
        "preferences": {"timeline_weeks": 6, "target_role": "Data Engineer"},
        "parsed_jobs": [
            {
                "url": "https://example.com/jobs/data-engineer-1",
                "signals": {
                    "skills": ["python", "sql", "databricks", "spark", "data modeling"],
                    "tools": ["databricks", "airflow", "power bi"],
                    "domains": ["retail"],
                    "seniority": "mid",
                },
            }
        ],
    }
    package = compose_demo_project_package(sample_intake=sample_intake, resource_file=RESOURCE_LIBRARY_PATH)
    return {"ok": True, "workspace_id": req.workspace_id, "project_package": package}


@app.get("/coaching/demo/seed-package")
def coaching_demo_seed_package_get(workspace_id: str, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    latest = list_coaching_intake_submissions(workspace_id=workspace_id, limit=1)
    applicant_name = str((latest[0] if latest else {}).get("applicant_name") or "Demo Candidate")
    sample_intake = {
        "workspace_id": workspace_id,
        "applicant_name": applicant_name,
        "preferences": {"timeline_weeks": 6, "target_role": "Data Engineer"},
        "parsed_jobs": [
            {
                "url": "https://example.com/jobs/data-engineer-1",
                "signals": {
                    "skills": ["python", "sql", "databricks", "spark", "data modeling"],
                    "tools": ["databricks", "airflow", "power bi"],
                    "domains": ["retail"],
                    "seniority": "mid",
                },
            }
        ],
    }
    package = compose_demo_project_package(sample_intake=sample_intake, resource_file=RESOURCE_LIBRARY_PATH)
    return {"ok": True, "workspace_id": workspace_id, "project_package": package}


@app.post("/coaching/sow/export")
def coaching_sow_export(req: CoachingSowExportRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="exports", request=request, session=session, workspace_id=req.workspace_id)
    intake = get_coaching_intake_submission(req.submission_id)
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(intake.get("applicant_email") or "").strip().lower() or None,
    )

    sow_payload = req.sow.model_dump(mode="json", by_alias=True)
    sow_payload, _ = sanitize_generated_sow(sow_payload)
    sow_payload = ensure_interview_ready_package(sow_payload)
    sow_payload = enforce_required_section_order(sow_payload)
    fmt = str(req.format or "markdown").strip().lower()
    _track_conversion_event(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        event_name="sow_exported",
        actor_user=session.username,
        payload={"format": fmt},
    )
    if fmt == "json":
        return {
            "ok": True,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "format": "json",
            "content": json.dumps(sow_payload, indent=2),
        }
    if fmt == "docx":
        docx_bytes = _render_sow_docx_bytes(sow_payload)
        filename = f"{_safe_export_slug(str(sow_payload.get('project_title') or 'coaching-sow'))}-{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"
        return {
            "ok": True,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "format": "docx",
            "filename": filename,
            "mime_type": DOCX_EXPORT_MIME,
            "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
        }
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "format": "markdown",
        "content": _render_sow_markdown(sow_payload),
    }


@app.get("/coaching/review/open-submissions")
def coaching_review_open_submissions(workspace_id: str, limit: int = 50, status: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _require_active_coaching_subscription(workspace_id=workspace_id, session=session)
    submissions = list_coaching_intake_submissions(workspace_id=workspace_id, limit=limit)
    enriched: list[dict[str, Any]] = []
    for sub in submissions:
        submission_id = str(sub.get("submission_id") or "")
        latest = get_latest_coaching_generation_run(submission_id) if submission_id else None
        run_status = str((latest or {}).get("run_status") or "not_started")
        review_status = str(sub.get("coach_review_status") or "new")
        if status and review_status != status:
            continue
        if run_status != "completed":
            enriched.append({"submission": sub, "latest_generation_run": latest, "review_state": run_status, "coach_review_status": review_status})

    return {"ok": True, "workspace_id": workspace_id, "open_submissions": enriched, "total": len(enriched)}


@app.get("/coaching/review/submissions/{submission_id}/runs")
def coaching_review_submission_runs(submission_id: str, limit: int = 20, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    submission = get_coaching_intake_submission(submission_id)
    if submission:
        _require_active_coaching_subscription(
            workspace_id=str(submission.get("workspace_id") or ""),
            session=session,
            email=str(submission.get("applicant_email") or "").strip().lower() or None,
        )
    if not submission:
        return {"ok": False, "message": "submission not found", "submission_id": submission_id}
    runs = list_coaching_generation_runs(submission_id=submission_id, limit=limit)
    return {
        "ok": True,
        "submission_id": submission_id,
        "workspace_id": submission.get("workspace_id"),
        "runs": runs,
        "total": len(runs),
    }


@app.post("/coaching/review/approve-send")
def coaching_review_approve_send(req: CoachingReviewApproveSendRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="review_actions", request=request, session=session, workspace_id=req.workspace_id)
    submission = get_coaching_intake_submission(req.submission_id)
    if not submission:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(submission.get("applicant_email") or "").strip().lower() or None,
    )

    latest_run = get_latest_coaching_generation_run(req.submission_id)
    if not latest_run:
        return {"ok": False, "message": "generation run not found", "submission_id": req.submission_id}
    if str(latest_run.get("run_status") or "") != "completed":
        return {
            "ok": False,
            "message": "latest generation run must be completed before approve-send",
            "submission_id": req.submission_id,
            "latest_run_status": latest_run.get("run_status"),
        }

    persist = _persist_review_state_with_retry(
        submission_id=req.submission_id,
        coach_review_status="approved_sent",
        coach_notes=req.coach_notes,
    )
    if not persist.get("ok"):
        return {
            "ok": False,
            "message": "failed to persist approved_sent review state",
            "submission_id": req.submission_id,
            "attempts": persist.get("attempts"),
            "error": persist.get("error"),
        }

    launch_token = _mint_launch_token(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        email=str(submission.get("applicant_email") or ""),
    )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "coach_review_status": "approved_sent",
        "consistency": {
            "persist_attempts": persist.get("attempts"),
            "persist_ok": True,
        },
        "handoff": {
            "launch_token": launch_token,
            "latest_run_id": latest_run.get("run_id"),
        },
        "audit": {
            "action": "review_approve_send",
            "actor": session.username,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
        },
    }


@app.post("/coaching/member/launch-token/verify")
def coaching_member_launch_token_verify(req: CoachingLaunchTokenVerifyRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    result = _verify_launch_token(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        token=req.launch_token,
    )
    if bool(result.get("valid")):
        _track_conversion_event(
            workspace_id=req.workspace_id,
            submission_id=req.submission_id,
            event_name="member_launch_verified",
            actor_user=session.username,
            payload={"source": "launch_token_verify"},
        )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "valid": bool(result.get("valid")),
        "reason": result.get("reason"),
    }


@app.post("/coaching/review/status")
def coaching_review_status_update(req: CoachingReviewStatusUpdateRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="review_actions", request=request, session=session, workspace_id=req.workspace_id)
    submission = get_coaching_intake_submission(req.submission_id)
    if not submission:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}
    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(submission.get("applicant_email") or "").strip().lower() or None,
    )
    persist = _persist_review_state_with_retry(
        submission_id=req.submission_id,
        coach_review_status=req.coach_review_status,
        coach_notes=req.coach_notes,
    )
    if not persist.get("ok"):
        return {
            "ok": False,
            "message": "failed to persist review status update",
            "submission_id": req.submission_id,
            "attempts": persist.get("attempts"),
            "error": persist.get("error"),
        }
    return {
        "ok": True,
        "submission": persist.get("submission"),
        "consistency": {"persist_attempts": persist.get("attempts"), "persist_ok": True},
        "audit": {
            "action": "review_status_update",
            "actor": session.username,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
        },
    }


@app.post("/coaching/review/batch-status")
def coaching_review_batch_status_update(req: CoachingBatchReviewStatusUpdateRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="review_actions", request=request, session=session, workspace_id=req.workspace_id)

    updated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    batch_id = str(uuid4())
    deduped_submission_ids = list(dict.fromkeys(req.submission_ids or []))
    for submission_id in deduped_submission_ids:
        submission = get_coaching_intake_submission(submission_id)
        if not submission:
            failed.append({"submission_id": submission_id, "error": "submission not found"})
            continue
        try:
            _require_active_coaching_subscription(
                workspace_id=req.workspace_id,
                session=session,
                email=str(submission.get("applicant_email") or "").strip().lower() or None,
            )
        except HTTPException as exc:
            failed.append({"submission_id": submission_id, "error": str(exc.detail)})
            continue

        persist = _persist_review_state_with_retry(
            submission_id=submission_id,
            coach_review_status=req.coach_review_status,
            coach_notes=req.coach_notes,
        )
        if not persist.get("ok"):
            failed.append(
                {
                    "submission_id": submission_id,
                    "error": persist.get("error") or "failed to persist review status",
                    "attempts": persist.get("attempts"),
                }
            )
            continue
        updated.append(
            {
                "submission_id": submission_id,
                "submission": persist.get("submission"),
                "attempts": persist.get("attempts"),
                "audit": {
                    "action": "batch_review_status_update",
                    "batch_id": batch_id,
                    "actor": session.username,
                    "workspace_id": req.workspace_id,
                    "coach_review_status": req.coach_review_status,
                },
            }
        )

    return {
        "ok": len(failed) == 0,
        "workspace_id": req.workspace_id,
        "coach_review_status": req.coach_review_status,
        "updated": updated,
        "failed": failed,
        "counts": {"updated": len(updated), "failed": len(failed), "requested": len(req.submission_ids or [])},
        "audit": {
            "action": "batch_review_status_update",
            "batch_id": batch_id,
            "actor": session.username,
            "workspace_id": req.workspace_id,
            "requested_submissions": len(req.submission_ids or []),
            "deduped_submissions": len(deduped_submission_ids),
        },
    }


@app.post("/coaching/sow/batch-regenerate")
def coaching_batch_regenerate(req: CoachingBatchRegenerateRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="generation", request=request, session=session, workspace_id=req.workspace_id)

    runs: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    batch_id = str(uuid4())
    deduped_submission_ids = list(dict.fromkeys(req.submission_ids or []))
    for submission_id in deduped_submission_ids:
        out = coaching_generate_sow(
            CoachingGenerateSowRequest(
                workspace_id=req.workspace_id,
                submission_id=submission_id,
                parsed_jobs=req.parsed_jobs or [],
                regenerate_with_improvements=bool(req.regenerate_with_improvements),
            ),
            request,
            session,
        )
        if not out.get("ok"):
            failed.append({"submission_id": submission_id, "error": out.get("message") or "generation failed"})
            continue
        runs.append(
            {
                "submission_id": submission_id,
                "run_id": out.get("run_id"),
                "quality_score": ((out.get("quality") or {}).get("score")),
                "findings_count": len(out.get("findings") or []),
                "hard_quality_gate_triggered": bool((out.get("quality_flags") or {}).get("hard_quality_gate_triggered")),
                "audit": {
                    "action": "batch_regenerate_submission",
                    "batch_id": batch_id,
                    "actor": session.username,
                    "workspace_id": req.workspace_id,
                },
            }
        )

    return {
        "ok": len(failed) == 0,
        "workspace_id": req.workspace_id,
        "runs": runs,
        "failed": failed,
        "counts": {"completed": len(runs), "failed": len(failed), "requested": len(req.submission_ids or [])},
        "audit": {
            "action": "batch_regenerate",
            "batch_id": batch_id,
            "actor": session.username,
            "workspace_id": req.workspace_id,
            "requested_submissions": len(req.submission_ids or []),
            "deduped_submissions": len(deduped_submission_ids),
        },
    }


@app.post("/coaching/review/feedback")
def coaching_review_feedback(req: CoachingFeedbackCaptureRequest, request: Request, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    _apply_rate_limit(policy_name="review_actions", request=request, session=session, workspace_id=req.workspace_id)
    submission = get_coaching_intake_submission(req.submission_id)
    if not submission:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(submission.get("applicant_email") or "").strip().lower() or None,
    )

    save_coaching_feedback_event(
        feedback_id=str(uuid4()),
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        run_id=req.run_id,
        review_tags=req.review_tags,
        coach_notes=req.coach_notes,
        regeneration_hints=req.regeneration_hints,
        created_by=session.username,
    )
    _track_conversion_event(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        event_name="coach_feedback_captured",
        actor_user=session.username,
        payload={"review_tags": req.review_tags, "hint_count": len(req.regeneration_hints or [])},
    )
    return {
        "ok": True,
        "workspace_id": req.workspace_id,
        "submission_id": req.submission_id,
        "tag_count": len(req.review_tags or []),
        "audit": {
            "action": "review_feedback_capture",
            "actor": session.username,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
        },
    }


@app.post("/coaching/mentoring/intent")
def coaching_mentoring_intent(req: CoachingMentoringIntentRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _track_conversion_event(
        workspace_id=req.workspace_id,
        submission_id=req.submission_id,
        event_name="mentoring_intent" if req.intent_type != "cta_click" else "cta_click",
        actor_user=session.username,
        payload={"cta_context": req.cta_context or ""},
    )
    return {"ok": True, "workspace_id": req.workspace_id, "submission_id": req.submission_id, "intent_type": req.intent_type}


@app.get("/coaching/conversion/funnel")
def coaching_conversion_funnel(workspace_id: str, submission_id: str | None = None, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    events = list_recent_coaching_conversion_events(workspace_id=workspace_id, submission_id=submission_id, limit=500)
    counts: dict[str, int] = {}
    for event in events:
        name = str(event.get("event_name") or "unknown")
        counts[name] = counts.get(name, 0) + 1
    ordered = [
        "member_launch_verified",
        "intake_completed",
        "sow_generated",
        "sow_regenerated",
        "sow_exported",
        "cta_click",
        "mentoring_intent",
        "coach_feedback_captured",
    ]
    funnel = [{"event": name, "count": counts.get(name, 0)} for name in ordered]
    return {"ok": True, "workspace_id": workspace_id, "submission_id": submission_id, "funnel": funnel, "total_events": len(events)}


@app.get("/coaching/conversion/weekly-summary")
def coaching_conversion_weekly_summary(
    workspace_id: str,
    submission_id: str | None = None,
    lookback_days: int = 7,
    session=Depends(get_current_session),
) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    days = max(1, min(int(lookback_days or 7), 60))
    now_utc = datetime.now(timezone.utc)
    since = (now_utc - timedelta(days=days)).isoformat()
    until = now_utc.isoformat()

    events = list_coaching_conversion_events_window(
        workspace_id=workspace_id,
        submission_id=submission_id,
        since_iso=since,
        until_iso=until,
        limit=10000,
    )

    tracked = ["intake_completed", "sow_generated", "sow_regenerated", "sow_exported", "cta_click", "mentoring_intent"]
    counts = {name: 0 for name in tracked}
    raw_event_counts = {name: 0 for name in tracked}
    by_day: dict[str, dict[str, int]] = {}

    stage_actor_sets: dict[str, set[str]] = {name: set() for name in tracked}
    for idx, event in enumerate(events):
        name = str(event.get("event_name") or "unknown")
        created_at = str(event.get("created_at") or "")
        day = created_at[:10] if len(created_at) >= 10 else "unknown"
        if name in raw_event_counts:
            raw_event_counts[name] += 1
        if name in counts:
            submission_key = str(event.get("submission_id") or "").strip() or f"event-{idx}"
            stage_actor_sets[name].add(submission_key)
            counts[name] = len(stage_actor_sets[name])
            by_day.setdefault(day, {k: 0 for k in tracked})
            by_day[day][name] += 1

    intake_base = counts.get("intake_completed", 0)
    generated_total = len(stage_actor_sets["sow_generated"].union(stage_actor_sets["sow_regenerated"]))
    exported_total = counts.get("sow_exported", 0)
    cta_total = len(stage_actor_sets["cta_click"].union(stage_actor_sets["mentoring_intent"]))

    def _safe_rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(min(1.0, numerator / denominator), 3)

    summary_rates = {
        "generate_rate": _safe_rate(generated_total, intake_base),
        "export_rate": _safe_rate(exported_total, intake_base),
        "cta_rate": _safe_rate(cta_total, intake_base),
    }

    funnel_stages = [
        ("intake_completed", counts.get("intake_completed", 0)),
        ("sow_generated_or_regenerated", generated_total),
        ("sow_exported", exported_total),
        ("cta_or_intent", cta_total),
    ]
    drop_offs: list[dict[str, Any]] = []
    for idx in range(len(funnel_stages) - 1):
        stage, current = funnel_stages[idx]
        next_stage, nxt = funnel_stages[idx + 1]
        loss = max(0, current - nxt)
        loss_rate = round((loss / current), 3) if current > 0 else None
        drop_offs.append(
            {
                "from_stage": stage,
                "to_stage": next_stage,
                "current_count": current,
                "next_count": nxt,
                "drop_off_count": loss,
                "drop_off_rate": loss_rate,
            }
        )
    top_drop_offs = sorted(drop_offs, key=lambda row: row.get("drop_off_count") or 0, reverse=True)

    return {
        "ok": True,
        "workspace_id": workspace_id,
        "submission_id": submission_id,
        "lookback_days": days,
        "window": {"since": since, "until": until},
        "counts": counts,
        "raw_event_counts": raw_event_counts,
        "conversion_rates": summary_rates,
        "drop_off_insights": {
            "stage_sequence": [{"stage": stage, "count": count} for stage, count in funnel_stages],
            "stage_drop_offs": drop_offs,
            "top_drop_offs": top_drop_offs[:3],
        },
        "daily_breakdown": [{"day": day, **vals} for day, vals in sorted(by_day.items())],
        "total_events": len(events),
    }


@app.get("/coaching/health/readiness")
def coaching_health_readiness(workspace_id: str, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor", "viewer"})
    _require_active_coaching_subscription(workspace_id=workspace_id, session=session)
    api_key = str(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    base_url = str(os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
    provider_ok, provider_message = _check_llm_provider_reachability(base_url=base_url, api_key=api_key)
    lb_ok, lb_msg = lakebase_health()
    backend_health = {
        "ok": lb_ok,
        "message": lb_msg,
    }
    return {
        "ok": True,
        "workspace_id": workspace_id,
        "readiness": {
            "api_key_present": bool(api_key),
            "llm_key_present": bool(api_key),
            "provider_reachable": provider_ok,
            "provider_message": provider_message,
            "base_url": base_url,
            "backend_health": backend_health,
            "lakebase_ok": lb_ok,
            "lakebase_message": lb_msg,
            "ready": bool(api_key and provider_ok and lb_ok),
        },
    }


@app.post("/coaching/sow/validate-loop")
def coaching_validate_loop(req: CoachingValidateLoopRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin", "editor"})
    logger.info(
        "coaching_validate_loop_requested",
        extra={
            "actor": session.username,
            "role": session.role,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "auto_revise_once": req.auto_revise_once,
        },
    )
    intake = get_coaching_intake_submission(req.submission_id)
    if not intake:
        return {"ok": False, "message": "submission not found", "submission_id": req.submission_id}

    _require_active_coaching_subscription(
        workspace_id=req.workspace_id,
        session=session,
        email=str(intake.get("applicant_email") or "").strip().lower() or None,
    )

    safe_input_sow, _ = sanitize_generated_sow(req.sow)
    first_findings = validate_sow_payload(safe_input_sow)
    revised = None
    final_findings = first_findings

    if req.auto_revise_once and first_findings:
        revised = auto_revise_sow_once(safe_input_sow, first_findings)
        revised, _ = sanitize_generated_sow(revised)
        final_findings = validate_sow_payload(revised)

    final_sow = revised or safe_input_sow
    run_id = str(uuid4())
    save_coaching_generation_run(
        run_id=run_id,
        submission_id=req.submission_id,
        workspace_id=req.workspace_id,
        run_status="completed" if len(final_findings) == 0 else "needs_review",
        parsed_jobs=[],
        sow=final_sow,
        validation={
            "first_pass_findings": first_findings,
            "final_findings": final_findings,
            "auto_revised": bool(revised),
        },
        error_message=None,
        created_by=session.username,
    )

    logger.info(
        "coaching_validate_loop_completed",
        extra={
            "actor": session.username,
            "role": session.role,
            "workspace_id": req.workspace_id,
            "submission_id": req.submission_id,
            "run_id": run_id,
            "first_pass_findings_count": len(first_findings),
            "final_findings_count": len(final_findings),
            "auto_revised": bool(revised),
        },
    )
    return {
        "ok": True,
        "run_id": run_id,
        "submission_id": req.submission_id,
        "workspace_id": req.workspace_id,
        "auto_revised": bool(revised),
        "first_pass_findings": first_findings,
        "final_findings": final_findings,
        "sow": final_sow,
    }


@app.get("/admin/security/rate-limits")
def admin_rate_limits_get(session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    return {"ok": True, **rate_limit_policy_snapshot()}


@app.put("/admin/security/rate-limits")
def admin_rate_limits_update(payload: dict[str, Any], session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    updated = rate_limit_policy_update(payload)
    return {"ok": True, **updated}


@app.get("/admin/security/runtime-rate-limit-config")
def admin_runtime_rate_limit_config_get(session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    return runtime_rate_limit_snapshot()


@app.put("/admin/security/runtime-rate-limit-config")
def admin_runtime_rate_limit_config_update(payload: dict[str, Any], session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    return runtime_rate_limit_update(payload)


@app.get("/admin/security/webhook-alerts")
def admin_webhook_invalid_signature_alerts(limit: int = 50, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    alerts = INVALID_WEBHOOK_SIGNATURE_TRACKER.recent_alerts(limit=limit)
    return {"ok": True, "alerts": alerts, "total": len(alerts)}


@app.get("/admin/users")
def admin_users(session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    return {"users": list_users()}


@app.post("/admin/users")
def admin_upsert_user(req: UserUpsertRequest, session=Depends(get_current_session)) -> dict:
    assert_role(session, {"admin"})
    upsert_user(username=req.username, password=req.password, role=req.role, active=req.active)
    revoked = revoke_user_sessions(req.username) if not req.active else 0
    return {"ok": True, "revoked_sessions": revoked}

