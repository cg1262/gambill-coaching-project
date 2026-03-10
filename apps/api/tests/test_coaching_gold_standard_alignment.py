from coaching import build_sow_skeleton, validate_sow_payload


def _intake(name: str, role_level: str, tools: list[str], domains: list[str], keywords: list[str]):
    return {
        "applicant_name": name,
        "preferences": {
            "timeline_weeks": 6,
            "resume_parse_summary": {
                "role_level": role_level,
                "years_experience_hint": 5,
                "parse_confidence": 84,
                "tools": tools,
                "domains": domains,
                "project_experience_keywords": keywords,
            },
        },
    }


def test_gold_standard_retail_shape_has_charter_depth_and_retail_story():
    sow = build_sow_skeleton(
        intake=_intake(
            "Taylor",
            "junior",
            ["python", "sql", "databricks", "power bi"],
            ["retail", "ecommerce"],
            ["medallion", "dashboard", "data modeling", "inventory"],
        ),
        parsed_jobs=[{"signals": {"seniority": "junior", "tools": ["power bi"], "domains": ["retail"]}}],
    )

    findings = validate_sow_payload(sow)
    charter = (sow.get("project_charter") or {}).get("sections") or {}
    roi = sow.get("roi_dashboard_requirements") or {}
    story_text = " ".join(
        [
            str(sow.get("project_title") or ""),
            str((sow.get("project_story") or {}).get("executive_summary") or ""),
            str((sow.get("business_outcome") or {}).get("problem_statement") or ""),
        ]
    ).lower()
    source_names = {str(src.get("name") or "") for src in ((sow.get("business_outcome") or {}).get("data_sources") or [])}

    assert charter.get("prerequisites_resources", {}).get("summary")
    assert charter.get("technical_architecture", {}).get("ingestion")
    assert len(charter.get("implementation_plan", {}).get("milestones") or []) >= 3
    assert len(roi.get("business_questions") or []) >= 3
    assert len(roi.get("visual_requirements") or []) >= 2
    assert "Sample Superstore Sales Dataset" in source_names
    assert "globalmart" in story_text or "retail" in story_text
    assert "blueorbit" not in story_text
    assert "home services" not in story_text
    assert findings == []



def test_gold_standard_energy_shape_selects_public_api_sources_and_energy_story():
    sow = build_sow_skeleton(
        intake=_intake(
            "Morgan",
            "mid",
            ["python", "sql", "spark", "databricks"],
            ["energy"],
            ["api", "streaming", "orchestration", "weather", "telemetry"],
        ),
        parsed_jobs=[{"signals": {"seniority": "mid", "tools": ["databricks"], "domains": ["energy"]}}],
    )

    findings = validate_sow_payload(sow)
    story_text = " ".join(
        [
            str(sow.get("project_title") or ""),
            str((sow.get("project_story") or {}).get("executive_summary") or ""),
            str((sow.get("business_outcome") or {}).get("problem_statement") or ""),
        ]
    ).lower()
    source_names = {str(src.get("name") or "") for src in ((sow.get("business_outcome") or {}).get("data_sources") or [])}

    assert "Open Charge Map API" in source_names
    assert "OpenWeather One Call API" in source_names
    assert "voltstream" in story_text or "resilience" in story_text
    assert "northbeam outfitters" not in story_text
    assert "globalmart" not in story_text
    assert findings == []



def test_gold_standard_finance_shape_selects_market_sources_and_alert_story():
    sow = build_sow_skeleton(
        intake=_intake(
            "Tafor",
            "mid",
            ["python", "sql", "spark", "databricks"],
            ["finance"],
            ["api", "crypto", "market", "latency", "donation"],
        ),
        parsed_jobs=[{"signals": {"seniority": "mid", "tools": ["databricks"], "domains": ["finance"]}}],
    )

    findings = validate_sow_payload(sow)
    story_text = " ".join(
        [
            str(sow.get("project_title") or ""),
            str((sow.get("project_story") or {}).get("executive_summary") or ""),
            str((sow.get("business_outcome") or {}).get("problem_statement") or ""),
        ]
    ).lower()
    source_names = {str(src.get("name") or "") for src in ((sow.get("business_outcome") or {}).get("data_sources") or [])}
    roi = sow.get("roi_dashboard_requirements") or {}

    assert "CoinGecko Simple Price API" in source_names
    assert "CoinGecko Markets API" in source_names
    assert "donation velocity" in story_text or "liquidation" in story_text or "coingecko" in story_text
    assert "globalmart" not in story_text
    assert "voltstream" not in story_text
    assert any("latency" in str(q).lower() for q in (roi.get("business_questions") or []))
    assert findings == []

def test_project_strategy_hint_can_steer_fallback_archetype():
    sow = build_sow_skeleton(
        intake=_intake(
            "Casey",
            "mid",
            ["python", "sql"],
            ["public sector"],
            ["dashboard", "orchestration"],
        ),
        parsed_jobs=[],
        project_strategy={
            "archetype": "finance",
            "recommended_source_names": ["CoinGecko Simple Price API", "CoinGecko Markets API"],
            "dashboard_questions": [
                "What is the current pipeline latency in seconds behind the live market?",
                "Which assets or market events meet the alert threshold right now?",
                "How much compute time is being used relative to the monitoring value created?",
            ],
            "candidate_fit_summary": "Candidate wants a real-time API ingestion project with alerting and KPI storytelling.",
        },
    )

    findings = validate_sow_payload(sow)
    source_names = {str(src.get("name") or "") for src in ((sow.get("business_outcome") or {}).get("data_sources") or [])}
    assert "Global Giving Network Market & Donation Velocity Monitor" in str(sow.get("project_title") or "")
    assert "CoinGecko Simple Price API" in source_names
    assert findings == []