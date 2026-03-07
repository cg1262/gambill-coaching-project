import json
from pathlib import Path

from coaching.sprint14_artifacts import build_seeded_artifact_bundle


BUNDLE_FILE = Path(__file__).parent / "fixtures" / "sprint14_seeded_artifacts_bundle.json"


def test_sprint14_seeded_artifacts_bundle_is_reviewable_and_quality_clean():
    generated = build_seeded_artifact_bundle()
    committed = json.loads(BUNDLE_FILE.read_text(encoding="utf-8"))

    assert committed["bundle_version"] == "2026-03-sprint14"
    assert committed["scenario_count"] == 3
    assert len(committed.get("artifacts") or []) == 3

    for artifact in committed["artifacts"]:
        quality = artifact.get("quality") or {}
        assert int(quality.get("major_deficiency_count") or 0) == 0
        assert int(quality.get("style_alignment_score") or 0) >= 75
        assert artifact.get("project_title")
        assert (artifact.get("sow") or {}).get("project_story")

    assert generated == committed
