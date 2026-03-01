from probabilistic import gate_findings, confidence_to_color


def test_gate_findings_filters_low_confidence_and_invalid():
    raw = [
        {"object_name": "a", "dependency_type": "code_ref", "confidence": 92, "rationale": "ok"},
        {"object_name": "b", "dependency_type": "code_ref", "confidence": 40, "rationale": "low"},
        {"object_name": "c", "dependency_type": "bad_type", "confidence": 99, "rationale": "invalid"},
    ]
    approved = gate_findings(raw, min_confidence=80)
    assert len(approved) == 1
    assert approved[0].object_name == "a"


def test_confidence_color_bands():
    assert confidence_to_color(80) == "red"
    assert confidence_to_color(90) == "yellow"
    assert confidence_to_color(99) == "green"
