import coaching
from coaching import sow_generation_gate as gate


def test_meta_rubric_gate_reprocesses_when_initial_score_below_threshold(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "initial"},
            "meta": {"strategy": {"project_strategy": {"archetype": "retail"}}},
        },
    )
    monkeypatch.setattr(
        gate,
        "build_sow_skeleton",
        lambda intake, parsed_jobs, project_strategy=None: {"project_title": f"{(project_strategy or {}).get('archetype', 'general')}-candidate"},
    )

    def _fake_eval(sow):
        title = str((sow or {}).get("project_title") or "")
        if title == "initial":
            return {"overall_score": 72}
        if title.startswith("energy"):
            return {"overall_score": 88}
        return {"overall_score": 80}

    monkeypatch.setattr(gate, "evaluate_sow_output", _fake_eval)

    out = gate.generate_sow_with_llm(intake={"applicant_name": "A"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    assert out["sow"]["project_title"].startswith("energy")
    assert gate_meta.get("reprocessed") is True
    assert gate_meta.get("met_threshold_final") is True
    assert int(gate_meta.get("final_overall_score") or 0) >= 85


def test_meta_rubric_gate_skips_reprocess_when_initial_score_passes(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "initial-pass"},
            "meta": {"strategy": {"project_strategy": {"archetype": "general"}}},
        },
    )
    monkeypatch.setattr(gate, "evaluate_sow_output", lambda sow: {"overall_score": 91})

    out = gate.generate_sow_with_llm(intake={"applicant_name": "A"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    assert out["sow"]["project_title"] == "initial-pass"
    assert gate_meta.get("reprocessed") is False
    assert gate_meta.get("status") == "initial_pass"
    assert gate_meta.get("reprocess_attempts") == []


def test_package_export_uses_meta_rubric_gate_wrapper():
    assert coaching.generate_sow_with_llm is gate.generate_sow_with_llm
