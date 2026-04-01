"""
Script to add Alicia and Hinobi to the database with their movesets and transformations.
"""

import sqlite3
import json

DATABASE_PATH = 'database/ronan.db'

def add_alicia():
    """Add Alicia to the database with her moveset."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Character stats from MD: str 2 | dex 3 | con 3 | int 2 | wis 3 | cha 3
    stats = {"str": 2, "dex": 3, "con": 3, "int": 2, "wis": 3, "cha": 3}
    stat_mods = {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}
    roll_mods = {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}

    # Resources: hp 55 | mp 110 | ac 13 | prof +3
    # AC 13 -> Tier 2 (medium)

    try:
        # Insert character
        cursor.execute("""
            INSERT INTO characters (
                name, hp, max_hp, mp, max_mp, ac, proficiency,
                stats_json, base_stats, stat_modifiers, roll_modifiers,
                current_form, tier, grunt, max_stars, current_stars, temp_hp, temp_mp,
                ac_modifier, ac_modifier_source, threshold_damage, threshold_dc,
                hidden_resources, squishy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Alicia", 55, 55, 110, 110, 2, 3,  # AC 13 -> tier 2
            json.dumps(stats), json.dumps(stats), json.dumps(stat_mods), json.dumps(roll_mods),
            "base", "veteran", 0, 5, 5, 0, 0,
            0, "", None, None, 0, 0
        ))

        print(f"[OK] Added character: Alicia (Duelist, Tier 2 AC)")

        # Add moveset
        # Fields: move_name, category, star_cost, mp_cost, hp_cost, stat, damage, hits, save_type, save_dc, save_effect, bonus_on_hit, cooldown, description
        moves = [
            # Utilities
            ("flutter flash", "utility", 2, 10, 0, "cha", 0, 1, None, None, None, None, 0, "Commit to fairy focus for 3 rounds. Choose: energy mode (+2 dmg), mind mode (advantage), fighter mode (+3 ac, resist physical)"),
            ("healing hands", "utility", 1, 12, 0, "wis", 0, 1, None, None, None, None, 3, "Restore 12+wis hp to self or ally. Cooldown: 3"),
            ("psycho parry", "utility", 0, 0, 0, None, 0, 1, None, None, None, None, 0, "Reaction: negate ranged attack, deal half damage back. 3 uses per combat"),

            # Light attacks
            ("energy spark", "light", 1, 6, 0, "cha", 5, 1, None, None, None, "energized:3", 0, "Quick energy burst. On hit: target energized for 3 rounds (+2 damage from energy attacks)"),
            ("psycho pull", "light", 1, 6, 0, "cha", 4, 1, None, None, None, "disadvantage:1", 0, "Telekinetic grip. On hit: disadvantage on their next attack"),
            ("shimmering strike", "light", 1, 6, 0, "dex", 5, 1, None, None, None, "shimmering:1", 0, "Quick glass blade thrust. On hit: next attack vs them has advantage"),

            # Medium attacks
            ("flower power", "medium", 2, 12, 0, "cha", 4, 3, None, None, None, None, 0, "Multiple flower energy projectiles. Each hit can target different enemy. +2 dmg vs energized"),
            ("psycho punchies", "medium", 2, 14, 0, "cha", 10, 1, "con", 2, "stunned", None, 0, "Telekinetic strike barrage. On hit: CON save or stunned"),
            ("shattering surge", "medium", 3, 18, 0, "dex", 11, 1, "dex", 2, None, None, 3, "Overcharged blade swing. Primary takes full, nearby DEX save or 6 fragment damage"),

            # Heavy attacks
            ("lazor blast", "heavy", 4, 25, 0, "cha", 13, 1, "dex", 2, "stunned", None, 3, "Energy beam line AOE. DEX save: fail=full+stunned, success=half. +6 vs energized"),
            ("psychic slam", "heavy", 3, 22, 0, "cha", 10, 1, "con", 2, "stunned:1", None, 2, "Telekinetic slam AOE. CON save or stunned 1 round. +4 dmg per additional target"),
            ("giggle fit", "heavy", 3, 18, 0, "cha", 6, 1, "wis", 2, None, None, 3, "WIS save: fail=stunned 2 rounds+6 dmg/turn, success=disadvantage next attack"),
            ("energy rain", "heavy", 3, 20, 0, "cha", 9, 1, None, None, None, None, 4, "Energy storm AOE. 9 damage/turn for 3 rounds. +2 vs energized. Dismissable"),

            # Defensive
            ("energy bubble", "defensive", 2, 10, 0, None, 0, 1, None, None, None, None, 0, "Gain 18 temp HP. Lasts 3 rounds or until depleted. 3 uses per combat"),
        ]

        for move_data in moves:
            cursor.execute("""
                INSERT INTO movesets (
                    character_name, move_name, category, star_cost, mp_cost, hp_cost,
                    stat, damage, hits, save_type, save_dc, save_effect, bonus_on_hit, cooldown, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Alicia",) + move_data)
            print(f"  - Added move: {move_data[0]} ({move_data[1]})")

        conn.commit()
        print(f"[OK] Added {len(moves)} moves for Alicia")

    except sqlite3.IntegrityError as e:
        print(f"[WARN] Alicia may already exist: {e}")
    finally:
        conn.close()


def add_hinobi():
    """Add Hinobi (base form) to the database with moveset."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Base form stats: str 2 | dex 3 | con 2 | int 3 | wis 2 | cha 3
    stats = {"str": 2, "dex": 3, "con": 2, "int": 3, "wis": 2, "cha": 3}
    stat_mods = {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0}
    roll_mods = {"attack_modifier": 0, "save_modifier": 0, "incoming_modifier": 0}

    # Resources: hp 55 | mp 110 | ac 14 | prof +3
    # AC 14 -> Tier 2 (medium)

    try:
        # Insert character
        cursor.execute("""
            INSERT INTO characters (
                name, hp, max_hp, mp, max_mp, ac, proficiency,
                stats_json, base_stats, stat_modifiers, roll_modifiers,
                current_form, tier, grunt, max_stars, current_stars, temp_hp, temp_mp,
                ac_modifier, ac_modifier_source, threshold_damage, threshold_dc,
                hidden_resources, squishy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Hinobi", 55, 55, 110, 110, 2, 3,  # AC 14 -> tier 2
            json.dumps(stats), json.dumps(stats), json.dumps(stat_mods), json.dumps(roll_mods),
            "base", "veteran", 0, 5, 5, 0, 50,  # +50 temp MP from passive
            0, "", None, None, 0, 0
        ))

        print(f"[OK] Added character: Hinobi (Duelist, Tier 2 AC, Base Form)")

        # Add base form moveset
        # Fields: move_name, category, star_cost, mp_cost, hp_cost, stat, damage, hits, save_type, save_dc, save_effect, bonus_on_hit, cooldown, description
        moves = [
            # Utilities
            ("cloud formation", "utility", 2, 10, 0, None, 0, 1, None, None, None, None, 0, "Summon storm afterimages. Gain advantage on attacks for 2 rounds"),
            ("static shield", "utility", 2, 10, 0, None, 0, 1, None, None, None, None, 0, "Reaction: +3 AC vs 1 attack. If hit, attacker takes 6 lightning damage"),

            # Light
            ("tempest fang", "light", 1, 0, 0, "dex", 4, 2, None, None, None, "disadvantage", 0, "Double backfist. Each hit gives disadvantage vs you (stacks)"),

            # Medium
            ("storm drummer", "medium", 2, 10, 0, "dex", 3, 4, None, None, "stunned", None, 0, "Electrified wing chun flurry. 2+ clean hits: target stunned"),
            ("thunderlash", "medium", 2, 12, 0, "int", 8, 1, None, None, None, "marked:2", 3, "Blitz past 3 enemies. Hit targets marked (+3 dmg) for 2 rounds"),
            ("licer", "medium", 2, 12, 0, "int", 12, 1, None, None, None, None, 0, "Concentrated lightning bolt"),

            # Heavy
            ("licer, wi ros", "heavy", 4, 18, 0, "int", 5, 1, "dex", 2, None, None, 3, "Raging typhoon AOE. DEX save each round or take damage. Targets have disadvantage while active. Duration: 3"),
        ]

        for move_data in moves:
            cursor.execute("""
                INSERT INTO movesets (
                    character_name, move_name, category, star_cost, mp_cost, hp_cost,
                    stat, damage, hits, save_type, save_dc, save_effect, bonus_on_hit, cooldown, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("Hinobi",) + move_data)
            print(f"  - Added move: {move_data[0]} ({move_data[1]})")

        conn.commit()
        print(f"[OK] Added {len(moves)} moves for Hinobi (base form)")

    except sqlite3.IntegrityError as e:
        print(f"[WARN] Hinobi may already exist: {e}")
    finally:
        conn.close()


def add_hinobi_transformations():
    """Add Hinobi's transformation forms to the forms table."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Speed Breaker form
    # From MD: offensive glass cannon, +1 dex, -1 con, AC 16 = tier 3
    speed_stats = {"str": 2, "dex": 4, "con": 1, "int": 3, "wis": 2, "cha": 3}

    # Power Breaker form
    # Balanced offensive, keeps base stats, AC 14 = tier 2
    power_stats = {"str": 2, "dex": 3, "con": 2, "int": 3, "wis": 2, "cha": 3}

    # God Breaker form
    # Ultimate form, enhanced stats, AC 16 = tier 3
    god_stats = {"str": 3, "dex": 4, "con": 3, "int": 4, "wis": 3, "cha": 4}

    # Forms table schema: character_name, form_name, stats_json, ac, transformation_cost, duration, cancellable, dot_damage, dot_type
    forms = [
        ("speed_breaker", speed_stats, 3, "free", None, 1, 0, ""),  # AC tier 3
        ("power_breaker", power_stats, 2, "free", None, 1, 0, ""),  # AC tier 2
        ("god_breaker", god_stats, 3, "free", None, 1, 0, ""),  # AC tier 3
    ]

    for form_name, stats, ac_tier, cost, duration, cancellable, dot_dmg, dot_type in forms:
        try:
            cursor.execute("""
                INSERT INTO forms (
                    character_name, form_name, stats_json, ac, transformation_cost,
                    duration, cancellable, dot_damage, dot_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "Hinobi", form_name, json.dumps(stats), ac_tier, cost,
                duration, cancellable, dot_dmg, dot_type
            ))
            print(f"  - Added transformation: {form_name} (AC Tier {ac_tier})")
        except sqlite3.IntegrityError:
            print(f"  - Transformation already exists: {form_name}")

    conn.commit()
    conn.close()
    print(f"[OK] Added Hinobi's transformation forms")


if __name__ == "__main__":
    print("=" * 60)
    print("ADDING ALICIA AND HINOBI TO DATABASE")
    print("=" * 60)
    print()

    print("[1/3] Adding Alicia...")
    add_alicia()
    print()

    print("[2/3] Adding Hinobi (base form)...")
    add_hinobi()
    print()

    print("[3/3] Adding Hinobi's transformations...")
    add_hinobi_transformations()
    print()

    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)
