from __future__ import annotations

from sqlalchemy import delete

from app.db.models import CanonPokemon
from app.worldgen.generator import generate_world


def _seed_pokemon(db_session) -> None:
    db_session.execute(delete(CanonPokemon))
    rows = [
        CanonPokemon(
            dex_no=1,
            slug_id="bulbasaur",
            name_zh="妙蛙种子",
            name_en="Bulbasaur",
            aliases=["bulbasaur", "妙蛙种子"],
            form=None,
            types=["grass", "poison"],
            base_stats={},
            abilities=["overgrow"],
            generation=1,
            source="test",
            source_version="v1",
        ),
        CanonPokemon(
            dex_no=4,
            slug_id="charmander",
            name_zh="小火龙",
            name_en="Charmander",
            aliases=["charmander", "小火龙"],
            form=None,
            types=["fire"],
            base_stats={},
            abilities=["blaze"],
            generation=1,
            source="test",
            source_version="v1",
        ),
        CanonPokemon(
            dex_no=7,
            slug_id="squirtle",
            name_zh="杰尼龟",
            name_en="Squirtle",
            aliases=["squirtle", "杰尼龟"],
            form=None,
            types=["water"],
            base_stats={},
            abilities=["torrent"],
            generation=1,
            source="test",
            source_version="v1",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()


def test_worldgen_seed_is_deterministic(db_session) -> None:
    _seed_pokemon(db_session)

    w1 = generate_world(db_session, seed="seed-abc", canon_gen=9, canon_game="sv")
    w2 = generate_world(db_session, seed="seed-abc", canon_gen=9, canon_game="sv")

    assert w1.world_profile == w2.world_profile
    assert w1.starter_options == w2.starter_options
    assert w1.gym_plan == w2.gym_plan


def test_worldgen_starters_and_gyms_rules(db_session) -> None:
    _seed_pokemon(db_session)

    world = generate_world(db_session, seed="seed-rules", canon_gen=9, canon_game="sv")

    assert len(world.starter_options) == 3
    starter_types = {opt["types"][0] if opt["types"] else "" for opt in world.starter_options}
    assert {"grass", "fire", "water"}.issubset({t.lower() for t in starter_types})

    assert len(world.gym_plan) == 8
    gym_types = [g["gym_type"] for g in world.gym_plan]
    assert len(gym_types) == len(set(gym_types))
    assert [g["difficulty_tier"] for g in world.gym_plan] == list(range(1, 9))


def test_worldgen_story_blueprint_and_legendary_web(db_session) -> None:
    _seed_pokemon(db_session)

    world = generate_world(db_session, seed="seed-story", canon_gen=9, canon_game="sv")
    profile = world.world_profile

    assert profile["start_town"] != "真新镇"
    assert "story_blueprint" in profile
    assert "legendary_web" in profile
    assert "map_data" not in profile

    blueprint = profile["story_blueprint"]
    assert blueprint["mode"] == "three_act_eight_chapter"
    assert blueprint["chapter_count"] == 8
    assert len(blueprint["acts"]) == 3
    chapters = [c for act in blueprint["acts"] for c in act["chapters"]]
    assert len(chapters) == 8
    assert all(bool(c.get("objective")) for c in chapters)

    web = profile["legendary_web"]
    assert len(web["nodes"]) >= 3
    assert all(bool(node.get("name_zh")) for node in web["nodes"])
