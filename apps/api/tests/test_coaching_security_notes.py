from coaching import build_sow_skeleton, validate_sow_payload


def test_sow_skeleton_includes_affiliate_disclosure_and_trust_language():
    sow = build_sow_skeleton(
        intake={"applicant_name": "Candidate", "preferences": {}},
        parsed_jobs=[{"signals": {"skills": ["python"], "tools": ["dbt"], "domains": ["finance"]}}],
    )

    resource_plan = sow.get("resource_plan") or {}
    mentoring = sow.get("mentoring_cta") or {}
    assert resource_plan.get("affiliate_disclosure")
    assert resource_plan.get("trust_language")
    assert mentoring.get("trust_language")


def test_validate_sow_flags_missing_affiliate_and_trust_language():
    sow = {
        "project_title": "x",
        "business_outcome": {},
        "solution_architecture": {"medallion_plan": {"bronze": "a", "silver": "b", "gold": "c"}},
        "milestones": [{"name": "m1"}, {"name": "m2"}, {"name": "m3"}],
        "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
        "resource_plan": {"required": [{"url": "https://example.com"}], "recommended": [], "optional": []},
        "mentoring_cta": {"recommended_tier": "TBD", "reason": "test"},
    }

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}
    assert "AFFILIATE_DISCLOSURE_MISSING" in codes
    assert "TRUST_LANGUAGE_MISSING" in codes
