from app.db.models import CanonMove, CanonPokemon, CanonTypeChart
from app.db.session import SessionLocal


def seed() -> None:
    with SessionLocal() as db:
        if not db.query(CanonPokemon).first():
            db.add(
                CanonPokemon(
                    dex_no=94,
                    slug_id="gengar",
                    name_zh="耿鬼",
                    name_en="Gengar",
                    aliases=["耿鬼", "gengar"],
                    form=None,
                    types=["ghost", "poison"],
                    base_stats={"hp": 60, "atk": 65, "def": 60, "spa": 130, "spd": 75, "spe": 110},
                    abilities=["cursed-body"],
                    generation=9,
                    source="seed",
                    source_version="v1",
                )
            )
        if not db.query(CanonMove).first():
            db.add(
                CanonMove(
                    slug_id="shadow-ball",
                    name_zh="暗影球",
                    name_en="Shadow Ball",
                    aliases=["暗影球", "shadow-ball"],
                    type="ghost",
                    category="special",
                    power=80,
                    accuracy=100,
                    pp=15,
                    priority=0,
                    effect_short="May lower target Sp. Def",
                    generation=9,
                    source="seed",
                    source_version="v1",
                )
            )

        if not db.query(CanonTypeChart).first():
            types = [
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
            for atk in types:
                for df in types:
                    db.add(
                        CanonTypeChart(
                            atk_type=atk,
                            def_type=df,
                            multiplier=1.0,
                            generation=9,
                            source="seed",
                            source_version="v1",
                        )
                    )

        db.commit()


if __name__ == "__main__":
    seed()
    print("seed done")
