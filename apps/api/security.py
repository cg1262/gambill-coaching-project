from __future__ import annotations

from pathlib import Path
import re
from typing import Any


ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
DEFAULT_MAX_RESUME_BYTES = 5 * 1024 * 1024


_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)([a-z0-9._\-~+/]+=*)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s,;\]\}]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;\]\}]+)"),
    re.compile(r"(?i)(client_secret\s*[=:]\s*)([^\s,;\]\}]+)"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;\]\}]+)"),
]


PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
}


class FileValidationError(ValueError):
    pass



def validate_resume_metadata(
    filename: str,
    content_type: str | None,
    size_bytes: int,
    max_size_bytes: int = DEFAULT_MAX_RESUME_BYTES,
) -> dict[str, Any]:
    cleaned_name = Path(filename or "").name
    if cleaned_name in {"", ".", ".."}:
        raise FileValidationError("Filename is required")

    ext = Path(cleaned_name).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise FileValidationError(f"Unsupported resume file type: {ext or 'none'}")

    if size_bytes <= 0:
        raise FileValidationError("File is empty")
    if size_bytes > max_size_bytes:
        raise FileValidationError(f"File exceeds max size ({max_size_bytes} bytes)")

    ctype = (content_type or "").strip().lower()
    content_type_ok = (not ctype) or ctype in ALLOWED_RESUME_CONTENT_TYPES
    if not content_type_ok:
        raise FileValidationError(f"Unsupported content type: {ctype}")

    return {
        "filename": cleaned_name,
        "extension": ext,
        "size_bytes": size_bytes,
        "content_type": ctype,
        "max_size_bytes": max_size_bytes,
        "accepted": True,
    }



def build_safe_resume_path(base_dir: str | Path, workspace_id: str, filename: str) -> Path:
    base = Path(base_dir).resolve()
    safe_workspace = re.sub(r"[^a-zA-Z0-9_-]", "_", workspace_id or "workspace")
    safe_file = Path(filename or "resume").name
    target = (base / safe_workspace / safe_file).resolve()

    if base not in target.parents and target != base:
        raise FileValidationError("Unsafe file path detected")

    return target



def mask_secrets_in_text(text: str) -> str:
    masked = text or ""
    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub(r"\1***", masked)
    return masked



def mask_sensitive_dict(payload: dict[str, Any], secret_keys: set[str] | None = None) -> dict[str, Any]:
    secret_keys = secret_keys or {"token", "connection_string", "password", "client_secret", "api_key"}
    out: dict[str, Any] = {}
    for k, v in (payload or {}).items():
        key = str(k).lower()
        if key in secret_keys and v not in (None, ""):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = mask_sensitive_dict(v, secret_keys)
        elif isinstance(v, str):
            out[k] = mask_secrets_in_text(v)
        else:
            out[k] = v
    return out



def pii_hits(text: str) -> dict[str, int]:
    content = text or ""
    return {name: len(pattern.findall(content)) for name, pattern in PII_PATTERNS.items()}
