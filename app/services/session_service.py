from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models import AuditLog, CanonLevel, SaveSlot, TimelineEvent, Turn
from app.db.models import Session as StorySession
from app.providers.base import LLMProvider
from app.services.opening_story_service import OpeningStoryService
from app.services.session_world_service import SessionWorldService
from app.services.story_enhancement_service import StoryEnhancementService
from app.services.v2.kernel_summary_service import KernelSummaryService
from app.services.v2.story_state_engine import StoryStateEngine
from app.worldgen.generator import generate_world

logger = get_logger(__name__)

PLAYER_NAMES = {
    "male": ["林烁", "顾泽", "陆川", "沈曜", "白隼", "程夜", "周岚", "韩澈"],
    "female": ["苏晴", "姜澜", "林澄", "顾念", "白音", "沈玲", "程雪", "安语"],
    "nonbinary": ["星野", "流岚", "若川", "朝雾", "叶岚", "云澈", "北景", "千岚"],
}
APPEARANCE_POOL = [
    "黑发，目光沉静，笑起来带一点锋芒",
    "银灰短发，轮廓干净，气质冷冽",
    "长发束尾，眼神明亮，运动感很强",
    "五官立体，神情克制，带一点神秘感",
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
        {"name": "林音", "role": "道馆继承人", "trait": "明艳强势，战斗气场极强"},
        {"name": "苏晚", "role": "联盟特派员", "trait": "高冷优雅，私下反差可爱"},
        {"name": "顾瑶", "role": "神兽观测员", "trait": "外表清冷，内心炽热"},
    ],
    "male": [
        {"name": "沈曜", "role": "精英训练家", "trait": "沉稳克制，关键时刻极有担当"},
        {"name": "程凛", "role": "巡防队长", "trait": "锋芒毕露，保护欲很强"},
        {"name": "陆川", "role": "机械师", "trait": "毒舌但可靠，行动力爆表"},
        {"name": "韩澈", "role": "领主候补", "trait": "冷面寡言，情感专一"},
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
    trigger_age = max(10, min(17, player_age - 1 if player_age > 10 else player_age))

    incident_pool = [
        f"你在{trigger_age}岁那年目睹了{main_legend}异象导致的城镇停电与暴走事件。",
        "一次护送任务中，你在遗迹里发现失控封印碎片，从此被卷入神兽纷争。",
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
def _extract_first_chapter(world: dict[str, Any]) -> dict[str, Any]:
    story_blueprint = (
        world.get("story_blueprint", {}) if isinstance(world.get("story_blueprint"), dict) else {}
    )
    acts = story_blueprint.get("acts", []) if isinstance(story_blueprint.get("acts"), list) else []
    if acts and isinstance(acts[0], dict):
        chapters = acts[0].get("chapters", [])
        if isinstance(chapters, list) and chapters and isinstance(chapters[0], dict):
            return chapters[0]
    return {}


def _opening_intro(
    story: StorySession,
    *,
    opening_story: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, str]], dict]:
    world: dict[str, Any] = story.world_profile if isinstance(story.world_profile, dict) else {}
    profile: dict[str, Any] = story.player_profile if isinstance(story.player_profile, dict) else {}
    starters = [s for s in (story.starter_options or []) if isinstance(s, dict)]
    backstory = profile.get("backstory", {}) if isinstance(profile.get("backstory"), dict) else {}
    first_chapter = _extract_first_chapter(world)

    opening_story = opening_story if isinstance(opening_story, dict) else {}
    digest_lines = [
        str(item).strip()
        for item in (opening_story.get("profile_digest_lines") or [])
        if str(item).strip()
    ][:5]
    if not digest_lines:
        digest_lines = [
            f"{profile.get('name', '未命名')}，{profile.get('gender', '未知')}，{profile.get('age', '?')}岁，{profile.get('height_cm', '?')}cm。",
            f"外形：{profile.get('appearance', '轮廓冷峻，气质克制')}。",
            f"性格：{profile.get('personality', '外冷内热，关键时刻会护住同伴')}。",
            f"背景：{profile.get('background', '来自边境小镇，背负未解之谜')}。",
        ]

    scene = str(opening_story.get("backstory_scene") or "").strip()
    if not scene:
        scene = (
            f"你在{world.get('start_town', '未知城镇')}醒来，夜色像铁一样压在轨道上。"
            f"脑海里最先涌上的，是那场灾变：{backstory.get('inciting_incident', '神兽异象打碎了原有的生活')}。"
            f"你仍记得自己立下的誓言：{backstory.get('scar_and_vow', '哪怕牺牲荣耀，也要守住撤离线')}。"
        )

    transition = str(opening_story.get("transition_line") or "").strip()
    if not transition:
        transition = (
            f"当前目标：{first_chapter.get('objective', '完成启程并锁定第一枚徽章线索')}。"
            f"代价预警：{first_chapter.get('sacrifice_cost', '胜利伴随牺牲')}。"
        )

    options: list[dict[str, str]] = []
    for idx, starter in enumerate(starters[:3], 1):
        name = str(starter.get("name_zh") or f"御三家{idx}")
        options.append(
            {
                "id": f"starter-{idx}",
                "text": f"选择{name}作为初始伙伴",
                "send_text": f"我选择{name}作为我的初始伙伴。",
            }
        )

    romance_candidates = [
        c for c in (world.get("romance_candidates") or []) if isinstance(c, dict)
    ]
    if romance_candidates:
        candidate_name = str(romance_candidates[0].get("name") or "关键人物")
        options.append(
            {
                "id": "ask-romance",
                "text": f"询问{candidate_name}与恋爱主线",
                "send_text": f"我想先了解{candidate_name}和这条恋爱线索。",
            }
        )
    options.append(
        {
            "id": "ask-legend",
            "text": "追问神兽危机与大陆真相",
            "send_text": "我想知道神兽危机和大陆异象的真相。",
        }
    )
    options.append(
        {
            "id": "ask-backstory",
            "text": "回看我的过去并确认誓言",
            "send_text": "我想回看过去的关键事件，并确认我的主线誓言。",
        }
    )

    intro_text = "\n\n".join(
        [
            "【旁白】\n"
            f"你在{world.get('start_town', '未知城镇')}醒来，眼前是{world.get('continent_name', '未知大陆')}的黎明。"
            "海风与机械轰鸣交织，远空的遗迹投影正缓慢旋转。",
            "【主角档案摘要】\n" + "\n".join(f"- {line}" for line in digest_lines),
            "【前史回放】\n" + scene,
            "【当前目标】\n" + transition,
        ]
    )

    opening_state = {
        "location": world.get("start_town", ""),
        "player_profile": profile,
        "story_progress": {
            "act": 1,
            "chapter": 1,
            "objective": first_chapter.get("objective", "完成启程并锁定第一枚徽章线索"),
            "objective_status": "pending",
            "turns_in_chapter": 0,
        },
        "quests": [
            "完成初始伙伴选择",
            first_chapter.get("objective", "完成启程并锁定第一枚徽章线索"),
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
        self.opening_story_service = OpeningStoryService(
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

        first_chapter = _extract_first_chapter(world_profile)
        backstory_payload = (
            profile.get("backstory", {}) if isinstance(profile.get("backstory"), dict) else {}
        )
        opening_started = perf_counter()
        opening_story_result = self.opening_story_service.generate_opening_story(
            world_profile=world_profile,
            player_profile=profile,
            backstory=backstory_payload,
            first_chapter=first_chapter,
            story_enhancement=story_enhancement if isinstance(story_enhancement, dict) else {},
        )
        opening_story = {
            "profile_digest_lines": opening_story_result.profile_digest_lines,
            "backstory_scene": opening_story_result.backstory_scene,
            "transition_line": opening_story_result.transition_line,
            "source": opening_story_result.source,
        }
        world_profile["opening_story"] = opening_story
        opening_story_ms = int((perf_counter() - opening_started) * 1000)
        logger.info(
            "opening_story_generated",
            opening_story_source=opening_story_result.source,
            opening_story_ms=opening_story_ms,
            opening_story_chars=len(opening_story_result.backstory_scene),
            session_seed=generated.seed,
            canon_gen=canon_gen,
        )

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

        intro_text, intro_options, opening_state = _opening_intro(story, opening_story=opening_story)
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

