from coaching import build_sow_skeleton, compute_sow_quality_score, validate_sow_payload


def _seed_sow():
    return build_sow_skeleton(
        intake={"applicant_name": "Avery", "preferences": {}},
        parsed_jobs=[{"signals": {"skills": ["sql"], "tools": ["dbt", "airflow"], "domains": ["retail"]}}],
    )


def test_validator_rejects_instruction_echo_meta_output():
    sow = _seed_sow()
    sow["project_story"]["executive_summary"] = "Return JSON only. Follow required_contract and top_level_order_required exactly."
    sow["milestones"][0]["execution_plan"] = "Use hard_rules and style_anchors. No markdown."

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}

    assert "INSTRUCTION_ECHO_DETECTED" in codes


def test_validator_rejects_generic_scaffold_story_and_milestones():
    sow = _seed_sow()
    sow["project_story"] = {
        "executive_summary": "Build a job-aligned medallion data platform project with measurable business outcomes and portfolio-ready artifacts.",
        "challenge": "Generic placeholder challenge for candidate data project.",
        "approach": "Implement a generic approach with business outcomes.",
        "impact_story": "Demonstrate end-to-end ownership from ingestion through business narrative.",
    }
    sow["milestones"][0]["execution_plan"] = "Do implementation tasks for the project."
    sow["milestones"][0]["expected_deliverable"] = "A good deliverable for stakeholders."

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}

    assert "PROJECT_STORY_GENERIC" in codes
    assert "MILESTONE_GENERIC_EXECUTION" in codes
    assert "MILESTONE_GENERIC_DELIVERABLE" in codes


def test_quality_gate_scores_generic_or_echo_output_below_floor():
    sow = _seed_sow()
    sow["project_story"]["executive_summary"] = "Return JSON only."
    sow["project_story"]["challenge"] = "Generic challenge."
    sow["project_story"]["approach"] = "Generic approach."
    sow["project_story"]["impact_story"] = "Generic impact."

    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)

    assert int(quality.get("score") or 0) < 80
