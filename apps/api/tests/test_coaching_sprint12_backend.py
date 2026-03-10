from coaching import build_sow_skeleton, validate_sow_payload, compute_sow_quality_score, build_quality_diagnostics


def _golden_intake(name: str, role_level: str, years: int, tools: list[str], domains: list[str], timeline_weeks: int = 6):
    return {
        "applicant_name": name,
        "preferences": {
            "timeline_weeks": timeline_weeks,
            "resume_parse_summary": {
                "role_level": role_level,
                "years_experience_hint": years,
                "parse_confidence": 82,
                "tools": tools,
                "domains": domains,
                "project_experience_keywords": ["medallion", "kpi", "data quality", "orchestration"],
            },
        },
    }


def test_sprint12_golden_globalmart_retail_style_acceptance():
    sow = build_sow_skeleton(
        intake=_golden_intake("Avery", "senior", 9, ["python", "sql", "dbt", "airflow", "aws", "power bi"], ["retail", "ecommerce"]),
        parsed_jobs=[{"signals": {"seniority": "senior", "skills": ["sql"], "tools": ["dbt"], "domains": ["retail"]}}],
    )
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-gold", submission_id="sub-gold-1")

    assert findings == []
    assert quality["style_alignment_score"] >= 80
    assert diagnostics["major_deficiency_count"] == 0


def test_sprint12_golden_voltstream_energy_style_acceptance():
    sow = build_sow_skeleton(
        intake=_golden_intake("Morgan", "mid", 6, ["python", "sql", "spark", "databricks", "azure"], ["energy", "telecom"]),
        parsed_jobs=[{"signals": {"seniority": "senior", "skills": ["spark"], "tools": ["databricks"], "domains": ["energy"]}}],
    )
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-gold", submission_id="sub-gold-2")

    assert findings == []
    assert quality["score"] >= 80
    assert diagnostics["major_deficiency_codes"] == []


def test_sprint12_golden_market_monitor_finance_style_acceptance():
    sow = build_sow_skeleton(
        intake=_golden_intake("Tafor", "mid", 5, ["python", "sql", "spark", "databricks", "azure"], ["finance"]),
        parsed_jobs=[{"signals": {"seniority": "mid", "skills": ["spark"], "tools": ["databricks"], "domains": ["finance"]}}],
    )
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-gold", submission_id="sub-gold-3")

    assert findings == []
    assert quality["score"] >= 80
    assert diagnostics["major_deficiency_codes"] == []


def test_sprint12_golden_foundational_candidate_still_contract_clean():
    sow = build_sow_skeleton(
        intake=_golden_intake("Jordan", "junior", 1, ["python", "sql"], ["healthcare"], timeline_weeks=10),
        parsed_jobs=[{"signals": {"seniority": "mid", "skills": ["sql"], "tools": ["airflow"], "domains": ["healthcare"]}}],
    )
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)

    scope = ((sow.get("candidate_profile") or {}).get("role_scope_assessment") or {})
    assert scope.get("scope_difficulty") == "foundational"
    assert int(scope.get("suggested_timeline_weeks") or 0) >= 6
    assert findings == []
    assert quality["style_alignment_score"] >= 80


def test_sprint12_scope_timeline_mapping_is_deterministic_and_tie_stable():
    intake = _golden_intake("Casey", "mid", 7, ["python", "sql", "dbt", "airflow", "aws"], ["finance"], timeline_weeks=7)
    parsed_jobs = [
        {"signals": {"seniority": "senior"}},
        {"signals": {"seniority": "mid"}},
        {"signals": {"seniority": "senior"}},
        {"signals": {"seniority": "mid"}},
    ]

    first = ((build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs).get("candidate_profile") or {}).get("role_scope_assessment") or {})
    second = ((build_sow_skeleton(intake=intake, parsed_jobs=list(reversed(parsed_jobs))).get("candidate_profile") or {}).get("role_scope_assessment") or {})

    assert first.get("target_role_level") == second.get("target_role_level")
    assert first.get("suggested_timeline_weeks") == second.get("suggested_timeline_weeks")


def test_sprint12_quality_diagnostics_exposes_regenerate_payload_contract():
    sow = build_sow_skeleton(intake=_golden_intake("Riley", "mid", 5, ["python", "sql", "dbt"], ["finance"]), parsed_jobs=[])
    sow["milestones"][0]["acceptance_checks"] = ["looks good"]

    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-12", submission_id="sub-12")

    payload = diagnostics.get("regenerate_payload") or {}
    assert payload.get("endpoint") == "/coaching/sow/generate"
    assert payload.get("method") == "POST"
    assert payload.get("body", {}).get("regenerate_with_improvements") is True
    assert payload.get("body", {}).get("workspace_id") == "ws-12"
    assert payload.get("body", {}).get("submission_id") == "sub-12"
    assert diagnostics.get("major_deficiency_count", 0) >= 1
