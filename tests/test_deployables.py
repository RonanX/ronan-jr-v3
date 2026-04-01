"""
Test script for deployable system
Tests deployable creation, attacking, damage, and expiration
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.init_db import init_database, get_db
from utils.dice import roll_pool, check_hit, is_crit


async def main():
    print("=== DEPLOYABLE SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Create test characters
    print("--- Test 2: Create Test Characters ---")
    db = await get_db()

    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Summoner", 90, 90, 100, 100, 12, 30, 3, json.dumps({
            "combat": 2,
            "power": 4,
            "mobility": 2,
            "technique": 4,
            "resilience": 2,
            "focus": 4
        }))
    )

    await db.execute(
        """
        INSERT OR REPLACE INTO characters
        (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
        """,
        ("Enemy", 120, 120, 50, 50, 13, 25, 2, json.dumps({
            "combat": 3,
            "power": 3,
            "mobility": 2,
            "technique": 2,
            "resilience": 3,
            "focus": 1
        }))
    )

    await db.commit()
    await db.close()
    print("[OK] Created Summoner and Enemy\n")

    # Test 3: Setup combat
    print("--- Test 3: Setup Combat ---")
    db = await get_db()

    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 1, current_turn_index = 0, turn_order_json = ? WHERE id = 1",
        (json.dumps([
            {"name": "Summoner", "initiative": 18, "roll": 16, "mobility": 2},
            {"name": "Enemy", "initiative": 15, "roll": 13, "mobility": 2}
        ]),)
    )

    await db.execute("DELETE FROM combat_state")
    await db.execute("DELETE FROM deployables")

    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Summoner",)
    )
    await db.execute(
        "INSERT INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
        ("Enemy",)
    )

    await db.commit()
    await db.close()
    print("[OK] Combat started, Summoner's turn\n")

    # Test 4: Create deployables
    print("--- Test 4: Create Deployables ---")
    db = await get_db()

    # Create Turret (3 stars, 3 duration)
    await db.execute(
        """
        INSERT INTO deployables (name, owner, hp, max_hp, stars, max_stars, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("Turret", "Summoner", 30, 30, 3, 3, 3)
    )

    # Create Drone (2 stars, 2 duration)
    await db.execute(
        """
        INSERT INTO deployables (name, owner, hp, max_hp, stars, max_stars, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("Drone", "Summoner", 20, 20, 2, 2, 2)
    )

    await db.commit()
    await db.close()

    print("[OK] Created 2 deployables:")
    print("  - Turret: 30 HP, 3 stars/turn, 3 rounds")
    print("  - Drone: 20 HP, 2 stars/turn, 2 rounds\n")

    # Test 5: List deployables
    print("--- Test 5: List Deployables ---")
    db = await get_db()

    async with db.execute(
        "SELECT name, owner, hp, max_hp, stars, max_stars, duration FROM deployables"
    ) as cursor:
        deployables = await cursor.fetchall()

    await db.close()

    for name, owner, hp, max_hp, stars, max_stars, duration in deployables:
        print(f"{name} (Owner: {owner})")
        print(f"  HP: {hp}/{max_hp} | Stars: {stars}/{max_stars} | Duration: {duration} rounds")

    print()

    # Test 6: Deployable attacks
    print("--- Test 6: Turret Attacks Enemy ---")
    db = await get_db()

    # Get turret
    async with db.execute(
        "SELECT owner, hp, stars FROM deployables WHERE name = ?",
        ("Turret",)
    ) as cursor:
        owner, turret_hp, turret_stars = await cursor.fetchone()

    # Get target
    async with db.execute(
        "SELECT ac, hp FROM characters WHERE name = ?",
        ("Enemy",)
    ) as cursor:
        target_ac, target_hp = await cursor.fetchone()

    # Roll attack (using stat rating 3)
    stat_rating = 3
    pool_result = roll_pool(stat_rating)
    hit_result = check_hit(pool_result.highest, target_ac)

    print(f"Turret attacks Enemy")
    print(f"Dice: {pool_result.dice} -> Highest: {pool_result.highest}")
    print(f"Result: {hit_result.outcome.upper()}")

    # Spend star
    new_turret_stars = turret_stars - 1
    await db.execute(
        "UPDATE deployables SET stars = ? WHERE name = ?",
        (new_turret_stars, "Turret")
    )

    if hit_result.outcome != "miss":
        damage = 12
        new_hp = target_hp - damage

        await db.execute(
            "UPDATE characters SET hp = ? WHERE name = ?",
            (new_hp, "Enemy")
        )

        print(f"Damage: {damage}")
        print(f"Enemy HP: {target_hp} -> {new_hp}")

    print(f"Turret stars: {turret_stars} -> {new_turret_stars}\n")

    await db.commit()
    await db.close()

    # Test 7: Damage deployable
    print("--- Test 7: Damage Drone ---")
    db = await get_db()

    async with db.execute(
        "SELECT hp, max_hp FROM deployables WHERE name = ?",
        ("Drone",)
    ) as cursor:
        drone_hp, drone_max_hp = await cursor.fetchone()

    damage = 15
    new_drone_hp = max(0, drone_hp - damage)

    if new_drone_hp == 0:
        await db.execute("DELETE FROM deployables WHERE name = ?", ("Drone",))
        print(f"Drone takes {damage} damage and is destroyed!")
    else:
        await db.execute(
            "UPDATE deployables SET hp = ? WHERE name = ?",
            (new_drone_hp, "Drone")
        )
        print(f"Drone takes {damage} damage ({new_drone_hp}/{drone_max_hp} HP)")

    await db.commit()
    await db.close()
    print()

    # Test 8: Advance turn (refresh stars, decrement duration)
    print("--- Test 8: Advance Turn ---")
    db = await get_db()

    # Get current index
    async with db.execute(
        "SELECT current_turn_index, round_number FROM initiative WHERE id = 1"
    ) as cursor:
        current_idx, round_num = await cursor.fetchone()

    # Advance to next turn (Enemy's turn)
    current_idx += 1
    if current_idx >= 2:
        current_idx = 0
        round_num += 1

    # Update initiative
    await db.execute(
        "UPDATE initiative SET round_number = ?, current_turn_index = ? WHERE id = 1",
        (round_num, current_idx)
    )

    await db.commit()
    print(f"Advanced to round {round_num}, turn index {current_idx}\n")

    # Test 9: Advance back to Summoner's turn
    print("--- Test 9: Advance to Summoner's Turn ---")

    # Advance again (back to Summoner)
    current_idx += 1
    if current_idx >= 2:
        current_idx = 0
        round_num += 1

    await db.execute(
        "UPDATE initiative SET round_number = ?, current_turn_index = ? WHERE id = 1",
        (round_num, current_idx)
    )

    # Refresh deployable stars
    await db.execute(
        "UPDATE deployables SET stars = max_stars WHERE owner = ?",
        ("Summoner",)
    )

    # Decrement duration
    await db.execute(
        "UPDATE deployables SET duration = duration - 1 WHERE owner = ?",
        ("Summoner",)
    )

    # Get expired
    async with db.execute(
        "SELECT name FROM deployables WHERE owner = ? AND duration <= 0",
        ("Summoner",)
    ) as cursor:
        expired = [row[0] for row in await cursor.fetchall()]

    # Remove expired
    await db.execute(
        "DELETE FROM deployables WHERE owner = ? AND duration <= 0",
        ("Summoner",)
    )

    await db.commit()

    print(f"Round {round_num} - Summoner's turn")
    print("Refreshed deployable stars")
    print("Decremented deployable durations")

    if expired:
        print(f"Expired deployables: {', '.join(expired)}")

    # Check remaining deployables
    async with db.execute(
        "SELECT name, stars, max_stars, duration FROM deployables WHERE owner = ?",
        ("Summoner",)
    ) as cursor:
        remaining = await cursor.fetchall()

    if remaining:
        print("\nRemaining deployables:")
        for name, stars, max_stars, duration in remaining:
            print(f"  {name}: {stars}/{max_stars} stars, {duration} rounds left")
    else:
        print("\nNo remaining deployables")

    await db.close()
    print()

    # Test 10: Continue advancing until all deployables expire
    print("--- Test 10: Advance Until All Expired ---")

    for i in range(5):
        db = await get_db()

        # Get current state
        async with db.execute(
            "SELECT current_turn_index, round_number FROM initiative WHERE id = 1"
        ) as cursor:
            current_idx, round_num = await cursor.fetchone()

        # Advance
        current_idx += 1
        if current_idx >= 2:
            current_idx = 0
            round_num += 1

        await db.execute(
            "UPDATE initiative SET round_number = ?, current_turn_index = ? WHERE id = 1",
            (round_num, current_idx)
        )

        # If Summoner's turn, handle deployables
        if current_idx == 0:
            await db.execute(
                "UPDATE deployables SET stars = max_stars WHERE owner = ?",
                ("Summoner",)
            )

            await db.execute(
                "UPDATE deployables SET duration = duration - 1 WHERE owner = ?",
                ("Summoner",)
            )

            async with db.execute(
                "SELECT name FROM deployables WHERE owner = ? AND duration <= 0",
                ("Summoner",)
            ) as cursor:
                expired = [row[0] for row in await cursor.fetchall()]

            await db.execute(
                "DELETE FROM deployables WHERE owner = ? AND duration <= 0",
                ("Summoner",)
            )

            if expired:
                print(f"Round {round_num}: Expired {', '.join(expired)}")

        await db.commit()
        await db.close()

    # Check final state
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM deployables"
    ) as cursor:
        count = (await cursor.fetchone())[0]

    await db.close()

    print(f"\nFinal deployable count: {count}")

    if count == 0:
        print("[OK] All deployables expired properly\n")
    else:
        print("[FAIL] Some deployables still remain\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
