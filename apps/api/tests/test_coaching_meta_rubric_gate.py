import coaching
from coaching import sow_generation_gate as gate


def test_meta_rubric_gate_preserves_initial_sow_when_score_is_below_threshold(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.delenv("COACHING_META_RUBRIC_MAX_REPROCESS_ATTEMPTS", raising=False)
    monkeypatch.delenv("COACHING_META_RUBRIC_ARCHETYPE_ORDER", raising=False)
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "initial"},
            "meta": {"strategy": {"project_strategy": {"archetype": "retail"}}},
        },
    )
    def _fake_eval(sow):
        title = str((sow or {}).get("project_title") or "")
        if title == "initial":
            return {"overall_score": 72}
        return {"overall_score": 88}

    monkeypatch.setattr(gate, "evaluate_sow_output", _fake_eval)

    out = gate.generate_sow_with_llm(intake={"applicant_name": "A"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    assert out["sow"]["project_title"] == "initial"
    assert gate_meta.get("reprocessed") is False
    assert gate_meta.get("met_threshold_final") is False
    assert int(gate_meta.get("final_overall_score") or 0) == 72
    assert int(gate_meta.get("max_reprocess_attempts") or 0) == 0
    assert isinstance(gate_meta.get("archetype_order"), list)


def test_meta_rubric_gate_skips_reprocess_when_initial_score_passes(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.delenv("COACHING_META_RUBRIC_MAX_REPROCESS_ATTEMPTS", raising=False)
    monkeypatch.delenv("COACHING_META_RUBRIC_ARCHETYPE_ORDER", raising=False)
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


def test_meta_rubric_gate_records_zero_reprocess_attempts(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "90")
    monkeypatch.setenv("COACHING_META_RUBRIC_MAX_REPROCESS_ATTEMPTS", "1")
    monkeypatch.delenv("COACHING_META_RUBRIC_ARCHETYPE_ORDER", raising=False)
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "initial"},
            "meta": {"strategy": {"project_strategy": {"archetype": "retail"}}},
        },
    )
    def _fake_eval(sow):
        title = str((sow or {}).get("project_title") or "")
        if title == "initial":
            return {"overall_score": 70}
        return {"overall_score": 95}

    monkeypatch.setattr(gate, "evaluate_sow_output", _fake_eval)

    out = gate.generate_sow_with_llm(intake={"applicant_name": "A"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    attempts = gate_meta.get("reprocess_attempts") or []
    assert len(attempts) == 0
    assert int(gate_meta.get("max_reprocess_attempts") or 0) == 0
    assert int(gate_meta.get("final_overall_score") or 0) == 70
    assert gate_meta.get("met_threshold_final") is False


def test_meta_rubric_gate_keeps_archetype_order_metadata_without_reprocessing(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.setenv("COACHING_META_RUBRIC_MAX_REPROCESS_ATTEMPTS", "2")
    monkeypatch.setenv("COACHING_META_RUBRIC_ARCHETYPE_ORDER", "finance,energy,retail,general")
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "initial"},
            "meta": {"strategy": {"project_strategy": {"archetype": "retail"}}},
        },
    )
    def _fake_eval(sow):
        title = str((sow or {}).get("project_title") or "")
        if title == "initial":
            return {"overall_score": 72}
        return {"overall_score": 90}

    monkeypatch.setattr(gate, "evaluate_sow_output", _fake_eval)

    out = gate.generate_sow_with_llm(intake={"applicant_name": "A"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    attempts = gate_meta.get("reprocess_attempts") or []
    assert attempts == []
    assert gate_meta.get("selected_archetype") == "retail"
    assert gate_meta.get("met_threshold_final") is False
    assert gate_meta.get("archetype_order") == ["finance", "energy", "retail", "general"]


def test_meta_rubric_gate_preserves_valid_openai_output_instead_of_swapping_in_scaffold(monkeypatch):
    monkeypatch.setenv("COACHING_META_RUBRIC_MIN_SCORE", "85")
    monkeypatch.delenv("COACHING_META_RUBRIC_MAX_REPROCESS_ATTEMPTS", raising=False)
    monkeypatch.delenv("COACHING_META_RUBRIC_ARCHETYPE_ORDER", raising=False)
    monkeypatch.setattr(
        gate,
        "_base_generate_sow_with_llm",
        lambda **kwargs: {
            "ok": True,
            "sow": {"project_title": "Video Game Performance Analytics Dashboard"},
            "meta": {
                "provider": "openai-compatible",
                "strategy": {"project_strategy": {"archetype": "general"}},
            },
        },
    )
    def _fake_eval(sow):
        title = str((sow or {}).get("project_title") or "")
        if title == "Video Game Performance Analytics Dashboard":
            return {"overall_score": 72}
        return {"overall_score": 91}

    monkeypatch.setattr(gate, "evaluate_sow_output", _fake_eval)

    out = gate.generate_sow_with_llm(intake={"applicant_name": "Chris"}, parsed_jobs=[])
    gate_meta = ((out.get("meta") or {}).get("meta_rubric_gate") or {})
    assert out["sow"]["project_title"] == "Video Game Performance Analytics Dashboard"
    assert gate_meta.get("status") == "evaluated_only_below_threshold"
    assert gate_meta.get("reprocess_attempts") == []
    assert int(gate_meta.get("final_overall_score") or 0) == 72


def test_package_export_uses_meta_rubric_gate_wrapper():
    assert coaching.generate_sow_with_llm is gate.generate_sow_with_llm
