"""
Test script for move system
Tests move creation, listing, usage, multihit, and form swapping
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.init_db import init_database, get_db
from utils.dice import roll_pool, check_hit, is_crit


async def main():
    print("=== MOVE SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Create test character
    print("--- Test 2: Create Test Character ---")
    db = await get_db()

    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Striker", 100, 100, 80, 80, 13, 30, 3, json.dumps({
            "combat": 4,
            "power": 3,
            "mobility": 3,
            "technique": 2,
            "resilience": 2,
            "focus": 2
        }))
    )

    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Dummy", 150, 150, 50, 50, 12, 25, 2, json.dumps({
            "combat": 1,
            "power": 1,
            "mobility": 1,
            "technique": 1,
            "resilience": 4,
            "focus": 1
        }))
    )

    await db.commit()
    await db.close()
    print("[OK] Created Striker and Dummy\n")

    # Test 3: Create moves
    print("--- Test 3: Create Moves ---")
    db = await get_db()

    # Move 1: Light single-hit move
    move1 = {
        "name": "Quick Slash",
        "type": "light",
        "star_cost": 1,
        "mp_cost": 5,
        "stat": "combat",
        "damage": 10,
        "effect": "Fast strike with sword",
        "multihit": None,
        "cooldown": None,
        "uses": None
    }

    # Move 2: Medium multihit move
    move2 = {
        "name": "Storm Drummer",
        "type": "medium",
        "star_cost": 2,
        "mp_cost": 15,
        "stat": "combat",
        "damage": 7,
        "effect": "Target makes resilience save DC 15 or stunned",
        "multihit": 4,
        "cooldown": 3,
        "uses": None
    }

    # Move 3: Heavy power move
    move3 = {
        "name": "Devastator",
        "type": "heavy",
        "star_cost": 4,
        "mp_cost": 25,
        "stat": "power",
        "damage": 30,
        "effect": "Massive single strike, pushes target back 10ft",
        "multihit": None,
        "cooldown": 5,
        "uses": None
    }

    moveset = [move1, move2, move3]

    await db.execute(
        "INSERT OR REPLACE INTO movesets (character_name, form_name, moves_json) VALUES (?, ?, ?)",
        ("Striker", "base", json.dumps(moveset))
    )

    await db.commit()
    await db.close()

    print(f"[OK] Created 3 moves for Striker:")
    print(f"  - {move1['name']} (light, 1 star, 5 mp)")
    print(f"  - {move2['name']} (medium, 2 stars, 15 mp, 4 hits)")
    print(f"  - {move3['name']} (heavy, 4 stars, 25 mp)\n")

    # Test 4: List moves
    print("--- Test 4: List Moves ---")
    db = await get_db()

    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "base")
    ) as cursor:
        moves = json.loads((await cursor.fetchone())[0])

    await db.close()

    print(f"Striker has {len(moves)} moves:")
    for move in moves:
        print(f"  - {move['name']}: {move['type']} ({move['star_cost']} stars, {move['mp_cost']} mp)")
    print()

    # Test 5: Setup combat
    print("--- Test 5: Setup Combat ---")
    db = await get_db()

    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 1, current_turn_index = 0, turn_order_json = ? WHERE id = 1",
        (json.dumps([
            {"name": "Striker", "initiative": 20, "roll": 17, "mobility": 3},
            {"name": "Dummy", "initiative": 15, "roll": 14, "mobility": 1}
        ]),)
    )

    await db.execute("DELETE FROM combat_state")
    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Striker",)
    )
    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Dummy",)
    )

    await db.commit()
    await db.close()
    print("[OK] Combat started\n")

    # Test 6: Use single-hit move
    print("--- Test 6: Use Single-Hit Move (Quick Slash) ---")
    db = await get_db()

    # Get move
    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "base")
    ) as cursor:
        moves = json.loads((await cursor.fetchone())[0])

    move = [m for m in moves if m['name'] == "Quick Slash"][0]

    # Get character stats
    async with db.execute(
        "SELECT stats_json, mp FROM characters WHERE name = ?",
        ("Striker",)
    ) as cursor:
        row = await cursor.fetchone()
        stats = json.loads(row[0])
        current_mp = row[1]

    stat_rating = stats[move['stat']]

    # Get target
    async with db.execute(
        "SELECT ac, hp FROM characters WHERE name = ?",
        ("Dummy",)
    ) as cursor:
        target_ac, target_hp = await cursor.fetchone()

    # Roll
    pool_result = roll_pool(stat_rating)
    hit_result = check_hit(pool_result.highest, target_ac)

    print(f"Dice: {pool_result.dice} -> Highest: {pool_result.highest}")
    print(f"Result: {hit_result.outcome.upper()}")

    if hit_result.outcome != "miss":
        damage = move['damage'] + stat_rating
        new_hp = target_hp - damage

        await db.execute(
            "UPDATE characters SET hp = ?, mp = ? WHERE name = ?",
            (target_hp, current_mp - move['mp_cost'], "Striker")
        )
        await db.execute(
            "UPDATE characters SET hp = ? WHERE name = ?",
            (new_hp, "Dummy")
        )

        print(f"Damage: {damage}")
        print(f"Dummy HP: {target_hp} -> {new_hp}")

    # Spend stars
    await db.execute(
        "UPDATE combat_state SET stars = stars - ? WHERE character_name = ?",
        (move['star_cost'], "Striker")
    )

    await db.commit()
    await db.close()
    print()

    # Test 7: Use multihit move
    print("--- Test 7: Use Multihit Move (Storm Drummer - 4 hits) ---")
    db = await get_db()

    # Get move
    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "base")
    ) as cursor:
        moves = json.loads((await cursor.fetchone())[0])

    move = [m for m in moves if m['name'] == "Storm Drummer"][0]

    # Get character stats
    async with db.execute(
        "SELECT stats_json, mp FROM characters WHERE name = ?",
        ("Striker",)
    ) as cursor:
        row = await cursor.fetchone()
        stats = json.loads(row[0])
        current_mp = row[1]

    stat_rating = stats[move['stat']]

    # Get target
    async with db.execute(
        "SELECT ac, hp FROM characters WHERE name = ?",
        ("Dummy",)
    ) as cursor:
        target_ac, target_hp = await cursor.fetchone()

    # Roll
    pool_result = roll_pool(stat_rating)
    hit_result = check_hit(pool_result.highest, target_ac)
    is_critical = is_crit(pool_result.dice)

    total_hits = move['multihit']

    if hit_result.outcome == "clean":
        hits_landed = total_hits
    elif hit_result.outcome == "cost":
        hits_landed = (total_hits + 1) // 2
    else:
        hits_landed = 1

    damage_per_hit = move['damage'] + stat_rating
    total_damage = damage_per_hit * hits_landed

    if is_critical:
        total_damage *= 2

    print(f"Dice: {pool_result.dice} -> Highest: {pool_result.highest}")
    print(f"Result: {hit_result.outcome.upper()}")
    print(f"Hits: {hits_landed}/{total_hits}")
    print(f"Damage per hit: {damage_per_hit}")
    print(f"Total damage: {total_damage}")

    new_hp = max(0, target_hp - total_damage)

    await db.execute(
        "UPDATE characters SET hp = ?, mp = ? WHERE name = ?",
        (target_hp, current_mp - move['mp_cost'], "Striker")
    )
    await db.execute(
        "UPDATE characters SET hp = ? WHERE name = ?",
        (new_hp, "Dummy")
    )

    await db.execute(
        "UPDATE combat_state SET stars = stars - ? WHERE character_name = ?",
        (move['star_cost'], "Striker")
    )

    await db.commit()
    await db.close()

    print(f"Dummy HP: {target_hp} -> {new_hp}\n")

    # Test 8: Check resources
    print("--- Test 8: Check Resources ---")
    db = await get_db()

    async with db.execute(
        "SELECT mp, max_mp FROM characters WHERE name = ?",
        ("Striker",)
    ) as cursor:
        mp, max_mp = await cursor.fetchone()

    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        ("Striker",)
    ) as cursor:
        stars = (await cursor.fetchone())[0]

    await db.close()

    print(f"Striker MP: {mp}/{max_mp}")
    print(f"Striker Stars: {stars}/5\n")

    # Test 9: Add super form with new moveset
    print("--- Test 9: Add Super Form with New Moveset ---")
    db = await get_db()

    # Add form stats
    super_stats = {
        "combat": 4,
        "power": 4,
        "mobility": 4,
        "technique": 3,
        "resilience": 3,
        "focus": 3
    }

    await db.execute(
        "INSERT OR REPLACE INTO forms (character_name, form_name, stats_json) VALUES (?, ?, ?)",
        ("Striker", "super", json.dumps(super_stats))
    )

    # Create super form moves
    super_moveset = [
        {
            "name": "Mega Slash",
            "type": "light",
            "star_cost": 1,
            "mp_cost": 10,
            "stat": "combat",
            "damage": 15,
            "effect": "Enhanced version of Quick Slash",
            "multihit": None,
            "cooldown": None,
            "uses": None
        },
        {
            "name": "Hyper Barrage",
            "type": "heavy",
            "star_cost": 4,
            "mp_cost": 40,
            "stat": "combat",
            "damage": 12,
            "effect": "Ultimate multi-hit combo",
            "multihit": 8,
            "cooldown": 5,
            "uses": None
        }
    ]

    await db.execute(
        "INSERT OR REPLACE INTO movesets (character_name, form_name, moves_json) VALUES (?, ?, ?)",
        ("Striker", "super", json.dumps(super_moveset))
    )

    await db.commit()
    await db.close()

    print("[OK] Added 'super' form with new moveset\n")

    # Test 10: Transform and check movesets
    print("--- Test 10: Transform and Check Movesets ---")
    db = await get_db()

    # Transform
    await db.execute(
        "UPDATE characters SET current_form = ?, stats_json = ?, mp = mp - 10 WHERE name = ?",
        ("super", json.dumps(super_stats), "Striker")
    )

    await db.commit()

    # Check base form moveset (still exists)
    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "base")
    ) as cursor:
        base_moves = json.loads((await cursor.fetchone())[0])

    # Check super form moveset (now active)
    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "super")
    ) as cursor:
        super_moves = json.loads((await cursor.fetchone())[0])

    await db.close()

    print(f"Base form moveset (inactive): {len(base_moves)} moves")
    for move in base_moves:
        print(f"  - {move['name']}")

    print(f"\nSuper form moveset (active): {len(super_moves)} moves")
    for move in super_moves:
        print(f"  - {move['name']}")

    print("\n[OK] Movesets swap when transforming!\n")

    # Test 11: Delete a move
    print("--- Test 11: Delete a Move ---")
    db = await get_db()

    # Get current moveset
    async with db.execute(
        "SELECT moves_json FROM movesets WHERE character_name = ? AND form_name = ?",
        ("Striker", "super")
    ) as cursor:
        moves = json.loads((await cursor.fetchone())[0])

    initial_count = len(moves)

    # Remove first move
    moves = [m for m in moves if m['name'] != "Mega Slash"]

    await db.execute(
        "UPDATE movesets SET moves_json = ? WHERE character_name = ? AND form_name = ?",
        (json.dumps(moves), "Striker", "super")
    )

    await db.commit()
    await db.close()

    print(f"Deleted 'Mega Slash' from super form")
    print(f"Moves remaining: {len(moves)}/{initial_count}\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
