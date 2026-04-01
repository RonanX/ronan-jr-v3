"""
Direct database import for Alicia and Hin'obi
Bypasses Discord commands and imports everything in one go
"""

import asyncio
import aiosqlite
import json

DATABASE_PATH = 'database/ronan.db'


async def import_alicia():
    """Import Alicia with full moveset"""
    db = await aiosqlite.connect(DATABASE_PATH)

    # Stats: str 1 | dex 4 | con 3 | int 2 | wis 2 | cha 4
    base_stats = json.dumps({"str": 1, "dex": 4, "con": 3, "int": 2, "wis": 2, "cha": 4})
    stat_modifiers = json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})
    roll_modifiers = json.dumps({"attack_modifier": 0, "incoming_modifier": 0, "save_modifier": 0})

    # Create character (stats_json is same as base_stats for compatibility)
    await db.execute("""
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, max_stars,
         stats_json, base_stats, stat_modifiers, roll_modifiers, current_form, ac_modifier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("Alicia", 55, 55, 110, 110, 13, 30, 3, 3,
          base_stats, base_stats, stat_modifiers, roll_modifiers, "base", 0))

    # Alicia's moves
    moves = [
        # Utility (2 stars)
        ("Flutter Flash (Energy)", "utility", "cha", 0, 0, 10, 0, 2, 0, None, None, None, 0, "buff", 3, 0, None, "+2 damage and burning to energy attacks"),
        ("Flutter Flash (Mind)", "utility", "cha", 0, 0, 10, 0, 2, 0, None, None, None, 0, "buff", 3, 0, None, "Advantage on mind attacks, +2 AC"),
        ("Flutter Flash (Fighter)", "utility", "cha", 0, 0, 10, 0, 2, 0, None, None, None, 0, "buff", 3, 0, None, "+3 AC, resistance to physical damage"),
        ("Healing Hands", "utility", "wis", 0, 0, 12, 0, 1, 0, None, None, None, 0, None, 0, 3, None, "Restore 12+wis HP to self or ally"),
        ("Phase Step", "utility", "dex", 0, 0, 8, 0, 1, 0, None, None, None, 0, None, 0, 0, 4, "Advantage on next attack OR disadvantage on attack vs you"),
        ("Energy Bubble", "utility", "cha", 0, 0, 10, 0, 2, 0, None, None, None, 0, None, 3, 0, 3, "Gain 18 temp HP for 3 rounds"),

        # Light (1 star)
        ("Energy Spark", "light", "cha", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: energized for 3 rounds (+2 dmg from energy attacks)"),
        ("Psycho Pull", "light", "cha", 4, 0, 6, 0, 0, 3, None, None, None, 0, None, 0, 0, None, "Each hit gives disadvantage on their next attack"),
        ("Shimmering Strike", "light", "dex", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: shimmering for 1 round (next attack has advantage)"),

        # Medium (2 stars)
        ("Flower Power", "medium", "cha", 5, 3, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Each hit can target different enemies. +2 per hit vs energized"),
        ("Psycho Punchies", "medium", "cha", 10, 0, 14, 0, 0, 1, "con", 15, None, 0, None, 0, 0, None, "On hit: con save or stunned. Reaction to negate ranged attack"),
        ("Shattering Surge", "heavy", "dex", 11, 0, 18, 0, 3, 1, "dex", 15, None, 1, None, 0, 3, None, "Primary takes full. Nearby: dex save or 6 dmg (half on save)"),

        # Heavy (3-4 stars)
        ("Lazor Blast", "heavy", "cha", 16, 0, 25, 0, 4, 1, "dex", 15, "Stunned until your next turn", 1, None, 0, 3, None, "Line attack. Save for half. +6 vs energized. Destroys cover"),
        ("Psychic Slam", "heavy", "cha", 10, 0, 22, 0, 3, 1, "con", 15, None, 0, None, 0, 2, None, "All nearby. Con save or stunned. +4 per extra enemy"),
        ("Giggle Fit", "heavy", "cha", 6, 0, 18, 0, 3, 1, "wis", 15, None, 0, None, 2, 3, None, "Save: stunned 2 rounds + 6/turn. Success: dis on next attack"),
        ("Energy Rain", "heavy", "cha", 9, 0, 20, 0, 3, 1, None, None, None, 0, None, 3, 4, None, "9 force at start of turn. +2 vs energized. Can dismiss early"),
    ]

    for move_data in moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description)
            VALUES (?, 'base', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Alicia",) + move_data)

    await db.commit()
    await db.close()
    print("[OK] Alicia imported with 16 moves")


async def import_hinobi():
    """Import Hin'obi with all 4 forms and movesets"""
    db = await aiosqlite.connect(DATABASE_PATH)

    # Base stats: str 2 | dex 3 | con 2 | int 3 | wis 2 | cha 3
    base_stats = json.dumps({"str": 2, "dex": 3, "con": 2, "int": 3, "wis": 2, "cha": 3})
    stat_modifiers = json.dumps({"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0})
    roll_modifiers = json.dumps({"attack_modifier": 0, "incoming_modifier": 0, "save_modifier": 0})

    # Create character (stats_json is same as base_stats for compatibility)
    await db.execute("""
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, max_stars,
         stats_json, base_stats, stat_modifiers, roll_modifiers, current_form, ac_modifier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("Hinobi", 55, 55, 110, 110, 14, 30, 3, 3,
          base_stats, base_stats, stat_modifiers, roll_modifiers, "base", 0))

    # Create forms
    forms = [
        # Speed Breaker: str 1 | dex 5 | con 2 | int 3 | wis 2 | cha 3
        ("Speed Breaker", json.dumps({"str": 1, "dex": 5, "con": 2, "int": 3, "wis": 2, "cha": 3}),
         15, "stars:1, mp:5", 0, 1, 0, ""),

        # Power Breaker: str 4 | dex 1 | con 5 | int 1 | wis 1 | cha 4
        ("Power Breaker", json.dumps({"str": 4, "dex": 1, "con": 5, "int": 1, "wis": 1, "cha": 4}),
         12, "stars:1, mp:5", 0, 1, 0, ""),

        # God Breaker: str 4 | dex 5 | con 2 | int 3 | wis 1 | cha 3
        ("God Breaker", json.dumps({"str": 4, "dex": 5, "con": 2, "int": 3, "wis": 1, "cha": 3}),
         16, "stars:1, mp:10", 0, 0, 5, ""),  # Duration 0, loses 5 MP/round
    ]

    for form_data in forms:
        await db.execute("""
            INSERT OR REPLACE INTO forms
            (character_name, form_name, stats_json, ac, transformation_cost, duration, cancellable, dot_damage, dot_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + form_data)

    # Base form moves - Order: name, category, stat, damage, hits, mp_cost, hp_cost, star_cost, targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description
    base_moves = [
        ("Cloud Formation", "utility", "dex", 0, 0, 10, 0, 2, 1, None, None, None, 0, None, 2, 0, None, "Advantage on attacks via afterimages"),
        ("Static Shield", "utility", "int", 0, 0, 10, 0, 2, 1, None, None, None, 0, None, 0, 0, None, "Reaction: +3 AC. If hit, deal 6 lightning to attacker"),
        ("Tempest Fang", "light", "dex", 4, 2, 0, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Each hit: attackers have disadvantage vs you (stacks)"),
        ("Storm Drummer", "medium", "dex", 3, 4, 10, 0, 0, 1, None, None, None, 0, "Clean hit: stun until your next turn", 0, 0, None, None),
        ("Thunderlash", "medium", "int", 8, 0, 12, 0, 0, 1, None, None, None, 0, "Mark targets: take +3 from your attacks for 2 rounds", 2, 3, None, None),
        ("Licér", "medium", "int", 12, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Concentrated lightning bolt"),
        ("Licér wi Rós", "heavy", "int", 5, 0, 18, 0, 4, 1, "dex", None, None, 0, None, 3, 3, None, "Typhoon. Dex save each round or dmg. Dis on attacks"),
    ]

    for move_data in base_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description)
            VALUES (?, 'base', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move_data)

    # Speed Breaker moves
    speed_moves = [
        ("Twin Cyclones", "utility", "dex", 0, 0, 10, 0, 2, 0, "dex", 10, None, 0, None, 0, 0, None, "Gap closer. Save fail: advantage + 4 dmg on next attack"),
        ("Wall Cloud", "utility", "dex", 0, 0, 10, 0, 2, 0, None, None, None, 0, None, 2, 0, None, "Immune to most small ranged attacks"),
        ("Calm Before", "utility", "dex", 4, 0, 10, 0, 2, 0, None, None, None, 0, None, 0, 0, None, "Reaction: auto-dodge, afterimage deals 4 dmg, reposition"),
        ("Approaching Storm", "light", "dex", 5, 0, 3, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "If first attack: advantage"),
        ("Gentle Breeze", "light", "dex", 4, 0, 4, 0, 0, 1, None, None, None, 0, None, 0, 1, None, "Auto-hit. Reaction when enemy disengages"),
        ("Eye of the Storm", "medium", "dex", 6, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Bypass shields. If they blocked: lose next reaction"),
        ("Gust Front", "medium", "dex", 6, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: next attack +6 dmg, ignores 1 defensive ability"),
        ("Perfect Storm", "heavy", "dex", 0, 4, 25, 0, 4, 1, None, None, None, 0, None, 0, 4, None, "4 light attacks (roll each). Each after 1st: +2 dmg"),
    ]

    for move_data in speed_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description)
            VALUES (?, 'Speed Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move_data)

    # Power Breaker moves
    power_moves = [
        ("Veprux's Roar", "utility", "str", 0, 0, 10, 0, 2, 0, None, None, None, 0, None, 0, 0, None, "Next attack: +8 dmg, ignores reduction"),
        ("Veprux's Hide", "utility", "con", 0, 0, 15, 0, 2, 0, None, None, None, 0, None, 3, 0, None, "Reduce incoming dmg by 5. Attackers take 6 on contact"),
        ("Gryphix's Flight", "medium", "str", 10, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Unstoppable rush. Can follow with another attack"),
        ("Veprux's Fang", "medium", "str", 12, 0, 14, 0, 0, 1, "con", None, None, 0, None, 0, 0, None, "On hit: con save or stunned"),
        ("Veprux's Quake", "heavy", "str", 16, 0, 20, 0, 4, 1, "str", None, None, 0, None, 0, 2, None, "Ground slam. Str save or prone"),
        ("Gryphix's Spite", "medium", "str", 8, 0, 10, 0, 0, 1, None, None, None, 0, None, 0, 1, None, "Reaction when hit: strike back. Double if took 10+ dmg"),
    ]

    for move_data in power_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description)
            VALUES (?, 'Power Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move_data)

    # God Breaker moves (base + upgraded variants)
    god_moves = [
        ("Descend", "light", "dex", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Drop from above. On hit: prone"),
        ("Descend (Upgraded)", "light", "dex", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Advantage. 3 force AoE on landing. Requires 1 stack"),
        ("Orbit", "light", "int", 6, 0, 8, 0, 0, 1, None, None, None, 0, None, 2, 0, None, "Halberd attacks autonomously each turn"),
        ("Orbit (Upgraded)", "light", "int", 6, 0, 8, 0, 0, 1, None, None, None, 0, None, 2, 0, None, "Attacks twice per turn. Requires 1 stack"),
        ("Scatter", "medium", "dex", 4, 4, 14, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "4 hits. Each: -1 AC (stacks)"),
        ("Scatter (Upgraded)", "medium", "dex", 4, 4, 14, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Marks targets. Lightning chains for +4. Requires 2 stacks"),
        ("Eclipse", "utility", "cha", 0, 0, 15, 0, 2, 0, None, None, None, 0, None, 2, 0, None, "Enemies: dis vs you. You: adv on saves"),
        ("Eclipse (Upgraded)", "utility", "cha", 0, 0, 15, 0, 2, 0, None, None, None, 0, None, 2, 0, None, "Also -2 AC to all enemies. Requires 2 stacks"),
        ("Pierce", "heavy", "int", 18, 0, 22, 0, 3, 1, None, None, None, 0, None, 0, 3, None, "Ignores all reductions/resistances. Cannot be blocked"),
        ("Pierce (Upgraded)", "heavy", "int", 18, 0, 22, 0, 3, 1, None, None, None, 0, None, 0, 3, None, "Also dispel 1 effect. Requires 3 stacks"),
        ("Severance", "heavy", "str", 20, 0, 24, 0, 4, 1, None, None, None, 0, None, 0, 3, None, "Wind blade. Ignores cover/barriers"),
        ("Severance (Upgraded)", "heavy", "str", 20, 0, 24, 0, 4, 1, None, None, None, 0, None, 0, 3, None, "Hits all in line. Requires 3 stacks"),
        ("Sunder", "heavy", "cha", 20, 0, 25, 0, 4, 1, None, None, None, 0, None, 0, 4, None, "Adapts to last dmg type. Physical/magic/status"),
        ("Sunder (Upgraded)", "heavy", "cha", 20, 0, 25, 0, 4, 1, None, None, None, 0, None, 1, 4, None, "Vulnerability for 1 round. Requires 3 stacks"),
        ("Erupt", "utility", "int", 0, 0, 12, 0, 2, 0, None, None, None, 0, None, 0, 2, None, "Reaction: nullify dmg. Next attack of that type: +10, crit"),
        ("Erupt (Upgraded)", "utility", "int", 0, 0, 12, 0, 2, 0, None, None, None, 0, None, 2, 2, None, "Also resistance for 2 rounds. Requires 3 stacks"),
    ]

    for move_data in god_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             targets, save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description)
            VALUES (?, 'God Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move_data)

    await db.commit()
    await db.close()

    move_count = len(base_moves) + len(speed_moves) + len(power_moves) + len(god_moves)
    print(f"[OK] Hinobi imported with 3 forms and {move_count} total moves")
    print("      - Base: 7 moves")
    print("      - Speed Breaker: 8 moves")
    print("      - Power Breaker: 6 moves")
    print("      - God Breaker: 16 moves")


async def main():
    print("=== Direct Database Import ===\n")
    print("Importing Alicia...")
    await import_alicia()
    print("\nImporting Hin'obi...")
    await import_hinobi()
    print("\n[SUCCESS] All characters imported!")
    print("\nVerify in Discord:")
    print("  /char show Alicia")
    print("  /char show Hinobi")
    print("  /form list Hinobi")
    print("  /move list Alicia")
    print("  /move list Hinobi Speed Breaker")


if __name__ == "__main__":
    asyncio.run(main())
