"""
Character import script for Alicia and Hin'obi
Imports characters with their forms and movesets into the database
"""

import asyncio
import aiosqlite
import json

DATABASE_PATH = 'database/ronan.db'

# Map character stats to bot's 6-stat system
# combat=offensive physical, power=strength/force, mobility=dex, technique=precision/skill, resilience=con, focus=mental
def map_stats_to_bot(char_stats):
    """Map traditional stats to bot's combat/power/mobility/technique/resilience/focus"""
    # Alicia: str 1 | dex 4 | con 3 | int 2 | wis 2 | cha 4
    # -> combat (offensive), power (str), mobility (dex), technique (skill), resilience (con), focus (mental)
    return {
        "combat": char_stats.get("cha", 0),  # Offensive capability (use cha for casters, str for fighters)
        "power": char_stats.get("str", 0),   # Raw strength
        "mobility": char_stats.get("dex", 0), # Dexterity/speed
        "technique": char_stats.get("int", 0), # Precision/skill (use int or dex)
        "resilience": char_stats.get("con", 0), # Durability
        "focus": char_stats.get("wis", 0)    # Mental fortitude
    }


async def import_alicia():
    """Import Alicia character"""
    db = await aiosqlite.connect(DATABASE_PATH)

    # Character: str 1 | dex 4 | con 3 | int 2 | wis 2 | cha 4
    # Mapped: combat=4 (cha), power=1 (str), mobility=4 (dex), technique=2 (int), resilience=3 (con), focus=2 (wis)
    base_stats = json.dumps({
        "combat": 4, "power": 1, "mobility": 4,
        "technique": 2, "resilience": 3, "focus": 2
    })

    stat_modifiers = json.dumps({
        "combat": 0, "power": 0, "mobility": 0,
        "technique": 0, "resilience": 0, "focus": 0
    })

    roll_modifiers = json.dumps({
        "attack_modifier": 0,
        "incoming_modifier": 0,
        "save_modifier": 0
    })

    # Create character
    await db.execute("""
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, stars, max_stars, ac, movement, proficiency,
         base_stats, stat_modifiers, roll_modifiers, current_form, ac_modifier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("Alicia", 55, 55, 110, 110, 0, 3, 13, 30, 3,
          base_stats, stat_modifiers, roll_modifiers, "base", 0))

    await db.commit()

    # Import moves for Alicia (base form only)
    moves = [
        # Utility moves (2 stars)
        ("Flutter Flash (Energy)", "utility", "combat", 0, 0, 10, 0, 0, 0, None, None, None, 0, "buff", 3, 0, None, "+2 damage and burning to energy attacks", 2),
        ("Flutter Flash (Mind)", "utility", "combat", 0, 0, 10, 0, 0, 0, None, None, None, 0, "buff", 3, 0, None, "Advantage on mind attacks, +2 AC", 2),
        ("Flutter Flash (Fighter)", "utility", "combat", 0, 0, 10, 0, 0, 0, None, None, None, 0, "buff", 3, 0, None, "+3 AC, resistance to physical damage", 2),
        ("Healing Hands", "utility", "focus", 0, 0, 12, 0, 0, 0, None, None, None, 0, None, 0, 3, None, "Restore 12+wis HP to self or ally", 1),
        ("Phase Step", "utility", "mobility", 0, 0, 8, 0, 0, 0, None, None, None, 0, None, 0, 0, 4, "Advantage on next attack OR disadvantage on attack against you", 1),
        ("Energy Bubble", "utility", "combat", 0, 0, 10, 0, 0, 0, None, None, None, 0, None, 3, 0, 3, "Gain 18 temp HP for 3 rounds", 2),

        # Light attacks (1 star)
        ("Energy Spark", "light", "combat", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: energized for 3 rounds (+2 dmg from energy attacks)", 1),
        ("Psycho Pull", "light", "combat", 4, 0, 6, 0, 0, 3, None, None, None, 0, None, 0, 0, None, "Each hit gives disadvantage on their next attack", 1),
        ("Shimmering Strike", "light", "mobility", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: shimmering for 1 round (next attack has advantage)", 1),

        # Medium attacks (2 stars)
        ("Flower Power", "medium", "combat", 5, 3, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Each hit can target different enemies. +2 per hit vs energized", 2),
        ("Psycho Punchies", "medium", "combat", 10, 0, 14, 0, 0, 1, "con", 15, None, 0, None, 0, 0, None, "On hit: con save or stunned. Reaction to negate ranged attack", 2),
        ("Shattering Surge", "heavy", "mobility", 11, 0, 18, 0, 0, 1, "dex", 15, None, 1, None, 0, 3, None, "Primary takes full. Nearby: dex save or 6 dmg (half on save)", 3),

        # Heavy attacks (4/3 stars)
        ("Lazor Blast", "heavy", "combat", 16, 0, 25, 0, 0, 1, "dex", 15, "Stunned until your next turn", 1, None, 0, 3, None, "Line attack. Save for half. +6 vs energized. Destroys cover", 4),
        ("Psychic Slam", "heavy", "combat", 10, 0, 22, 0, 0, 1, "con", 15, None, 0, None, 0, 2, None, "All nearby. Con save or stunned. +4 per extra enemy", 3),
        ("Giggle Fit", "heavy", "combat", 6, 0, 18, 0, 0, 1, "wis", 15, None, 0, None, 2, 3, None, "Save: stunned 2 rounds + 6/turn. Success: dis on next attack", 3),
        ("Energy Rain", "heavy", "combat", 9, 0, 20, 0, 0, 1, None, None, None, 0, None, 3, 4, None, "9 force at start of turn. +2 vs energized. Can dismiss early", 3),
    ]

    for move in moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description, targets)
            VALUES (?, 'base', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Alicia",) + move)

    await db.commit()
    await db.close()
    print("✅ Alicia imported successfully!")


async def import_hinobi():
    """Import Hin'obi with all 4 forms"""
    db = await aiosqlite.connect(DATABASE_PATH)

    # Base stats: str 2 | dex 3 | con 2 | int 3 | wis 2 | cha 3
    # Mapped: combat=3 (balanced), power=2, mobility=3, technique=3, resilience=2, focus=2
    base_stats = json.dumps({
        "combat": 3, "power": 2, "mobility": 3,
        "technique": 3, "resilience": 2, "focus": 2
    })

    stat_modifiers = json.dumps({
        "combat": 0, "power": 0, "mobility": 0,
        "technique": 0, "resilience": 0, "focus": 0
    })

    roll_modifiers = json.dumps({
        "attack_modifier": 0,
        "incoming_modifier": 0,
        "save_modifier": 0
    })

    # Create character
    await db.execute("""
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, stars, max_stars, ac, movement, proficiency,
         base_stats, stat_modifiers, roll_modifiers, current_form, ac_modifier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("Hinobi", 55, 55, 110, 110, 0, 3, 14, 30, 3,
          base_stats, stat_modifiers, roll_modifiers, "base", 0))

    await db.commit()

    # Add forms
    forms = [
        # Speed Breaker: str 1 | dex 5 | con 2 | int 3 | wis 2 | cha 3
        # combat=3, power=1, mobility=5, technique=3, resilience=2, focus=2
        ("Speed Breaker", json.dumps({"combat": 3, "power": 1, "mobility": 5, "technique": 3, "resilience": 2, "focus": 2}),
         15, "stars:1, mp:5", 0, 1, 0, ""),

        # Power Breaker: str 4 | dex 1 | con 5 | int 1 | wis 1 | cha 4
        # combat=4, power=4, mobility=1, technique=1, resilience=5, focus=1
        ("Power Breaker", json.dumps({"combat": 4, "power": 4, "mobility": 1, "technique": 1, "resilience": 5, "focus": 1}),
         12, "stars:1, mp:5", 0, 1, 0, ""),

        # God Breaker: str 4 | dex 5 | con 2 | int 3 | wis 1 | cha 3
        # combat=5 (apex), power=4, mobility=5, technique=3, resilience=2, focus=1
        ("God Breaker", json.dumps({"combat": 5, "power": 4, "mobility": 5, "technique": 3, "resilience": 2, "focus": 1}),
         16, "stars:1, mp:10", 0, 0, 5, ""),  # Duration 0 = loses 5 MP/round, cancellable=0 (locked)
    ]

    for form in forms:
        await db.execute("""
            INSERT OR REPLACE INTO forms
            (character_name, form_name, stats, ac, transformation_cost, duration, cancellable, dot_damage, dot_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + form)

    await db.commit()

    # Base form moves
    base_moves = [
        ("Cloud Formation", "utility", "mobility", 0, 0, 10, 0, 0, 0, None, None, None, 0, None, 2, 0, None, "Advantage on attacks via afterimages", 2),
        ("Static Shield", "utility", "technique", 0, 0, 10, 0, 0, 0, None, None, None, 0, None, 0, 0, None, "Reaction: +3 AC. If hit, deal 6 lightning to attacker", 2),
        ("Tempest Fang", "light", "mobility", 4, 2, 0, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Each hit: attackers have disadvantage vs you (stacks)", 1),
        ("Storm Drummer", "medium", "mobility", 3, 4, 10, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Clean hit: stun until your next turn", 2),
        ("Thunderlash", "medium", "technique", 8, 0, 12, 0, 0, 1, None, None, None, 0, None, 2, 3, None, "Mark targets: take +3 from your attacks for 2 rounds", 2),
        ("Licér", "medium", "technique", 12, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Concentrated lightning bolt", 2),
        ("Licér wi Rós", "heavy", "technique", 5, 0, 18, 0, 0, 1, "dex", None, None, 0, None, 3, 3, None, "Typhoon. Dex save each round or dmg. Dis on attacks", 4),
    ]

    for move in base_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description, targets)
            VALUES (?, 'base', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move)

    # Speed Breaker moves
    speed_moves = [
        ("Twin Cyclones", "utility", "mobility", 0, 0, 10, 0, 0, 0, "dex", 10, None, 0, None, 0, 0, None, "Gap closer. Save fail: advantage + 4 dmg on next attack", 2),
        ("Wall Cloud", "utility", "mobility", 0, 0, 10, 0, 0, 0, None, None, None, 0, None, 2, 0, None, "Immune to most small ranged attacks", 2),
        ("Calm Before", "utility", "mobility", 4, 0, 10, 0, 0, 0, None, None, None, 0, None, 0, 0, None, "Reaction: auto-dodge, afterimage deals 4 dmg, reposition", 2),
        ("Approaching Storm", "light", "mobility", 5, 0, 3, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "If first attack: advantage", 1),
        ("Gentle Breeze", "light", "mobility", 4, 0, 4, 0, 0, 1, None, None, None, 0, None, 0, 1, None, "Auto-hit. Reaction when enemy disengages", 1),
        ("Eye of the Storm", "medium", "mobility", 6, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Bypass shields. If they blocked: lose next reaction", 2),
        ("Gust Front", "medium", "mobility", 6, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "On hit: next attack +6 dmg, ignores 1 defensive ability", 2),
        ("Perfect Storm", "heavy", "mobility", 0, 4, 25, 0, 0, 1, None, None, None, 0, None, 0, 4, None, "4 light attacks (roll each). Each after 1st: +2 dmg", 4),
    ]

    for move in speed_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description, targets)
            VALUES (?, 'Speed Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move)

    # Power Breaker moves
    power_moves = [
        ("Veprux's Roar", "utility", "power", 0, 0, 10, 0, 0, 0, None, None, None, 0, None, 0, 0, None, "Next attack: +8 dmg, ignores reduction", 2),
        ("Veprux's Hide", "utility", "resilience", 0, 0, 15, 0, 0, 0, None, None, None, 0, None, 3, 0, None, "Reduce incoming dmg by 5. Attackers take 6 on contact", 2),
        ("Gryphix's Flight", "medium", "power", 10, 0, 12, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Unstoppable rush. Can follow with another attack", 2),
        ("Veprux's Fang", "medium", "power", 12, 0, 14, 0, 0, 1, "con", None, None, 0, None, 0, 0, None, "On hit: con save or stunned", 2),
        ("Veprux's Quake", "heavy", "power", 16, 0, 20, 0, 0, 1, "power", None, None, 0, None, 0, 2, None, "Ground slam. Str save or prone", 4),
        ("Gryphix's Spite", "medium", "power", 8, 0, 10, 0, 0, 1, None, None, None, 0, None, 0, 1, None, "Reaction when hit: strike back. Double if took 10+ dmg", 2),
    ]

    for move in power_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description, targets)
            VALUES (?, 'Power Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move)

    # God Breaker moves (base versions)
    god_moves = [
        ("Descend", "light", "mobility", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Drop from above. On hit: prone", 1),
        ("Descend (Upgraded)", "light", "mobility", 5, 0, 6, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Advantage. 3 force AoE on landing. Requires 1 stack", 1),
        ("Orbit", "light", "technique", 6, 0, 8, 0, 0, 1, None, None, None, 0, None, 2, 0, None, "Halberd attacks autonomously each turn", 1),
        ("Orbit (Upgraded)", "light", "technique", 6, 0, 8, 0, 0, 1, None, None, None, 0, None, 2, 0, None, "Attacks twice per turn. Requires 1 stack", 1),
        ("Scatter", "medium", "mobility", 4, 4, 14, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "4 hits. Each: -1 AC (stacks)", 2),
        ("Scatter (Upgraded)", "medium", "mobility", 4, 4, 14, 0, 0, 1, None, None, None, 0, None, 0, 0, None, "Marks targets. Lightning chains for +4. Requires 2 stacks", 2),
        ("Eclipse", "utility", "combat", 0, 0, 15, 0, 0, 0, None, None, None, 0, None, 2, 0, None, "Enemies: dis vs you. You: adv on saves", 2),
        ("Eclipse (Upgraded)", "utility", "combat", 0, 0, 15, 0, 0, 0, None, None, None, 0, None, 2, 0, None, "Also -2 AC to all enemies. Requires 2 stacks", 2),
        ("Pierce", "heavy", "technique", 18, 0, 22, 0, 0, 1, None, None, None, 0, None, 0, 3, None, "Ignores all reductions/resistances. Cannot be blocked", 3),
        ("Pierce (Upgraded)", "heavy", "technique", 18, 0, 22, 0, 0, 1, None, None, None, 0, None, 0, 3, None, "Also dispel 1 effect. Requires 3 stacks", 3),
        ("Severance", "heavy", "power", 20, 0, 24, 0, 0, 1, None, None, None, 0, None, 0, 3, None, "Wind blade. Ignores cover/barriers", 4),
        ("Severance (Upgraded)", "heavy", "power", 20, 0, 24, 0, 0, 1, None, None, None, 0, None, 0, 3, None, "Hits all in line. Requires 3 stacks", 4),
        ("Sunder", "heavy", "combat", 20, 0, 25, 0, 0, 1, None, None, None, 0, None, 0, 4, None, "Adapts to last dmg type. Physical/magic/status", 4),
        ("Sunder (Upgraded)", "heavy", "combat", 20, 0, 25, 0, 0, 1, None, None, None, 0, None, 1, 4, None, "Vulnerability for 1 round. Requires 3 stacks", 4),
        ("Erupt", "utility", "combat", 0, 0, 12, 0, 0, 0, None, None, None, 0, None, 0, 2, None, "Reaction: nullify dmg. Next attack of that type: +10, crit", 2),
        ("Erupt (Upgraded)", "utility", "combat", 0, 0, 12, 0, 0, 0, None, None, None, 0, None, 2, 2, None, "Also resistance for 2 rounds. Requires 3 stacks", 2),
    ]

    for move in god_moves:
        await db.execute("""
            INSERT OR REPLACE INTO movesets
            (character_name, form_name, move_name, category, stat, damage, hits, mp_cost, hp_cost, star_cost,
             save_type, save_dc, save_effect, half_on_save, bonus_on_hit, duration, cooldown, uses, description, targets)
            VALUES (?, 'God Breaker', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Hinobi",) + move)

    await db.commit()
    await db.close()
    print("✅ Hin'obi imported with all 4 forms!")


async def main():
    """Import both characters"""
    print("Importing characters...")
    await import_alicia()
    await import_hinobi()
    print("\n🎉 All characters imported successfully!")
    print("\nTo view in Discord:")
    print("  /char show Alicia")
    print("  /char show Hinobi")
    print("\nTo list forms:")
    print("  /form list Hinobi")
    print("\nTo list moves:")
    print("  /move list Alicia")
    print("  /move list Hinobi")


if __name__ == "__main__":
    asyncio.run(main())
