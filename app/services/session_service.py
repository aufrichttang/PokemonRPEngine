from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models import AuditLog, CanonLevel, SaveSlot, TimelineEvent, Turn
from app.db.models import Session as StorySession
from app.providers.base import LLMProvider
from app.services.session_world_service import SessionWorldService
from app.services.story_enhancement_service import StoryEnhancementService
from app.services.v2.kernel_summary_service import KernelSummaryService
from app.services.v2.story_state_engine import StoryStateEngine
from app.worldgen.generator import generate_world

logger = get_logger(__name__)

PLAYER_NAMES = {
    "male": ["林烬", "顾泽", "陆川", "沈曜", "白霆", "程夜", "周岚", "韩澈"],
    "female": ["苏晴", "姜澜", "林汐", "顾念", "白音", "沈璃", "程雪", "安语"],
    "nonbinary": ["星野", "流岚", "若川", "朝雾", "叶岚", "云澈", "北辰", "千屿"],
}
APPEARANCE_POOL = [
    "黑发、目光沉静、笑起来带一点锋芒",
    "银灰短发、轮廓干净、气质冷冽",
    "长发束尾、眼神明亮、运动感很强",
    "五官立体、神情克制、带一点神秘感",
]
PERSONALITY_POOL = [
    "外冷内热，关键时刻会护住同伴",
    "理性果断，做决定很快",
    "温柔细腻，但战斗时非常强硬",
    "嘴硬心软，重承诺",
]
BACKGROUND_POOL = [
    "来自边境小镇，曾因神兽异象失去重要之人",
    "联盟实习调查员，擅长破解遗迹机关",
    "道馆学徒出身，目标是建立自己的道馆",
    "前运输队成员，熟悉大陆的隐秘路线",
]
ROMANCE_POOL = {
    "female": [
        {"name": "白晴", "role": "遗迹研究员", "trait": "冷艳聪明，笑起来很温柔"},
        {"name": "林音", "role": "道馆继承人", "trait": "明媚强势，战斗气场极强"},
        {"name": "苏晚", "role": "联盟特派员", "trait": "高冷优雅，私下反差可爱"},
        {"name": "顾瑶", "role": "神兽观测员", "trait": "外表清冷，内心炽热"},
    ],
    "male": [
        {"name": "沈曜", "role": "精英训练家", "trait": "沉稳克制，关键时刻极有担当"},
        {"name": "程凛", "role": "巡防队长", "trait": "锋芒毕露，保护欲很强"},
        {"name": "陆川", "role": "机械师", "trait": "毒舌但可靠，行动力爆表"},
        {"name": "韩澈", "role": "馆主候补", "trait": "冷面寡言，情感专一"},
    ],
}


def _default_player_state() -> dict:
    return {
        "location": "",
        "money": 1200,
        "badges": [],
        "team": [],
        "storage_box": [],
        "inventory": {
            "balls": [{"name_zh": "精灵球", "count": 5}],
            "medicine": [{"name_zh": "伤药", "count": 3}],
            "battle_items": [],
            "berries": [],
            "key_items": [{"name_zh": "训练家证", "count": 1}],
            "materials": [],
            "misc": [],
        },
        "quests": [],
    }


def _public_world_profile(value: dict[str, Any] | None) -> dict[str, Any]:
    profile = dict(value) if isinstance(value, dict) else {}
    profile.pop("map_data", None)
    return profile


def _normalize_gender(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {"male", "man", "m", "男", "男性"}:
        return "male"
    if value in {"female", "woman", "f", "女", "女性"}:
        return "female"
    return "nonbinary"


def _build_player_profile(
    *, seed: str, user_id: uuid.UUID, player_profile: dict[str, Any] | None
) -> dict[str, Any]:
    raw = player_profile if isinstance(player_profile, dict) else {}
    rnd = random.Random(f"{seed}-{user_id}")

    gender = _normalize_gender(str(raw.get("gender") or ""))
    gender_label = "男" if gender == "male" else "女" if gender == "female" else "其他"

    name_raw = str(raw.get("name") or "").strip()
    height_raw = str(raw.get("height_cm") or raw.get("height") or "").strip()
    age_raw = str(raw.get("age") or "").strip()
    detail_raw = str(raw.get("detail") or raw.get("details") or "").strip()
    appearance_raw = str(raw.get("appearance") or "").strip()
    personality_raw = str(raw.get("personality") or "").strip()
    background_raw = str(raw.get("background") or "").strip()

    if name_raw:
        name = name_raw[:24]
    else:
        name = rnd.choice(PLAYER_NAMES[gender])

    if height_raw.isdigit():
        height_cm = max(130, min(220, int(height_raw)))
    else:
        base = {"male": 176, "female": 165, "nonbinary": 170}[gender]
        height_cm = base + rnd.randint(-8, 8)

    if age_raw.isdigit():
        age = max(10, min(50, int(age_raw)))
    else:
        age = rnd.randint(15, 22)

    return {
        "name": name,
        "gender": gender_label,
        "gender_code": gender,
        "height_cm": height_cm,
        "age": age,
        "appearance": appearance_raw or rnd.choice(APPEARANCE_POOL),
        "personality": personality_raw or rnd.choice(PERSONALITY_POOL),
        "background": background_raw or rnd.choice(BACKGROUND_POOL),
        "detail": detail_raw or "目标是夺得冠军并解开大陆神兽异象之谜。",
        "romance_preference": "hetero",
    }


def _build_romance_candidates(*, profile: dict[str, Any], seed: str) -> list[dict[str, Any]]:
    rnd = random.Random(f"romance-{seed}-{profile.get('name', '')}")
    gender_code = str(profile.get("gender_code") or "nonbinary")
    if gender_code == "male":
        pool = ROMANCE_POOL["female"][:]
    elif gender_code == "female":
        pool = ROMANCE_POOL["male"][:]
    else:
        pool = [*ROMANCE_POOL["female"], *ROMANCE_POOL["male"]]
    rnd.shuffle(pool)
    selected = pool[:3]
    for idx, item in enumerate(selected, 1):
        item["route_tag"] = f"route-{idx}"
        item["route_hint"] = "主线抉择可锁定专一路线，也允许保留多线关系。"
    return selected


def _build_backstory(
    *,
    profile: dict[str, Any],
    world_profile: dict[str, Any],
    seed: str,
) -> dict[str, Any]:
    rnd = random.Random(f"backstory-{seed}-{profile.get('name', '')}")
    continent = str(world_profile.get("continent_name") or "未知大陆")
    start_town = str(world_profile.get("start_town") or "未知城镇")
    legends = []
    legendary_web = world_profile.get("legendary_web")
    if isinstance(legendary_web, dict):
        nodes = legendary_web.get("nodes", [])
        if isinstance(nodes, list):
            legends = [
                str(node.get("name_zh"))
                for node in nodes
                if isinstance(node, dict) and node.get("name_zh")
            ]
    main_legend = legends[0] if legends else "神兽"

    origin_pool = [
        f"{continent}边境的旧驿站",
        f"{start_town}附近的矿脉聚落",
        f"{continent}北部海岬的渔村",
        f"{continent}南线的联盟预备营",
    ]
    raw_age = profile.get("age")
    player_age = int(raw_age) if isinstance(raw_age, int) else 18
    # Keep timeline consistent with current character age.
    # Example: age=12 -> trigger_age=11, avoiding fixed 15-year contradiction.
    trigger_age = max(10, min(17, player_age - 1 if player_age > 10 else player_age))

    incident_pool = [
        f"你在{trigger_age}岁那年目睹了{main_legend}异象导致的城镇停电与暴走事件。",
        "一次护送任务中，你在遗迹中发现了失控封印碎片，从此被卷入神兽纷争。",
        "你曾试图救下重要之人，却在封印崩裂中失败，这成为你无法回避的伤口。",
    ]
    vow_pool = [
        "你发誓不再让同伴独自承担牺牲，哪怕代价由你来背负。",
        "你立下誓言：就算必须失去荣耀，也要守住最后的平民撤离线。",
        "你决定追到真相尽头，即使终点会撕碎你最珍视的关系。",
    ]
    companion_pool = [
        {"name": "遥斗", "role": "旧搭档", "fate": "在撤离行动中失踪"},
        {"name": "澪音", "role": "幼时青梅", "fate": "加入了对立阵营"},
        {"name": "真由", "role": "通讯员", "fate": "为掩护你撤退身负重伤"},
        {"name": "凛司", "role": "导师", "fate": "留下地图后下落不明"},
    ]
    secret_pool = [
        f"你体内残留着{main_legend}共鸣痕迹，情绪失控时会触发异常感知。",
        "你曾短暂加入灰烬议会外围情报网，这段经历不能公开。",
        "你掌握一枚未登记封印碎片坐标，但公布后会引发大规模争夺。",
    ]
    romance_hook_pool = [
        "你对“并肩作战后仍愿回头等你的人”毫无抵抗力。",
        "你习惯把伤口藏起来，却会被真诚的温柔瞬间击穿防线。",
        "你表面理性克制，但一旦确认心意会毫不犹豫护到底。",
    ]

    return {
        "origin": rnd.choice(origin_pool),
        "inciting_incident": rnd.choice(incident_pool),
        "scar_and_vow": rnd.choice(vow_pool),
        "past_companion": rnd.choice(companion_pool),
        "secret": rnd.choice(secret_pool),
        "romance_hook": rnd.choice(romance_hook_pool),
    }


def _opening_intro(story: StorySession) -> tuple[str, list[dict[str, str]], dict]:
    world: dict[str, Any] = story.world_profile if isinstance(story.world_profile, dict) else {}
    profile: dict[str, Any] = story.player_profile if isinstance(story.player_profile, dict) else {}
    starters = [s for s in (story.starter_options or []) if isinstance(s, dict)]
    love_raw = world.get("romance_lead")
    love: dict[str, Any] = love_raw if isinstance(love_raw, dict) else {}
    romance_candidates = [
        c for c in (world.get("romance_candidates") or []) if isinstance(c, dict)
    ]
    legend_raw = world.get("legendary_arc")
    legend: dict[str, Any] = legend_raw if isinstance(legend_raw, dict) else {}
    backstory = profile.get("backstory", {}) if isinstance(profile.get("backstory"), dict) else {}
    story_enhancement = (
        world.get("story_enhancement", {}) if isinstance(world.get("story_enhancement"), dict) else {}
    )
    enhanced_backstory = (
        backstory.get("enhanced", {}) if isinstance(backstory.get("enhanced"), dict) else {}
    )
    story_blueprint = (
        world.get("story_blueprint", {}) if isinstance(world.get("story_blueprint"), dict) else {}
    )
    acts = story_blueprint.get("acts", []) if isinstance(story_blueprint.get("acts"), list) else []
    first_chapter: dict[str, Any] = {}
    if acts and isinstance(acts[0], dict):
        chapters = acts[0].get("chapters", [])
        if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
            first_chapter = chapters[0]
    legendary_names = []
    legendary_web = world.get("legendary_web", {})
    if isinstance(legendary_web, dict):
        nodes = legendary_web.get("nodes", [])
        if isinstance(nodes, list):
            legendary_names = [
                str(node.get("name_zh"))
                for node in nodes
                if isinstance(node, dict) and node.get("name_zh")
            ]

    starter_lines = []
    options: list[dict[str, str]] = []
    for idx, s in enumerate(starters[:3], 1):
        name = str(s.get("name_zh") or "未知伙伴")
        starter_lines.append(f"{idx}) {name}")
        options.append(
            {
                "id": f"starter-{idx}",
                "text": f"选择{name}作为初始伙伴",
                "send_text": f"我选择{name}作为我的初始伙伴。",
            }
        )

    options.extend(
        [
            {
                "id": "ask-romance",
                "text": "询问恋爱线索与主角背景",
                "send_text": "我先了解恋爱线索与主角背景。",
            },
            {
                "id": "ask-legend",
                "text": "追问神兽传说与主线危机",
                "send_text": "我追问神兽传说和这片大陆的危机。",
            },
            {
                "id": "ask-backstory",
                "text": "追问我过去的关键事件",
                "send_text": "我想先回看我的过去经历和关键创伤。",
            },
        ]
    )
    for idx, candidate in enumerate(romance_candidates[:3], 1):
        candidate_name = str(candidate.get("name") or f"候选对象{idx}")
        options.append(
            {
                "id": f"romance-route-{idx}",
                "text": f"优先接近{candidate_name}，推进恋爱支线",
                "send_text": f"我决定先接近{candidate_name}，看看我们会发生什么。",
            }
        )

    intro_text = "\n".join(
        [
            "【旁白】",
            f"你在 {world.get('start_town', '未知城镇')} 醒来，眼前是从未见过的新大陆：{world.get('continent_name', '未知大陆')}。",
            "海风与机械轰鸣交织，城市上空闪烁着古代遗迹投影，冒险与命运同一刻降临。",
            "",
            "【主角档案】",
            f"- 名字：{profile.get('name', '未命名')}",
            f"- 性别：{profile.get('gender', '未设定')}  年龄：{profile.get('age', '?')}  身高：{profile.get('height_cm', '?')}cm",
            f"- 外形：{profile.get('appearance', '未设定')}",
            f"- 个性：{profile.get('personality', '未设定')}",
            f"- 背景：{profile.get('background', '未设定')}",
            f"- 细节：{profile.get('detail', '未设定')}",
            "",
            "【剧情预告】",
            f"- 恋爱主线：{love.get('name', '神秘同伴')}（{love.get('role', '搭档候选')}）",
            f"- 神兽主线：{legend.get('legendary_name', '未知神兽')} · {legend.get('prophecy', '一则古老预言')}",
            f"- 多神兽网络：{' / '.join(legendary_names) if legendary_names else '尚未显形'}",
            f"- 主线润色：{story_enhancement.get('arc_overview', '规则骨架模式，待润色')}",
            *(
                [
                    f"- 恋爱候选：{c.get('name', '未知')}（{c.get('role', '未知身份')}）· {c.get('trait', '')}"
                    for c in romance_candidates[:3]
                ]
                if romance_candidates
                else []
            ),
            "",
            "【前史档案】",
            f"- 出身：{backstory.get('origin', '未知')}",
            f"- 触发事件：{backstory.get('inciting_incident', '未知')}",
            f"- 创伤与誓言：{backstory.get('scar_and_vow', '未知')}",
            f"- 旧羁绊：{(backstory.get('past_companion') or {}).get('name', '未知')} / {(backstory.get('past_companion') or {}).get('fate', '未知')}",
            f"- 隐藏秘密：{backstory.get('secret', '未知')}",
            f"- 恋爱引线：{backstory.get('romance_hook', '未知')}",
            f"- 润色前史：{enhanced_backstory.get('inciting_incident', backstory.get('inciting_incident', '未知'))}",
            "",
            "【主线蓝图】",
            f"- 当前章节：第{first_chapter.get('chapter_index', 1)}章·{first_chapter.get('title', '起始火花')}",
            f"- 强制目标：{first_chapter.get('objective', '完成启程并锁定主线危机')}",
            f"- 冲突核心：{first_chapter.get('core_conflict', '封印异动正在蔓延')}",
            f"- 代价提示：{first_chapter.get('sacrifice_cost', '胜利一定伴随代价')}",
            f"- 当前起点：{world.get('start_town', '未知城镇')}",
            "",
            "【御三家】",
            *(starter_lines or ["1) 妙蛙种子", "2) 小火龙", "3) 杰尼龟"]),
            "",
            "【可选动作】",
            "1) 选择你的初始伙伴",
            "2) 询问恋爱线的关键人物",
            "3) 追问神兽危机与大陆真相",
            "4) 回看我的过去并确认主线誓言",
        ]
    )

    opening_state = {
        "location": world.get("start_town", ""),
        "player_profile": profile,
        "story_progress": {
            "act": 1,
            "chapter": 1,
            "objective": first_chapter.get("objective", "完成启程并锁定主线危机"),
            "objective_status": "pending",
            "turns_in_chapter": 0,
        },
        "quests": [
            "完成初始伙伴选择",
            f"接触{love.get('name', '关键角色')}并建立羁绊",
            f"调查{legend.get('legendary_name', '神兽')}相关异象",
            f"主线第1章：{first_chapter.get('objective', '完成启程并锁定主线危机')}",
        ],
    }
    return intro_text, options, opening_state


class SessionService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.story_enhancement_service = StoryEnhancementService(
            settings=settings,
            provider=provider,
        )
        self.session_world_service = SessionWorldService(self.story_enhancement_service)
        self.story_state_engine = StoryStateEngine()
        self.kernel_summary_service = KernelSummaryService()

    def create_session(
        self,
        db: Session,
        *,
        user_id: uuid.UUID,
        title: str,
        world_template_id: str | None,
        world_seed: str | None,
        canon_gen: int,
        canon_game: str | None,
        custom_lore_enabled: bool,
        player_profile: dict[str, Any] | None = None,
        ensure_v3_slot: bool = True,
    ) -> StorySession:
        generated = generate_world(
            db,
            seed=world_seed,
            canon_gen=canon_gen,
            canon_game=canon_game,
        )
        profile = _build_player_profile(
            seed=generated.seed, user_id=user_id, player_profile=player_profile
        )
        world_profile = (
            dict(generated.world_profile) if isinstance(generated.world_profile, dict) else {}
        )
        profile["backstory"] = _build_backstory(
            profile=profile,
            world_profile=world_profile,
            seed=generated.seed,
        )
        romance_candidates = _build_romance_candidates(profile=profile, seed=generated.seed)
        world_profile["romance_candidates"] = romance_candidates
        world_profile["romance_mode"] = "branching_plus_multi"
        if romance_candidates:
            world_profile["romance_lead"] = romance_candidates[0]
        world_profile["version"] = 2
        story_enhancement = self.story_enhancement_service.enhance_story(
            world_profile=world_profile,
            player_profile=profile,
            seed=generated.seed,
            canon_gen=canon_gen,
        )
        world_profile["story_enhancement"] = story_enhancement
        if isinstance(profile.get("backstory"), dict):
            backstory = dict(profile["backstory"])
            backstory["enhanced"] = story_enhancement.get("backstory_polish", {})
            profile["backstory"] = backstory

        story = StorySession(
            user_id=user_id,
            title=title,
            world_template_id=world_template_id,
            world_seed=generated.seed,
            canon_gen=canon_gen,
            canon_game=canon_game,
            custom_lore_enabled=custom_lore_enabled,
            world_profile=world_profile,
            player_profile=profile,
            starter_options=generated.starter_options,
            gym_plan=generated.gym_plan,
            player_state=_default_player_state(),
            battle_mode=generated.battle_mode,
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        db.add(
            AuditLog(
                session_id=story.id,
                turn_id=None,
                action="story_enhanced",
                payload={
                    "source": story_enhancement.get("source", "fallback"),
                    "cache_hit": bool(story_enhancement.get("cache_hit", False)),
                    "generated_with_llm": bool(story_enhancement.get("generated_with_llm", False)),
                    "seed": generated.seed,
                    "canon_gen": canon_gen,
                },
            )
        )
        db.commit()

        intro_text, intro_options, opening_state = _opening_intro(story)
        turn = Turn(
            session_id=story.id,
            turn_index=1,
            user_text="【系统】自动开场",
            assistant_text=intro_text,
            action_options=intro_options,
            state_update=opening_state,
        )
        db.add(turn)
        db.flush()

        story.player_state = {**(story.player_state or {}), **opening_state}
        story.updated_at = datetime.now(UTC)
        db.add(story)
        db.commit()
        if ensure_v3_slot:
            slot = self.story_state_engine.ensure_slot_for_session(db, session_obj=story)
            self.story_state_engine.ensure_kernel_rows(db, slot_id=slot.id)
            db.commit()
        db.refresh(story)
        return story

    def list_sessions(
        self, db: Session, *, user_id: uuid.UUID, page: int, size: int
    ) -> list[StorySession]:
        stmt = (
            select(StorySession)
            .where(StorySession.user_id == user_id, StorySession.deleted.is_(False))
            .order_by(desc(StorySession.updated_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(db.execute(stmt).scalars().all())

    def ensure_world_profile_integrity(
        self,
        db: Session,
        *,
        session_obj: StorySession,
        save: bool = True,
    ) -> dict[str, Any]:
        result = self.session_world_service.ensure_world_profile_integrity(
            db,
            session_obj=session_obj,
            save=save,
        )
        return {
            "changed": result.changed,
            "changed_fields": result.changed_fields,
            "migration_applied": result.migration_applied,
        }

    def get_session(self, db: Session, *, session_id: uuid.UUID) -> StorySession | None:
        session_obj = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one_or_none()
        if session_obj:
            self.ensure_world_profile_integrity(db, session_obj=session_obj, save=True)
        return session_obj

    def get_recent_turns(
        self, db: Session, *, session_id: uuid.UUID, limit: int = 50
    ) -> list[Turn]:
        stmt = (
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(desc(Turn.turn_index))
            .limit(limit)
        )
        rows = list(db.execute(stmt).scalars().all())
        rows.reverse()
        return rows

    def delete_session(self, db: Session, *, session_id: uuid.UUID) -> None:
        session = db.execute(select(StorySession).where(StorySession.id == session_id)).scalar_one()
        session.deleted = True
        db.add(session)
        db.commit()

    def export_session(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
    ) -> dict:
        sess = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one()
        self.ensure_world_profile_integrity(db, session_obj=sess, save=True)
        turns = self.get_recent_turns(db, session_id=session_id, limit=10_000)
        return {
            "session": {
                "id": str(sess.id),
                "title": sess.title,
                "canon_gen": sess.canon_gen,
                "canon_game": sess.canon_game,
                "world_seed": sess.world_seed,
                "world_profile": sess.world_profile or {},
                "player_profile": sess.player_profile or {},
                "starter_options": sess.starter_options or [],
                "gym_plan": sess.gym_plan or [],
                "player_state": sess.player_state or _default_player_state(),
                "battle_mode": sess.battle_mode,
                "created_at": sess.created_at.isoformat() if sess.created_at else None,
                "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
            },
            "turns": [
                {
                    "turn_index": t.turn_index,
                    "user_text": t.user_text,
                    "assistant_text": t.assistant_text,
                    "action_options": t.action_options or [],
                    "battle_summary": t.battle_summary or {},
                    "state_update": t.state_update or {},
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in turns
            ],
        }

    def get_world_state(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
    ) -> dict:
        sess = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one()
        self.ensure_world_profile_integrity(db, session_obj=sess, save=True)
        slot = db.execute(select(SaveSlot).where(SaveSlot.session_id == sess.id)).scalar_one_or_none()
        lore_row = time_row = faction_row = None
        if slot:
            lore_row, time_row, faction_row = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        return {
            "session_id": str(sess.id),
            "world_seed": sess.world_seed,
            "battle_mode": sess.battle_mode,
            "world_profile": _public_world_profile(sess.world_profile),
            "player_profile": sess.player_profile or {},
            "starter_options": sess.starter_options or [],
            "gym_plan": sess.gym_plan or [],
            "player_state": sess.player_state or _default_player_state(),
            "current_badges": len([g for g in (sess.gym_plan or []) if g.get("cleared")]),
            "lore_kernel_summary": self.kernel_summary_service.summarize_lore(lore_row),
            "time_kernel_summary": self.kernel_summary_service.summarize_time(time_row),
            "faction_kernel_summary": self.kernel_summary_service.summarize_faction(faction_row),
            "active_warnings": self.kernel_summary_service.warnings(lore=lore_row, time=time_row),
        }

    def get_story_data(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
    ) -> dict[str, Any]:
        sess = db.execute(
            select(StorySession).where(
                StorySession.id == session_id, StorySession.deleted.is_(False)
            )
        ).scalar_one()
        self.ensure_world_profile_integrity(db, session_obj=sess, save=True)
        world_profile = sess.world_profile if isinstance(sess.world_profile, dict) else {}
        player_profile = sess.player_profile if isinstance(sess.player_profile, dict) else {}
        backstory = (
            player_profile.get("backstory", {})
            if isinstance(player_profile.get("backstory"), dict)
            else {}
        )
        slot = db.execute(select(SaveSlot).where(SaveSlot.session_id == sess.id)).scalar_one_or_none()
        lore_row = time_row = faction_row = None
        if slot:
            lore_row, time_row, faction_row = self.kernel_summary_service.get_rows(db, slot_id=slot.id)
        return {
            "session_id": str(sess.id),
            "story_blueprint": world_profile.get("story_blueprint", {}),
            "story_enhancement": world_profile.get("story_enhancement", {}),
            "legendary_web": world_profile.get("legendary_web", {}),
            "backstory": backstory,
            "narrative_mode": "layered",
            "lore_kernel_summary": self.kernel_summary_service.summarize_lore(lore_row),
            "time_kernel_summary": self.kernel_summary_service.summarize_time(time_row),
            "faction_kernel_summary": self.kernel_summary_service.summarize_faction(faction_row),
            "source": (
                world_profile.get("story_enhancement", {}).get("source", "fallback")
                if isinstance(world_profile.get("story_enhancement"), dict)
                else "fallback"
            ),
        }

    def public_world_profile(self, world_profile: dict[str, Any] | None) -> dict[str, Any]:
        return _public_world_profile(world_profile)

    def list_timeline_events(
        self,
        db: Session,
        *,
        session_id: uuid.UUID,
        canon_level: CanonLevel | None,
        page: int,
        size: int,
    ) -> list[TimelineEvent]:
        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.session_id == session_id)
            .order_by(desc(TimelineEvent.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        if canon_level:
            stmt = stmt.where(TimelineEvent.canon_level == canon_level)
        return list(db.execute(stmt).scalars().all())

