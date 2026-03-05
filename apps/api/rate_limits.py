from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int
    key_scope: str  # ip | user | workspace
    burst: int | None = None


@dataclass
class RateLimitPolicy:
    name: str
    rules: list[RateLimitRule]


class RateLimitExceeded(Exception):
    def __init__(self, *, policy: str, rule: str, retry_after_seconds: int):
        super().__init__(f"rate limit exceeded for {policy}:{rule}")
        self.policy = policy
        self.rule = rule
        self.retry_after_seconds = max(1, int(retry_after_seconds))


class _TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = float(max(1, capacity))
        self.refill_rate_per_sec = float(max(0.0001, refill_rate_per_sec))
        self.tokens = float(capacity)
        self.last_refill_ts = time.time()

    def consume(self, amount: float = 1.0, *, now: float | None = None) -> tuple[bool, int]:
        ts = float(now if now is not None else time.time())
        elapsed = max(0.0, ts - self.last_refill_ts)
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate_per_sec))
            self.last_refill_ts = ts
        if self.tokens >= amount:
            self.tokens -= amount
            return True, 0
        deficit = amount - self.tokens
        retry = int(deficit / self.refill_rate_per_sec) + 1
        return False, retry


class RateLimitStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: dict[str, _TokenBucket] = {}

    def reset(self) -> None:
        with self._lock:
            self._buckets = {}

    def check(self, *, policy: RateLimitPolicy, key_values: dict[str, str], now: float | None = None) -> None:
        with self._lock:
            for rule in policy.rules:
                scoped_value = str(key_values.get(rule.key_scope) or "unknown")
                bucket_key = f"{policy.name}:{rule.name}:{rule.key_scope}:{scoped_value}"
                capacity = int(rule.burst or rule.limit)
                refill_rate = float(rule.limit) / float(rule.window_seconds)
                bucket = self._buckets.get(bucket_key)
                if bucket is None:
                    bucket = _TokenBucket(capacity=capacity, refill_rate_per_sec=refill_rate)
                    self._buckets[bucket_key] = bucket
                allowed, retry_after = bucket.consume(now=now)
                if not allowed:
                    raise RateLimitExceeded(policy=policy.name, rule=rule.name, retry_after_seconds=retry_after)


# TODO: RATE_LIMIT_POLICIES and RATE_LIMIT_STORE are in-memory only.
# With WEB_CONCURRENCY > 1 (multiple uvicorn workers), each worker maintains
# a separate copy — rate limit counts are NOT shared across workers.
# A Redis or DB backend is required for production multi-worker deployments.
_POLICIES_LOCK = threading.RLock()

RATE_LIMIT_POLICIES_DEFAULT: dict[str, RateLimitPolicy] = {
    "auth": RateLimitPolicy(
        name="auth",
        rules=[
            RateLimitRule(name="auth_ip", limit=10, window_seconds=60, key_scope="ip", burst=20),
        ],
    ),
    "generation": RateLimitPolicy(
        name="generation",
        rules=[
            RateLimitRule(name="generation_user_10m", limit=5, window_seconds=600, key_scope="user"),
            RateLimitRule(name="generation_workspace_1h", limit=20, window_seconds=3600, key_scope="workspace"),
        ],
    ),
    "review_actions": RateLimitPolicy(
        name="review_actions",
        rules=[
            RateLimitRule(name="review_user_1m", limit=30, window_seconds=60, key_scope="user"),
        ],
    ),
    "exports": RateLimitPolicy(
        name="exports",
        rules=[
            RateLimitRule(name="exports_user_1h", limit=20, window_seconds=3600, key_scope="user"),
        ],
    ),
    "subscription": RateLimitPolicy(
        name="subscription",
        rules=[
            RateLimitRule(name="subscription_user_1m", limit=30, window_seconds=60, key_scope="user", burst=45),
            RateLimitRule(name="subscription_ip_1m", limit=60, window_seconds=60, key_scope="ip", burst=80),
        ],
    ),
}


def _get_rule(policy: RateLimitPolicy, name: str) -> RateLimitRule:
    """Look up a rule by name. Avoids fragile positional indexing."""
    for rule in policy.rules:
        if rule.name == name:
            return rule
    raise ValueError(f"Rule '{name}' not found in policy '{policy.name}'")


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except Exception:
        return default


def _apply_env_overrides(base: dict[str, RateLimitPolicy]) -> dict[str, RateLimitPolicy]:
    out = {
        name: RateLimitPolicy(name=policy.name, rules=[RateLimitRule(**asdict(rule)) for rule in policy.rules])
        for name, policy in base.items()
    }

    auth_ip = _get_rule(out["auth"], "auth_ip")
    auth_ip.limit = _env_int("RATE_LIMIT_AUTH_LIMIT_PER_MIN", auth_ip.limit)
    auth_ip.burst = _env_int("RATE_LIMIT_AUTH_BURST", int(auth_ip.burst or auth_ip.limit))

    gen_user = _get_rule(out["generation"], "generation_user_10m")
    gen_user.limit = _env_int("RATE_LIMIT_GENERATION_USER_LIMIT_PER_10M", gen_user.limit)

    gen_ws = _get_rule(out["generation"], "generation_workspace_1h")
    gen_ws.limit = _env_int("RATE_LIMIT_GENERATION_WORKSPACE_LIMIT_PER_HOUR", gen_ws.limit)

    review_user = _get_rule(out["review_actions"], "review_user_1m")
    review_user.limit = _env_int("RATE_LIMIT_REVIEW_ACTIONS_USER_LIMIT_PER_MIN", review_user.limit)

    exports_user = _get_rule(out["exports"], "exports_user_1h")
    exports_user.limit = _env_int("RATE_LIMIT_EXPORTS_USER_LIMIT_PER_HOUR", exports_user.limit)

    sub_user = _get_rule(out["subscription"], "subscription_user_1m")
    sub_user.limit = _env_int("RATE_LIMIT_SUBSCRIPTION_USER_LIMIT_PER_MIN", sub_user.limit)
    sub_user.burst = _env_int("RATE_LIMIT_SUBSCRIPTION_USER_BURST", int(sub_user.burst or sub_user.limit))

    sub_ip = _get_rule(out["subscription"], "subscription_ip_1m")
    sub_ip.limit = _env_int("RATE_LIMIT_SUBSCRIPTION_IP_LIMIT_PER_MIN", sub_ip.limit)
    sub_ip.burst = _env_int("RATE_LIMIT_SUBSCRIPTION_IP_BURST", int(sub_ip.burst or sub_ip.limit))

    return out


RATE_LIMIT_POLICIES = _apply_env_overrides(RATE_LIMIT_POLICIES_DEFAULT)
RATE_LIMIT_STORE = RateLimitStore()


def policy_snapshot() -> dict[str, Any]:
    with _POLICIES_LOCK:
        return {
            "backend": "in_memory_token_bucket",
            "admin_editable": True,
            "db_ready_shape": True,
            "policies": {
                name: {
                    "name": policy.name,
                    "rules": [asdict(rule) for rule in policy.rules],
                }
                for name, policy in RATE_LIMIT_POLICIES.items()
            },
        }


def policy_update(payload: dict[str, Any]) -> dict[str, Any]:
    policies = payload.get("policies") if isinstance(payload, dict) else None
    if not isinstance(policies, dict):
        return policy_snapshot()

    with _POLICIES_LOCK:
        for policy_name, entry in policies.items():
            if policy_name not in RATE_LIMIT_POLICIES or not isinstance(entry, dict):
                continue
            rules = entry.get("rules")
            if not isinstance(rules, list):
                continue
            current_policy = RATE_LIMIT_POLICIES[policy_name]
            for idx, rule in enumerate(rules):
                if idx >= len(current_policy.rules) or not isinstance(rule, dict):
                    continue
                if "limit" in rule:
                    try:
                        current_policy.rules[idx].limit = max(1, int(rule["limit"]))
                    except Exception:
                        pass
                if "window_seconds" in rule:
                    try:
                        current_policy.rules[idx].window_seconds = max(1, int(rule["window_seconds"]))
                    except Exception:
                        pass
                if "burst" in rule:
                    try:
                        burst_raw = rule["burst"]
                        current_policy.rules[idx].burst = None if burst_raw is None else max(1, int(burst_raw))
                    except Exception:
                        pass

    RATE_LIMIT_STORE.reset()
    return policy_snapshot()


def enforce_rate_limit(policy_name: str, *, ip: str | None = None, user: str | None = None, workspace: str | None = None) -> None:
    with _POLICIES_LOCK:
        policy = RATE_LIMIT_POLICIES.get(policy_name)
    if policy is None:
        return
    key_values = {
        "ip": str(ip or "unknown"),
        "user": str(user or "anonymous"),
        "workspace": str(workspace or "unknown"),
    }
    RATE_LIMIT_STORE.check(policy=policy, key_values=key_values)
