from coaching import build_sow_skeleton, compute_sow_quality_score, validate_sow_payload


def test_sprint10_validator_enforces_ingestion_and_acceptance_checks():
    sow = build_sow_skeleton(intake={"applicant_name": "Jordan", "preferences": {}}, parsed_jobs=[])
    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}
    assert "INGESTION_INSTRUCTIONS_MISSING" not in codes
    assert "MILESTONE_ACCEPTANCE_CHECKS_MISSING" not in codes


def test_sprint10_style_alignment_score_rewards_anchor_signals():
    sow = build_sow_skeleton(intake={"applicant_name": "Jordan", "preferences": {}}, parsed_jobs=[])
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    assert int(quality.get("style_alignment_score") or 0) >= 75
