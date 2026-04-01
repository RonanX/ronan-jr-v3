"""
Test script for attack system
Tests attack mechanics, star spending, and damage application
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.init_db import init_database, get_db
from utils.dice import roll_pool, check_hit, is_crit, roll_save


async def main():
    print("=== ATTACK SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Create test characters
    print("--- Test 2: Create Test Characters ---")
    db = await get_db()

    # Attacker - high combat
    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Attacker", 100, 100, 50, 50, 12, 30, 3, json.dumps({
            "combat": 4,
            "power": 3,
            "mobility": 2,
            "technique": 2,
            "resilience": 3,
            "focus": 2
        }))
    )

    # Target - high AC
    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Target", 80, 80, 40, 40, 15, 25, 3, json.dumps({
            "combat": 2,
            "power": 2,
            "mobility": 3,
            "technique": 3,
            "resilience": 4,
            "focus": 2
        }))
    )

    await db.commit()
    await db.close()
    print("[OK] Created Attacker and Target\n")

    # Test 3: Start combat and add to initiative
    print("--- Test 3: Setup Combat ---")
    db = await get_db()

    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 1, current_turn_index = 0, turn_order_json = ? WHERE id = 1",
        (json.dumps([
            {"name": "Attacker", "initiative": 20, "roll": 18, "mobility": 2},
            {"name": "Target", "initiative": 18, "roll": 15, "mobility": 3}
        ]),)
    )

    await db.execute("DELETE FROM combat_state")
    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Attacker",)
    )
    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Target",)
    )

    await db.commit()
    await db.close()
    print("[OK] Combat started, Attacker's turn\n")

    # Test 4: Light attack (1 star)
    print("--- Test 4: Light Attack (1 star) ---")
    db = await get_db()

    # Get attacker stats
    async with db.execute(
        "SELECT stats_json FROM characters WHERE name = ?",
        ("Attacker",)
    ) as cursor:
        stats = json.loads((await cursor.fetchone())[0])

    combat_rating = stats["combat"]

    # Get target AC and HP
    async with db.execute(
        "SELECT ac, hp FROM characters WHERE name = ?",
        ("Target",)
    ) as cursor:
        target_ac, target_hp = await cursor.fetchone()

    # Get current stars
    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        ("Attacker",)
    ) as cursor:
        current_stars = (await cursor.fetchone())[0]

    print(f"Attacker has {current_stars} stars")
    print(f"Using Combat rating: {combat_rating}")
    print(f"Target AC: {target_ac}")

    # Roll attack
    pool_result = roll_pool(combat_rating)
    hit_result = check_hit(pool_result.highest, target_ac)
    is_critical = is_crit(pool_result.dice)

    print(f"Dice rolled: {pool_result.dice}")
    print(f"Highest die: {pool_result.highest}")
    print(f"Result: {hit_result.outcome.upper()}")
    print(f"Critical: {is_critical}")

    # Spend 1 star
    new_stars = current_stars - 1
    await db.execute(
        "UPDATE combat_state SET stars = ? WHERE character_name = ?",
        (new_stars, "Attacker")
    )

    # Apply damage if hit
    if hit_result.outcome != "miss":
        damage = 15
        if is_critical:
            damage *= 2
            print(f"CRIT! Damage doubled: {damage}")

        new_hp = max(0, target_hp - damage)
        await db.execute(
            "UPDATE characters SET hp = ? WHERE name = ?",
            (new_hp, "Target")
        )
        print(f"Damage: {damage}")
        print(f"Target HP: {target_hp} -> {new_hp}")

    await db.commit()
    await db.close()
    print(f"Stars remaining: {new_stars}\n")

    # Test 5: Medium attack (2 stars)
    print("--- Test 5: Medium Attack (2 stars) ---")
    db = await get_db()

    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        ("Attacker",)
    ) as cursor:
        current_stars = (await cursor.fetchone())[0]

    async with db.execute(
        "SELECT ac, hp FROM characters WHERE name = ?",
        ("Target",)
    ) as cursor:
        target_ac, target_hp = await cursor.fetchone()

    print(f"Attacker has {current_stars} stars")

    # Roll with power this time
    async with db.execute(
        "SELECT stats_json FROM characters WHERE name = ?",
        ("Attacker",)
    ) as cursor:
        stats = json.loads((await cursor.fetchone())[0])

    power_rating = stats["power"]
    print(f"Using Power rating: {power_rating}")

    pool_result = roll_pool(power_rating)
    hit_result = check_hit(pool_result.highest, target_ac)

    print(f"Dice rolled: {pool_result.dice}")
    print(f"Highest die: {pool_result.highest}")
    print(f"Result: {hit_result.outcome.upper()}")

    # Spend 2 stars
    new_stars = current_stars - 2
    await db.execute(
        "UPDATE combat_state SET stars = ? WHERE character_name = ?",
        (new_stars, "Attacker")
    )

    if hit_result.outcome != "miss":
        damage = 25
        new_hp = max(0, target_hp - damage)
        await db.execute(
            "UPDATE characters SET hp = ? WHERE name = ?",
            (new_hp, "Target")
        )
        print(f"Damage: {damage}")
        print(f"Target HP: {target_hp} -> {new_hp}")

    await db.commit()
    await db.close()
    print(f"Stars remaining: {new_stars}\n")

    # Test 6: Try heavy attack without enough stars
    print("--- Test 6: Heavy Attack - Not Enough Stars ---")
    db = await get_db()

    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        ("Attacker",)
    ) as cursor:
        current_stars = (await cursor.fetchone())[0]

    print(f"Attacker has {current_stars} stars")
    print(f"Heavy attack requires 4 stars")

    if current_stars < 4:
        print("[OK] Cannot perform heavy attack - not enough stars\n")
    else:
        print("[FAIL] Should not have enough stars\n")

    await db.close()

    # Test 7: Saving throw
    print("--- Test 7: Saving Throw ---")
    db = await get_db()

    async with db.execute(
        "SELECT stats_json FROM characters WHERE name = ?",
        ("Target",)
    ) as cursor:
        stats = json.loads((await cursor.fetchone())[0])

    resilience = stats["resilience"]
    dc = 15

    save_result = roll_save(resilience, dc)

    print(f"Target rolls Resilience save")
    print(f"Resilience rating: {resilience}")
    print(f"Roll: {save_result.roll} + {save_result.modifier} = {save_result.total}")
    print(f"DC: {dc}")
    print(f"Result: {'SUCCESS' if save_result.success else 'FAILURE'}\n")

    await db.close()

    # Test 8: Refresh stars for next turn
    print("--- Test 8: Next Turn - Refresh Stars ---")
    db = await get_db()

    # Advance turn (Target's turn now)
    await db.execute(
        "UPDATE initiative SET current_turn_index = 1 WHERE id = 1"
    )

    # Refresh Target's stars
    await db.execute(
        "UPDATE combat_state SET stars = 5 WHERE character_name = ?",
        ("Target",)
    )

    await db.commit()

    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        ("Target",)
    ) as cursor:
        target_stars = (await cursor.fetchone())[0]

    print(f"Target's turn - Stars refreshed to {target_stars}\n")

    await db.close()

    # Test 9: Multiple attacks in one turn
    print("--- Test 9: Multiple Light Attacks ---")
    db = await get_db()

    # Set Attacker back to current turn with 5 stars
    await db.execute(
        "UPDATE initiative SET current_turn_index = 0 WHERE id = 1"
    )
    await db.execute(
        "UPDATE combat_state SET stars = 5 WHERE character_name = ?",
        ("Attacker",)
    )
    await db.commit()

    attacks_made = 0
    current_stars = 5

    print(f"Starting with {current_stars} stars")

    # Simulate 3 light attacks
    for i in range(3):
        if current_stars >= 1:
            pool_result = roll_pool(combat_rating)
            hit_result = check_hit(pool_result.highest, target_ac)

            print(f"Attack {i+1}: {pool_result.dice} -> {pool_result.highest} -> {hit_result.outcome.upper()}")

            current_stars -= 1
            attacks_made += 1

            # If miss, stop attacking
            if hit_result.outcome == "miss":
                print("  MISS - Combo broken!")
                break

    await db.execute(
        "UPDATE combat_state SET stars = ? WHERE character_name = ?",
        (current_stars, "Attacker")
    )
    await db.commit()
    await db.close()

    print(f"Made {attacks_made} attacks, {current_stars} stars remaining\n")

    # Test 10: Check final state
    print("--- Test 10: Final State ---")
    db = await get_db()

    async with db.execute(
        "SELECT name, hp, max_hp FROM characters WHERE name IN ('Attacker', 'Target')"
    ) as cursor:
        chars = await cursor.fetchall()

    for name, hp, max_hp in chars:
        print(f"{name}: {hp}/{max_hp} HP")

    async with db.execute(
        "SELECT character_name, stars FROM combat_state"
    ) as cursor:
        combat_states = await cursor.fetchall()

    for name, stars in combat_states:
        print(f"{name}: {stars} stars")

    await db.close()

    print()
    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
