from __future__ import annotations

import re
from typing import Any

import httpx

from .constants import COMMON_SKILLS, COMMON_DOMAINS, COMMON_TOOLS
from .constants import RESUME_TOOL_KEYWORDS, RESUME_DOMAIN_KEYWORDS, RESUME_PROJECT_KEYWORDS
from .sow_security import _validate_safe_url


def _plain_text_from_html(body: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", body, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_job_text(url: str, timeout: int = 8) -> dict[str, Any]:
    ok, reason = _validate_safe_url(url)
    if not ok:
        return {"ok": False, "url": url, "text": "", "error": f"Unsafe URL blocked ({reason})"}

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (OpenClaw CoachingBot)"})
            resp.raise_for_status()
            ctype = str(resp.headers.get("content-type") or "").lower()
            if ctype and not any(x in ctype for x in ["html", "text", "json", "xml"]):
                return {"ok": False, "url": url, "text": "", "error": f"Unsupported content type: {ctype}"}
            decoded = resp.text
            if "html" in ctype or "<html" in decoded[:400].lower():
                txt = _plain_text_from_html(decoded)
            else:
                txt = decoded
            return {"ok": True, "url": url, "text": txt[:30000], "error": None}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "url": url, "text": "", "error": f"HTTPError {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"ok": False, "url": url, "text": "", "error": f"RequestError {e}"}
    except Exception as e:
        return {"ok": False, "url": url, "text": "", "error": str(e)}


def extract_job_signals(text: str) -> dict[str, Any]:
    low = (text or "").lower()

    skills = sorted([s for s in COMMON_SKILLS if s in low])
    domains = sorted([d for d in COMMON_DOMAINS if d in low])
    tools = sorted([t for t in COMMON_TOOLS if t in low])

    seniority = "mid"
    if any(w in low for w in ["principal", "staff", "lead"]):
        seniority = "senior"
    elif any(w in low for w in ["senior", "sr.", "sr "]):
        seniority = "senior"
    elif any(w in low for w in ["entry", "junior", "associate"]):
        seniority = "junior"

    return {
        "skills": skills,
        "tools": tools,
        "domains": domains,
        "seniority": seniority,
    }


def extract_resume_signals(text: str) -> dict[str, Any]:
    raw = str(text or "")
    low = raw.lower()

    role_level = "mid"
    if any(token in low for token in ["principal", "staff", "architect", "head of", "director"]):
        role_level = "senior"
    elif any(token in low for token in ["senior", "sr ", "sr.", "lead"]):
        role_level = "senior"
    elif any(token in low for token in ["entry", "junior", "intern", "new grad", "associate"]):
        role_level = "junior"

    tools = sorted([tool for tool in RESUME_TOOL_KEYWORDS if tool in low])
    domains = sorted([domain for domain in RESUME_DOMAIN_KEYWORDS if domain in low])
    project_keywords = sorted([kw for kw in RESUME_PROJECT_KEYWORDS if kw in low])

    strengths: list[str] = []
    gaps: list[str] = []
    if {"python", "sql"}.issubset(set(tools)):
        strengths.append("Core analytics engineering stack (Python + SQL) evidenced")
    if any(t in tools for t in ["dbt", "airflow", "spark", "databricks"]):
        strengths.append("Modern data platform tooling experience")
    if not any(t in tools for t in ["aws", "azure", "gcp"]):
        gaps.append("Cloud platform depth not explicit (AWS/Azure/GCP)")
    if "data quality" not in project_keywords:
        gaps.append("Data quality/testing ownership not clearly stated")
    if len(project_keywords) < 3:
        gaps.append("Project experience keywords are sparse; add impact bullets with tooling and outcomes")

    years_match = re.findall(r"(\d{1,2})\+?\s+years", low)
    years_experience = max([int(x) for x in years_match], default=0)

    return {
        "role_level": role_level,
        "tools": tools,
        "domains": domains,
        "project_experience_keywords": project_keywords,
        "strengths": strengths,
        "gaps": gaps,
        "years_experience_hint": years_experience,
        "parse_strategy": "heuristic",
    }
