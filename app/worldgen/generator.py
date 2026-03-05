from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CanonPokemon

TYPE_POOL = [
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
]

EARLY_GYM_TYPES = ["normal", "grass", "water", "electric", "bug", "flying"]
MID_GYM_TYPES = ["fire", "poison", "ground", "rock", "psychic", "fighting", "fairy"]
LATE_GYM_TYPES = ["ice", "ghost", "dragon", "dark", "steel"]

THEME_POOL = [
    "海岬航线",
    "古代遗迹",
    "雪岭列岛",
    "机械都会",
    "密林秘境",
    "火山走廊",
    "高原峡谷",
    "薄雾沼泽",
    "极光海湾",
    "群峰矿脉",
]

CONTINENT_FIRST = ["苍", "澄", "岚", "绯", "霁", "曜", "星", "澜", "玄", "碧", "霜", "辉"]
CONTINENT_SECOND = ["羽", "渊", "岳", "岬", "潮", "穹", "湾", "陵", "川", "原", "泽", "辉"]
CONTINENT_SUFFIX = ["地区", "联邦", "大陆", "群岛"]
CITY_SUFFIX = ["镇", "市", "港", "原", "岬", "谷", "城"]

TYPE_CITY_PREFIX: dict[str, list[str]] = {
    "fire": ["熔", "赤", "焰", "炉"],
    "water": ["潮", "澄", "湛", "渔"],
    "electric": ["霓", "雷", "磁", "机"],
    "grass": ["森", "藤", "芽", "青"],
    "ice": ["霜", "雪", "冰", "极"],
    "fighting": ["武", "拳", "烈", "斗"],
    "poison": ["雾", "瘴", "紫", "泽"],
    "ground": ["砾", "砂", "岩", "峁"],
    "flying": ["岚", "风", "羽", "空"],
    "psychic": ["幻", "念", "星", "梦"],
    "bug": ["茧", "茸", "虫", "栖"],
    "rock": ["砺", "矿", "峤", "岩"],
    "ghost": ["幽", "冥", "影", "夜"],
    "dragon": ["龙", "苍", "岚", "天"],
    "dark": ["朔", "暗", "夜", "影"],
    "steel": ["铸", "钢", "锻", "铁"],
    "fairy": ["绮", "月", "虹", "花"],
    "normal": ["常", "牧", "栖", "野"],
}

THEME_TO_BIOME = {
    "海岬航线": "coast",
    "古代遗迹": "ruin",
    "雪岭列岛": "snow",
    "机械都会": "urban",
    "密林秘境": "forest",
    "火山走廊": "volcanic",
    "高原峡谷": "highland",
    "薄雾沼泽": "swamp",
    "极光海湾": "aurora",
    "群峰矿脉": "mountain",
}

BANNED_PLACE_NAMES = {
    "真新镇",
    "常磐市",
    "尼比市",
    "华蓝市",
    "枯叶市",
    "玉虹市",
    "浅红市",
    "红莲镇",
    "紫苑镇",
}

LEADER_FAMILY = ["神原", "月城", "白石", "风间", "桐生", "雾岛", "天城", "北原", "叶山", "九条", "黑泽", "浅井"]
LEADER_GIVEN = ["澪", "凛", "葵", "岚", "曜", "焰", "澄", "悠", "凪", "枫", "琉", "祈"]

STARTER_REASON = {
    "grass": "草系稳健成长，适合建立长期节奏与场面控制。",
    "fire": "火系爆发强劲，适合高压推进与关键突破。",
    "water": "水系均衡可靠，适合应对复杂战况与长线探索。",
}
STARTER_POOL = {
    "grass": [
        "bulbasaur",
        "chikorita",
        "treecko",
        "turtwig",
        "snivy",
        "chespin",
        "rowlet",
        "grookey",
        "sprigatito",
    ],
    "fire": [
        "charmander",
        "cyndaquil",
        "torchic",
        "chimchar",
        "tepig",
        "fennekin",
        "litten",
        "scorbunny",
        "fuecoco",
    ],
    "water": [
        "squirtle",
        "totodile",
        "mudkip",
        "piplup",
        "oshawott",
        "froakie",
        "popplio",
        "sobble",
        "quaxly",
    ],
}
STARTER_FALLBACK = {
    "grass": {"slug_id": "bulbasaur", "name_zh": "妙蛙种子", "types": ["grass", "poison"]},
    "fire": {"slug_id": "charmander", "name_zh": "小火龙", "types": ["fire"]},
    "water": {"slug_id": "squirtle", "name_zh": "杰尼龟", "types": ["water"]},
}

LEGENDARY_PACKS: list[list[dict[str, str]]] = [
    [
        {"slug_id": "rayquaza", "name_zh": "裂空座", "domain": "天穹"},
        {"slug_id": "kyogre", "name_zh": "盖欧卡", "domain": "海渊"},
        {"slug_id": "groudon", "name_zh": "固拉多", "domain": "地核"},
        {"slug_id": "jirachi", "name_zh": "基拉祈", "domain": "愿星"},
    ],
    [
        {"slug_id": "dialga", "name_zh": "帝牙卢卡", "domain": "时间"},
        {"slug_id": "palkia", "name_zh": "帕路奇亚", "domain": "空间"},
        {"slug_id": "giratina", "name_zh": "骑拉帝纳", "domain": "反转"},
        {"slug_id": "arceus", "name_zh": "阿尔宙斯", "domain": "创世"},
    ],
    [
        {"slug_id": "reshiram", "name_zh": "莱希拉姆", "domain": "真实"},
        {"slug_id": "zekrom", "name_zh": "捷克罗姆", "domain": "理想"},
        {"slug_id": "kyurem", "name_zh": "酋雷姆", "domain": "极寒"},
        {"slug_id": "keldeo", "name_zh": "凯路迪欧", "domain": "誓剑"},
    ],
    [
        {"slug_id": "solgaleo", "name_zh": "索尔迦雷欧", "domain": "日轮"},
        {"slug_id": "lunala", "name_zh": "露奈雅拉", "domain": "月影"},
        {"slug_id": "necrozma", "name_zh": "奈克洛兹玛", "domain": "光蚀"},
        {"slug_id": "zygarde", "name_zh": "基格尔德", "domain": "秩序"},
    ],
]


@dataclass
class GeneratedWorld:
    seed: str
    world_profile: dict[str, Any]
    starter_options: list[dict[str, Any]]
    gym_plan: list[dict[str, Any]]
    battle_mode: str = "fast"


def normalize_seed(seed: str | None) -> str:
    if seed and seed.strip():
        cleaned = seed.strip().replace("\n", " ")[:64]
        return cleaned
    return uuid.uuid4().hex[:16]


def _stable_rng(seed: str, canon_gen: int, canon_game: str | None) -> random.Random:
    material = f"{seed}|{canon_gen}|{canon_game or '-'}"
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return random.Random(value)


def _build_continent_name(rng: random.Random) -> str:
    while True:
        name = f"{rng.choice(CONTINENT_FIRST)}{rng.choice(CONTINENT_SECOND)}{rng.choice(CONTINENT_SUFFIX)}"
        if name not in BANNED_PLACE_NAMES:
            return name


def _compose_city_name(rng: random.Random, *, type_hint: str | None, used: set[str]) -> str:
    prefixes = TYPE_CITY_PREFIX.get(type_hint or "", TYPE_CITY_PREFIX["normal"])
    bridge_pool = ["", "新", "南", "北", "东", "西", "云", "星", "月"]
    for _ in range(120):
        name = f"{rng.choice(prefixes)}{rng.choice(bridge_pool)}{rng.choice(CITY_SUFFIX)}"
        name = name.replace("  ", "").replace(" ", "")
        if name in BANNED_PLACE_NAMES or name in used:
            continue
        if len(name) < 2:
            continue
        used.add(name)
        return name
    fallback = f"{rng.choice(CONTINENT_FIRST)}{rng.choice(CITY_SUFFIX)}"
    used.add(fallback)
    return fallback


def _best_zh_name(name_zh: str | None, aliases: list[str] | None, name_en: str | None, slug: str) -> str:
    def has_han(value: str) -> bool:
        return any("\u4e00" <= ch <= "\u9fff" for ch in value)

    def has_kana_or_hangul(value: str) -> bool:
        return any(("\u3040" <= ch <= "\u30ff") or ("\uac00" <= ch <= "\ud7af") for ch in value)

    if isinstance(name_zh, str) and name_zh.strip():
        candidate = name_zh.strip()
        if has_han(candidate) and not has_kana_or_hangul(candidate):
            return candidate
    if isinstance(aliases, list):
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            candidate = alias.strip()
            if candidate and has_han(candidate) and not has_kana_or_hangul(candidate):
                return candidate
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            candidate = alias.strip()
            if candidate and has_han(candidate):
                return candidate
    if isinstance(name_zh, str) and name_zh.strip():
        return name_zh.strip()
    if isinstance(name_en, str) and name_en.strip():
        return name_en.strip()
    return slug


def _pick_starters(db: Session, rng: random.Random, canon_gen: int) -> list[dict[str, Any]]:
    rows = list(db.execute(select(CanonPokemon).where(CanonPokemon.generation <= canon_gen)).scalars().all())
    by_slug = {row.slug_id: row for row in rows}

    selected: list[dict[str, Any]] = []
    used_slugs: set[str] = set()

    for key in ("grass", "fire", "water"):
        candidates = [by_slug[s] for s in STARTER_POOL[key] if s in by_slug]
        pick: CanonPokemon | None = None
        if candidates:
            trials = candidates[:]
            rng.shuffle(trials)
            for cand in trials:
                if cand.slug_id not in used_slugs:
                    pick = cand
                    break
        if not pick:
            fallback_slug = str(STARTER_FALLBACK[key]["slug_id"])
            pick = by_slug.get(fallback_slug)
        if not pick and rows:
            pick = rows[rng.randrange(0, len(rows))]

        if pick:
            used_slugs.add(pick.slug_id)
            selected.append(
                {
                    "slug_id": pick.slug_id,
                    "name_zh": _best_zh_name(pick.name_zh, pick.aliases, pick.name_en, pick.slug_id),
                    "types": pick.types,
                    "reason": STARTER_REASON[key],
                }
            )
            continue

        fallback_entry = STARTER_FALLBACK[key]
        selected.append(
            {
                "slug_id": fallback_entry["slug_id"],
                "name_zh": fallback_entry["name_zh"],
                "types": fallback_entry["types"],
                "reason": STARTER_REASON[key],
            }
        )

    return selected


def _generate_gym_plan(rng: random.Random) -> list[dict[str, Any]]:
    early = rng.sample(EARLY_GYM_TYPES, 3)
    mid_pool = [t for t in MID_GYM_TYPES if t not in early]
    mid = rng.sample(mid_pool, 3)
    late_pool = [t for t in LATE_GYM_TYPES if t not in early and t not in mid]
    late = rng.sample(late_pool, 2)

    gym_types = [*early, *mid, *late]
    used_cities: set[str] = set()

    plan: list[dict[str, Any]] = []
    for idx, gym_type in enumerate(gym_types, start=1):
        city_name = _compose_city_name(rng, type_hint=gym_type, used=used_cities)
        leader_name = f"{rng.choice(LEADER_FAMILY)}{rng.choice(LEADER_GIVEN)}"
        plan.append(
            {
                "index": idx,
                "city_name": city_name,
                "gym_type": gym_type,
                "leader_name": leader_name,
                "difficulty_tier": idx,
                "cleared": False,
            }
        )
    return plan


def _build_legendary_web(rng: random.Random) -> dict[str, Any]:
    nodes = [dict(x) for x in rng.choice(LEGENDARY_PACKS)]
    stances = ["守护", "失衡", "沉睡", "观望"]
    risk_levels = ["中", "高", "极高", "高"]
    for idx, node in enumerate(nodes, start=1):
        node["index"] = idx
        node["stance"] = stances[idx - 1]
        node["risk_level"] = risk_levels[idx - 1]
        node["seal_fragment"] = f"{node['name_zh']}之印-{idx}"

    return {
        "nodes": nodes,
        "core_conflict": "封印链断裂导致神兽权柄相互牵引，地区秩序濒临崩坏。",
        "factions": ["联盟远征队", "遗迹守望会", "灰烬议会"],
    }


def _build_story_blueprint(
    *,
    continent_name: str,
    start_town: str,
    gym_plan: list[dict[str, Any]],
    legendary_web: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    nodes = legendary_web.get("nodes", []) if isinstance(legendary_web, dict) else []
    legends = [str(x.get("name_zh", "神兽")) for x in nodes if isinstance(x, dict)]
    while len(legends) < 4:
        legends.append("神兽")

    chapter_defs = [
        {
            "title": "起始火花",
            "objective": f"在{start_town}完成启程并锁定第一枚徽章线索。",
            "conflict": f"{legends[0]}的异常波动撕开了最初的平静。",
            "sacrifice": "你必须放弃安稳生活，公开站上危险前线。",
            "reward": "获得联盟临时执照与首个关键情报。",
        },
        {
            "title": "馆城试锋",
            "objective": f"前往{gym_plan[0]['city_name']}挑战首馆并调查封印碎片。",
            "conflict": f"{legends[1]}的信徒开始阻挠馆战秩序。",
            "sacrifice": "旧同伴受伤离队，你必须独自扛起前线压力。",
            "reward": "拿到第一枚徽章与第一片神兽封印。",
        },
        {
            "title": "雾港失守",
            "objective": f"在{gym_plan[1]['city_name']}阻止灰烬议会夺取能源核心。",
            "conflict": f"{legends[2]}被强行唤醒，引发局部灾厄。",
            "sacrifice": "你需牺牲一条关键补给线换取平民撤离。",
            "reward": "解锁远征队协作权限。",
        },
        {
            "title": "裂界回响",
            "objective": f"赶赴{gym_plan[2]['city_name']}修复失控封印阵。",
            "conflict": f"{legends[0]}与{legends[1]}权柄发生对冲。",
            "sacrifice": "必须放弃短期胜利，保全更大范围秩序。",
            "reward": "获得第二组封印坐标。",
        },
        {
            "title": "盟约断裂",
            "objective": f"在{gym_plan[3]['city_name']}重建联盟与守望会同盟。",
            "conflict": "内部背叛导致作战计划全面暴露。",
            "sacrifice": "你要亲手切断一段旧羁绊以止损。",
            "reward": "主线伙伴觉醒，战术上限提升。",
        },
        {
            "title": "群星坠夜",
            "objective": f"穿越{gym_plan[4]['city_name']}至核心遗迹，集齐四枚封印。",
            "conflict": f"{legends[3]}的沉睡被迫终止，终局计时开始。",
            "sacrifice": "你必须接受无法回头的代价，换取终局资格。",
            "reward": "开启最终仪式与全域传送权限。",
        },
        {
            "title": "灰烬终线",
            "objective": f"在{gym_plan[5]['city_name']}与灰烬议会正面决战。",
            "conflict": "敌方以人质与封印同毁进行要挟。",
            "sacrifice": "你必须在挚爱与大局之间做出残酷抉择。",
            "reward": "夺回主导权并重启最终封印链。",
        },
        {
            "title": "黎明誓约",
            "objective": f"于{continent_name}中央圣域完成多神兽共鸣封印。",
            "conflict": f"{legends[0]}、{legends[1]}、{legends[2]}权柄同时暴走。",
            "sacrifice": "终局必须付出不可逆代价，才能换来新秩序。",
            "reward": "世界线稳定，进入冠军与情感结局分歧。",
        },
    ]

    acts: list[dict[str, Any]] = [
        {"act_index": 1, "title": "起势", "tone": "热血与不安", "chapters": []},
        {"act_index": 2, "title": "崩裂", "tone": "残酷与牺牲", "chapters": []},
        {"act_index": 3, "title": "终局", "tone": "悲壮与新生", "chapters": []},
    ]

    for idx, chapter in enumerate(chapter_defs, start=1):
        if idx <= 3:
            act_index = 1
        elif idx <= 6:
            act_index = 2
        else:
            act_index = 3
        chapter_obj = {
            "chapter_index": idx,
            "act_index": act_index,
            "title": chapter["title"],
            "objective": chapter["objective"],
            "core_conflict": chapter["conflict"],
            "sacrifice_cost": chapter["sacrifice"],
            "reward": chapter["reward"],
            "status": "pending",
        }
        acts[act_index - 1]["chapters"].append(chapter_obj)

    sacrifice_stakes = [
        "伙伴可能为主线撤离与封印付出代价。",
        "恋爱线与大局线在关键章节会出现冲突抉择。",
        "终局胜利不代表零代价，需承受可持续后果。",
    ]

    blueprint = {
        "mode": "three_act_eight_chapter",
        "title": f"{continent_name}神兽封印战役",
        "chapter_count": 8,
        "current_act": 1,
        "current_chapter": 1,
        "acts": acts,
    }
    return blueprint, sacrifice_stakes


def generate_world(
    db: Session,
    *,
    seed: str | None,
    canon_gen: int,
    canon_game: str | None,
) -> GeneratedWorld:
    final_seed = normalize_seed(seed)
    rng = _stable_rng(final_seed, canon_gen, canon_game)

    continent_name = _build_continent_name(rng)
    theme_tags = rng.sample(THEME_POOL, 3)
    used_cities: set[str] = set()
    start_town = _compose_city_name(rng, type_hint=None, used=used_cities)

    starter_options = _pick_starters(db, rng, canon_gen)
    gym_plan = _generate_gym_plan(rng)
    legendary_web = _build_legendary_web(rng)
    story_blueprint, sacrifice_stakes = _build_story_blueprint(
        continent_name=continent_name,
        start_town=start_town,
        gym_plan=gym_plan,
        legendary_web=legendary_web,
    )

    world_profile = {
        "continent_name": continent_name,
        "theme_tags": theme_tags,
        "start_town": start_town,
        "seed": final_seed,
        "legendary_arc": {
            "legendary_name": " / ".join([n["name_zh"] for n in legendary_web["nodes"][:2]]),
            "prophecy": "四柱神兽封印链正在瓦解，唯有以牺牲换取重启。",
        },
        "legendary_web": legendary_web,
        "story_blueprint": story_blueprint,
        "sacrifice_stakes": sacrifice_stakes,
    }

    return GeneratedWorld(
        seed=final_seed,
        world_profile=world_profile,
        starter_options=starter_options,
        gym_plan=gym_plan,
    )
