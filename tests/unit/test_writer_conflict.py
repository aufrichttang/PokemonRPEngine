from app.memory.writer import _is_conflict


def test_conflict_detection() -> None:
    existing = "我们见过面并交换了徽章。"
    candidate = "我们从未见过面，也没有交换徽章。"
    assert _is_conflict(existing, candidate) is True


def test_conflict_detection_false_when_same_polarity() -> None:
    existing = "我们见过面并交换了徽章。"
    candidate = "我们后来又见过面。"
    assert _is_conflict(existing, candidate) is False
