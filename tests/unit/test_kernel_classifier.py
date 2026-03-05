from __future__ import annotations

from app.kernels.event_classifier import classify_event_metadata, infer_legacy_tags


def test_infer_legacy_tags_detects_galactic() -> None:
    tags = infer_legacy_tags(text="我们在银河队遗址找到了古代日志")
    assert "legacy_team_galactic" in tags


def test_classify_event_metadata_fixed() -> None:
    meta = classify_event_metadata(
        text="联盟确认封印已稳定，城市恢复供电。",
        canon_level="confirmed",
        source_trust=0.9,
        conflict_score=10,
    )
    assert meta["time_class"] == "fixed"
    assert meta["source_trust"] == 0.9
    assert meta["witness_count"] >= 1


def test_classify_event_metadata_echo() -> None:
    meta = classify_event_metadata(
        text="我在梦里听见封印回响，像是过去的幻视。",
        canon_level="pending",
    )
    assert meta["time_class"] == "echo"

