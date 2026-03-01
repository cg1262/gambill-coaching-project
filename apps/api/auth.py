from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any

from fastapi import Header, HTTPException


@dataclass
class Session:
    username: str
    role: str
    expires_at: datetime


_SESSIONS: dict[str, Session] = {}
_MAX_SESSIONS = 5000


def _prune_expired_sessions() -> None:
    now = datetime.now(timezone.utc)
    expired = [t for t, s in _SESSIONS.items() if s.expires_at < now]
    for t in expired:
        _SESSIONS.pop(t, None)


def issue_token(username: str, role: str, ttl_hours: int = 12) -> str:
    _prune_expired_sessions()
    if len(_SESSIONS) >= _MAX_SESSIONS:
        # best-effort guard against unbounded growth
        oldest_token = sorted(_SESSIONS.items(), key=lambda kv: kv[1].expires_at)[0][0]
        _SESSIONS.pop(oldest_token, None)

    token = token_urlsafe(32)
    _SESSIONS[token] = Session(
        username=username,
        role=role,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    return token


def validate_token(token: str) -> Session | None:
    session = _SESSIONS.get(token)
    if not session:
        return None
    if session.expires_at < datetime.now(timezone.utc):
        _SESSIONS.pop(token, None)
        return None
    return session


def parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    token = parse_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    session = validate_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return session.username


def get_current_session(authorization: str | None = Header(default=None)) -> Session:
    token = parse_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    session = validate_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return session


def assert_role(session: Session, allowed_roles: set[str]) -> None:
    if session.role.lower() not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient role")


def refresh_token(authorization: str | None = Header(default=None), ttl_hours: int = 12) -> dict[str, Any]:
    token = parse_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    session = validate_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    new_token = issue_token(session.username, session.role, ttl_hours=ttl_hours)
    _SESSIONS.pop(token, None)
    return {"ok": True, "token": new_token, "username": session.username, "role": session.role}


def revoke_token(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = parse_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    _SESSIONS.pop(token, None)
    return {"ok": True}


def revoke_user_sessions(username: str) -> int:
    to_remove = [t for t, s in _SESSIONS.items() if s.username == username]
    for t in to_remove:
        _SESSIONS.pop(t, None)
    return len(to_remove)


def session_stats() -> dict[str, Any]:
    _prune_expired_sessions()
    return {"active_sessions": len(_SESSIONS), "max_sessions": _MAX_SESSIONS}


def whoami(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token = parse_bearer_token(authorization)
    session = validate_token(token) if token else None
    return {
        "authenticated": bool(session),
        "username": session.username if session else None,
        "role": session.role if session else None,
    }
