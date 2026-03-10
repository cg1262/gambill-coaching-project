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


def test_validator_rejects_legacy_story_marker_reuse():
    sow = _seed_sow()
    sow["project_title"] = "Avery - Northbeam Analytics Program"
    sow["project_story"]["executive_summary"] = "Northbeam Outfitters needs a modern data platform."

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}

    assert "LEGACY_STORY_REUSE_DETECTED" in codes


def test_validator_rejects_domain_source_and_kpi_mismatch():
    sow = _seed_sow()
    sow["project_strategy"] = {"archetype": "energy"}
    sow["business_outcome"]["data_sources"] = [
        {
            "name": "Sample Superstore Sales Dataset",
            "url": "https://www.kaggle.com/datasets/vivek468/superstore-dataset-final",
            "ingestion_doc_url": "https://www.kaggle.com/docs/api",
            "selection_rationale": "Retail sample data for sales analysis",
            "ingestion_instructions": "Load CSV daily into bronze with metadata.",
        }
    ]
    sow["roi_dashboard_requirements"]["required_measures"] = ["gross_margin", "basket_size"]
    sow["roi_dashboard_requirements"]["business_questions"] = ["Which stores have the highest basket size by month?"]

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}

    assert "DOMAIN_SOURCE_MISMATCH" in codes
    assert "DOMAIN_KPI_MISMATCH" in codes
