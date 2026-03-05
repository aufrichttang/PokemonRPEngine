from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parent / "rules"


def _load_json(name: str) -> dict[str, Any]:
    path = RULES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def lore_rules() -> dict[str, Any]:
    return _load_json("lore_kernel_rules.json")


@lru_cache(maxsize=1)
def time_rules() -> dict[str, Any]:
    return _load_json("time_kernel_rules.json")


@lru_cache(maxsize=1)
def faction_rules() -> dict[str, Any]:
    return _load_json("faction_kernel_rules.json")


@lru_cache(maxsize=1)
def legacy_catalog() -> dict[str, list[str]]:
    raw = _load_json("legacy_tag_catalog.json")
    data = raw.get("keywords", {})
    return data if isinstance(data, dict) else {}

