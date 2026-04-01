"""
Simple character import that works with current schema
Just creates character entries and moveset text files for manual import
"""

import asyncio
import aiosqlite
import json

DATABASE_PATH = 'database/ronan.db'


async def check_schema():
    """Check what columns exist in characters table"""
    db = await aiosqlite.connect(DATABASE_PATH)
    async with db.execute("PRAGMA table_info(characters)") as cursor:
        columns = await cursor.fetchall()
        print("Current characters table columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    await db.close()


async def import_characters():
    """Import using current schema"""
    db = await aiosqlite.connect(DATABASE_PATH)

    # Check if characters exist
    async with db.execute("SELECT name FROM characters WHERE name IN ('Alicia', 'Hinobi')") as cursor:
        existing = await cursor.fetchall()
        if existing:
            print(f"Characters already exist: {[row[0] for row in existing]}")
            print("Skipping character creation...")
        else:
            print("Characters don't exist in database.")
            print("Please create them using Discord commands:")
            print("\n  /char create Alicia hp:55 mp:110 ac:13 movement:30")
            print("  Then set stats: combat:4, power:1, mobility:4, technique:2, resilience:3, focus:2")
            print("\n  /char create Hinobi hp:55 mp:110 ac:14 movement:30")
            print("  Then set stats: combat:3, power:2, mobility:3, technique:3, resilience:2, focus:2")

    await db.close()


# Generate moveset import text files
def generate_alicia_moveset():
    """Generate Alicia's moveset in text format for /moveset import"""
    moves = """Flutter Flash (Energy) - utility, stat:combat, mp_cost:10, duration:3, description:+2 damage and burning to energy attacks
Flutter Flash (Mind) - utility, stat:combat, mp_cost:10, duration:3, description:Advantage on mind attacks +2 AC
Flutter Flash (Fighter) - utility, stat:combat, mp_cost:10, duration:3, description:+3 AC resistance to physical damage
Healing Hands - utility, stat:focus, mp_cost:12, cooldown:3, star_cost:1, description:Restore 12+wis HP to self or ally
Phase Step - utility, stat:mobility, mp_cost:8, uses:4, star_cost:1, description:Advantage on next attack OR disadvantage on attack vs you
Energy Bubble - utility, stat:combat, mp_cost:10, uses:3, duration:3, description:Gain 18 temp HP
Energy Spark - light, stat:combat, damage:5, mp_cost:6, description:On hit energized for 3 rounds
Psycho Pull - light, stat:combat, damage:4, mp_cost:6, targets:3, description:Each hit gives disadvantage on next attack
Shimmering Strike - light, stat:mobility, damage:5, mp_cost:6, description:On hit shimmering 1 round
Flower Power - medium, stat:combat, damage:5, hits:3, mp_cost:12, description:Each hit different target +2 per hit vs energized
Psycho Punchies - medium, stat:combat, damage:10, mp_cost:14, save_type:con, save_dc:15, description:Con save or stunned. Reaction vs ranged
Shattering Surge - heavy, stat:mobility, damage:11, mp_cost:18, star_cost:3, save_type:dex, save_dc:15, half_on_save:1, cooldown:3, description:Primary full dmg. Nearby dex save or 6 half on save
Lazor Blast - heavy, stat:combat, damage:16, mp_cost:25, save_type:dex, save_dc:15, half_on_save:1, save_effect:Stunned, cooldown:3, description:Line attack. +6 vs energized. Destroys cover
Psychic Slam - heavy, stat:combat, damage:10, mp_cost:22, star_cost:3, save_type:con, save_dc:15, cooldown:2, description:All nearby. +4 per extra enemy
Giggle Fit - heavy, stat:combat, damage:6, mp_cost:18, star_cost:3, save_type:wis, save_dc:15, duration:2, cooldown:3, description:Save stunned 2 rounds 6 per turn. Success dis on next attack
Energy Rain - heavy, stat:combat, damage:9, mp_cost:20, star_cost:3, duration:3, cooldown:4, description:9 force per turn. +2 vs energized"""

    with open("data/saves/lore/alicia_moveset.txt", "w") as f:
        f.write(moves)
    print("[OK] Generated alicia_moveset.txt")


def generate_hinobi_movesets():
    """Generate all Hinobi movesets"""

    base = """Cloud Formation - utility, stat:mobility, mp_cost:10, duration:2, description:Advantage on attacks via afterimages
Static Shield - utility, stat:technique, mp_cost:10, description:Reaction +3 AC. If hit deal 6 lightning
Tempest Fang - light, stat:mobility, damage:4, hits:2, description:Each hit attackers have disadvantage vs you
Storm Drummer - medium, stat:mobility, damage:3, hits:4, mp_cost:10, description:Clean hit stun until your next turn
Thunderlash - medium, stat:technique, damage:8, mp_cost:12, duration:2, cooldown:3, description:Mark targets take +3 from attacks for 2 rounds
Licér - medium, stat:technique, damage:12, mp_cost:12, description:Concentrated lightning bolt
Licér wi Rós - heavy, stat:technique, damage:5, mp_cost:18, save_type:dex, duration:3, cooldown:3, description:Typhoon. Dex save each round or dmg. Dis on attacks"""

    speed = """Twin Cyclones - utility, stat:mobility, mp_cost:10, save_type:dex, save_dc:10, description:Gap closer. Fail advantage +4 dmg next attack
Wall Cloud - utility, stat:mobility, mp_cost:10, duration:2, description:Immune to most small ranged attacks
Calm Before - utility, stat:mobility, damage:4, mp_cost:10, description:Reaction auto-dodge afterimage deals 4 reposition
Approaching Storm - light, stat:mobility, damage:5, mp_cost:3, description:If first attack advantage
Gentle Breeze - light, stat:mobility, damage:4, mp_cost:4, star_cost:1, cooldown:1, description:Auto-hit. Reaction when enemy disengages
Eye of the Storm - medium, stat:mobility, damage:6, mp_cost:12, description:Bypass shields. If blocked lose next reaction
Gust Front - medium, stat:mobility, damage:6, mp_cost:12, description:On hit next attack +6 dmg ignores 1 defensive ability
Perfect Storm - heavy, stat:mobility, hits:4, mp_cost:25, cooldown:4, description:4 light attacks roll each. Each after 1st +2 dmg"""

    power = """Veprux's Roar - utility, stat:power, mp_cost:10, description:Next attack +8 dmg ignores reduction
Veprux's Hide - utility, stat:resilience, mp_cost:15, duration:3, description:Reduce incoming by 5. Attackers take 6 on contact
Gryphix's Flight - medium, stat:power, damage:10, mp_cost:12, description:Unstoppable rush. Can follow with another attack
Veprux's Fang - medium, stat:power, damage:12, mp_cost:14, save_type:con, description:Con save or stunned
Veprux's Quake - heavy, stat:power, damage:16, mp_cost:20, save_type:power, cooldown:2, description:Ground slam. Str save or prone
Gryphix's Spite - medium, stat:power, damage:8, mp_cost:10, cooldown:1, description:Reaction when hit strike back. Double if took 10+ dmg"""

    god = """Descend - light, stat:mobility, damage:5, mp_cost:6, description:Drop from above. On hit prone
Descend (Upgraded) - light, stat:mobility, damage:5, mp_cost:6, description:Advantage. 3 force AoE. Requires 1 stack
Orbit - light, stat:technique, damage:6, mp_cost:8, duration:2, description:Halberd attacks autonomously each turn
Orbit (Upgraded) - light, stat:technique, damage:6, mp_cost:8, duration:2, description:Attacks twice per turn. Requires 1 stack
Scatter - medium, stat:mobility, damage:4, hits:4, mp_cost:14, description:4 hits. Each -1 AC stacks
Scatter (Upgraded) - medium, stat:mobility, damage:4, hits:4, mp_cost:14, description:Marks targets. Lightning chains +4. Requires 2 stacks
Eclipse - utility, stat:combat, mp_cost:15, duration:2, description:Enemies dis vs you. You adv on saves
Eclipse (Upgraded) - utility, stat:combat, mp_cost:15, duration:2, description:Also -2 AC all enemies. Requires 2 stacks
Pierce - heavy, stat:technique, damage:18, mp_cost:22, star_cost:3, cooldown:3, description:Ignores all reductions. Cannot be blocked
Pierce (Upgraded) - heavy, stat:technique, damage:18, mp_cost:22, star_cost:3, cooldown:3, description:Also dispel 1 effect. Requires 3 stacks
Severance - heavy, stat:power, damage:20, mp_cost:24, cooldown:3, description:Wind blade. Ignores cover barriers
Severance (Upgraded) - heavy, stat:power, damage:20, mp_cost:24, cooldown:3, description:Hits all in line. Requires 3 stacks
Sunder - heavy, stat:combat, damage:20, mp_cost:25, cooldown:4, description:Adapts to last dmg type. Physical magic status
Sunder (Upgraded) - heavy, stat:combat, damage:20, mp_cost:25, cooldown:4, duration:1, description:Vulnerability for 1 round. Requires 3 stacks
Erupt - utility, stat:combat, mp_cost:12, cooldown:2, description:Reaction nullify dmg. Next attack of that type +10 crit
Erupt (Upgraded) - utility, stat:combat, mp_cost:12, duration:2, cooldown:2, description:Also resistance for 2 rounds. Requires 3 stacks"""

    with open("data/saves/lore/hinobi_base_moveset.txt", "w") as f:
        f.write(base)
    with open("data/saves/lore/hinobi_speed_moveset.txt", "w") as f:
        f.write(speed)
    with open("data/saves/lore/hinobi_power_moveset.txt", "w") as f:
        f.write(power)
    with open("data/saves/lore/hinobi_god_moveset.txt", "w") as f:
        f.write(god)

    print("[OK] Generated all Hinobi moveset files")


async def main():
    print("=== Character Import Tool ===\n")
    await check_schema()
    print()
    await import_characters()
    print()
    print("Generating moveset import files...")
    generate_alicia_moveset()
    generate_hinobi_movesets()
    print("\n[SUCCESS] Import files generated!")
    print("\nNext steps:")
    print("1. Create characters in Discord using /char create commands above")
    print("2. Import movesets using /moveset import and paste from generated .txt files")
    print("3. For Hin'obi forms, use /form add and manually create each form")


if __name__ == "__main__":
    asyncio.run(main())
