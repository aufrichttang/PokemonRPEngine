from __future__ import annotations

import re

from app.memory.schemas import QueryItem, QueryPlan, QueryType

TIME_REFS = ["之前", "那天", "上次", "昨晚", "第一次", "后来", "当时", "曾经"]
LOCATION_SUFFIXES = ("市", "镇", "村", "路", "街", "馆", "中心", "研究所", "道馆")


def build_query_plan(user_text: str) -> QueryPlan:
    text = user_text.strip()
    queries: list[QueryItem] = []

    quoted = re.findall(r'["“](.+?)["”]|《(.+?)》|「(.+?)」', text)
    for match in quoted:
        entity = "".join([m for m in match if m])
        if entity:
            queries.append(QueryItem(type=QueryType.actors, q=entity))

    words = re.findall(r"[A-Za-z][A-Za-z\-]+|[\u4e00-\u9fff]{2,}", text)
    for w in words[:12]:
        if w.endswith(LOCATION_SUFFIXES):
            queries.append(QueryItem(type=QueryType.locations, q=w))
        elif w in {"精灵球", "宝可梦图鉴", "徽章", "技能机", "药水"}:
            queries.append(QueryItem(type=QueryType.items, q=w))

    if any(token in text for token in ["冲突", "矛盾", "不一致", "谎言", "误会"]):
        queries.append(QueryItem(type=QueryType.conflict, q=text[:40]))

    if any(token in text for token in TIME_REFS):
        queries.append(QueryItem(type=QueryType.time_ref, q="回溯历史事件"))

    snippet = (text[:50] + " " + text[-50:]).strip()
    if snippet:
        queries.append(QueryItem(type=QueryType.keywords, q=snippet))

    uniq: list[QueryItem] = []
    seen: set[tuple[str, str]] = set()
    for q in queries:
        key = (q.type.value, q.q)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(q)

    if len(uniq) < 3:
        uniq.append(QueryItem(type=QueryType.keywords, q=text[:80]))
    return QueryPlan(queries=uniq[:6])
