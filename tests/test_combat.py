"""
Test script for combat and initiative system
Tests initiative, turn tracking, stars, and effects
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.init_db import init_database, get_db


async def main():
    print("=== COMBAT SYSTEM TESTS ===\n")

    # Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Create test characters
    print("--- Test 2: Create Test Characters ---")
    test_chars = [
        {
            "name": "Fighter",
            "hp": 100,
            "max_hp": 100,
            "mp": 40,
            "max_mp": 40,
            "ac": 14,
            "movement": 30,
            "proficiency": 3,
            "stats": json.dumps({
                "combat": 4,
                "power": 3,
                "mobility": 2,
                "technique": 2,
                "resilience": 4,
                "focus": 1
            })
        },
        {
            "name": "Rogue",
            "hp": 80,
            "max_hp": 80,
            "mp": 50,
            "max_mp": 50,
            "ac": 15,
            "movement": 35,
            "proficiency": 3,
            "stats": json.dumps({
                "combat": 3,
                "power": 2,
                "mobility": 4,
                "technique": 3,
                "resilience": 2,
                "focus": 2
            })
        },
        {
            "name": "Wizard",
            "hp": 60,
            "max_hp": 60,
            "mp": 80,
            "max_mp": 80,
            "ac": 12,
            "movement": 25,
            "proficiency": 3,
            "stats": json.dumps({
                "combat": 1,
                "power": 4,
                "mobility": 1,
                "technique": 4,
                "resilience": 2,
                "focus": 4
            })
        }
    ]

    db = await get_db()
    for char in test_chars:
        await db.execute(
            """
            INSERT OR REPLACE INTO characters
            (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'base')
            """,
            (char["name"], char["hp"], char["max_hp"], char["mp"], char["max_mp"],
             char["ac"], char["movement"], char["proficiency"], char["stats"])
        )
    await db.commit()
    await db.close()
    print("[OK] Created Fighter, Rogue, Wizard\n")

    # Test 3: Start combat
    print("--- Test 3: Start Combat ---")
    db = await get_db()
    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 0, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
    )
    await db.execute("DELETE FROM combat_state")
    await db.commit()
    await db.close()
    print("[OK] Combat started\n")

    # Test 4: Add characters to initiative
    print("--- Test 4: Add Characters to Initiative ---")
    initiative_rolls = []

    for char in test_chars:
        db = await get_db()
        async with db.execute(
            "SELECT stats_json FROM characters WHERE name = ?",
            (char["name"],)
        ) as cursor:
            row = await cursor.fetchone()

        stats = json.loads(row[0])
        mobility = stats.get("mobility", 0)

        # Simulate roll
        import random
        roll = random.randint(1, 20)
        initiative = roll + mobility

        # Get turn order
        async with db.execute(
            "SELECT turn_order_json FROM initiative WHERE id = 1"
        ) as cursor:
            turn_order = json.loads((await cursor.fetchone())[0])

        # Add to turn order
        turn_order.append({
            "name": char["name"],
            "initiative": initiative,
            "roll": roll,
            "mobility": mobility
        })

        # Sort
        turn_order.sort(key=lambda x: (x["initiative"], x["mobility"]), reverse=True)

        # Save
        await db.execute(
            "UPDATE initiative SET turn_order_json = ? WHERE id = 1",
            (json.dumps(turn_order),)
        )

        # Add to combat state
        await db.execute(
            "INSERT OR REPLACE INTO combat_state (character_name, stars, effects_json) VALUES (?, 5, '[]')",
            (char["name"],)
        )

        await db.commit()
        await db.close()

        print(f"{char['name']}: {roll} + {mobility} (mobility) = {initiative}")
        initiative_rolls.append((char["name"], initiative))

    print()

    # Test 5: Show turn order
    print("--- Test 5: Show Turn Order ---")
    db = await get_db()
    async with db.execute(
        "SELECT turn_order_json FROM initiative WHERE id = 1"
    ) as cursor:
        turn_order = json.loads((await cursor.fetchone())[0])
    await db.close()

    for i, entry in enumerate(turn_order):
        print(f"{i+1}. {entry['name']} ({entry['initiative']})")
    print()

    # Test 6: Add effects
    print("--- Test 6: Add Status Effects ---")
    db = await get_db()

    # Add Haste to Rogue
    async with db.execute(
        "SELECT effects_json FROM combat_state WHERE character_name = ?",
        ("Rogue",)
    ) as cursor:
        effects = json.loads((await cursor.fetchone())[0])

    effects.append({"name": "Haste", "duration": 3})

    await db.execute(
        "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
        (json.dumps(effects), "Rogue")
    )

    # Add Shield to Fighter
    async with db.execute(
        "SELECT effects_json FROM combat_state WHERE character_name = ?",
        ("Fighter",)
    ) as cursor:
        effects = json.loads((await cursor.fetchone())[0])

    effects.append({"name": "Shield", "duration": 2})

    await db.execute(
        "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
        (json.dumps(effects), "Fighter")
    )

    await db.commit()
    await db.close()

    print("[OK] Added 'Haste' to Rogue (3 rounds)")
    print("[OK] Added 'Shield' to Fighter (2 rounds)\n")

    # Test 7: Advance turns and watch effects tick down
    print("--- Test 7: Advance Turns (Watch Effects) ---")

    for turn_num in range(5):
        db = await get_db()

        async with db.execute(
            "SELECT round_number, current_turn_index, turn_order_json FROM initiative WHERE id = 1"
        ) as cursor:
            row = await cursor.fetchone()
            round_num, current_idx, turn_order_json = row
            turn_order = json.loads(turn_order_json)

        # Advance turn
        current_idx += 1
        if current_idx >= len(turn_order):
            current_idx = 0
            round_num += 1

        current_char = turn_order[current_idx]["name"]

        # Refresh stars
        await db.execute(
            "UPDATE combat_state SET stars = 5 WHERE character_name = ?",
            (current_char,)
        )

        # Get and decrement effects
        async with db.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            (current_char,)
        ) as cursor:
            effects = json.loads((await cursor.fetchone())[0])

        updated_effects = []
        expired = []
        for effect in effects:
            effect["duration"] -= 1
            if effect["duration"] > 0:
                updated_effects.append(effect)
            else:
                expired.append(effect["name"])

        # Save
        await db.execute(
            "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
            (json.dumps(updated_effects), current_char)
        )

        await db.execute(
            "UPDATE initiative SET round_number = ?, current_turn_index = ? WHERE id = 1",
            (round_num, current_idx)
        )

        await db.commit()
        await db.close()

        print(f"Round {round_num} - {current_char}'s turn")
        if updated_effects:
            effects_str = ", ".join([f"{e['name']} ({e['duration']})" for e in updated_effects])
            print(f"  Active effects: {effects_str}")
        if expired:
            print(f"  Expired: {', '.join(expired)}")

    print()

    # Test 8: Spend stars
    print("--- Test 8: Spend Stars ---")
    db = await get_db()

    async with db.execute(
        "SELECT current_turn_index, turn_order_json FROM initiative WHERE id = 1"
    ) as cursor:
        row = await cursor.fetchone()
        current_char = json.loads(row[1])[row[0]]["name"]

    async with db.execute(
        "SELECT stars FROM combat_state WHERE character_name = ?",
        (current_char,)
    ) as cursor:
        current_stars = (await cursor.fetchone())[0]

    # Spend 3 stars
    new_stars = current_stars - 3
    await db.execute(
        "UPDATE combat_state SET stars = ? WHERE character_name = ?",
        (new_stars, current_char)
    )

    await db.commit()
    await db.close()

    print(f"{current_char} spent 3 stars ({new_stars} remaining)\n")

    # Test 9: List effects
    print("--- Test 9: List All Character Effects ---")
    db = await get_db()

    for char in test_chars:
        async with db.execute(
            "SELECT effects_json FROM combat_state WHERE character_name = ?",
            (char["name"],)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                effects = json.loads(row[0])
                if effects:
                    effects_str = ", ".join([f"{e['name']} ({e['duration']})" for e in effects])
                    print(f"{char['name']}: {effects_str}")
                else:
                    print(f"{char['name']}: No effects")

    await db.close()
    print()

    # Test 10: End combat
    print("--- Test 10: End Combat ---")
    db = await get_db()
    await db.execute(
        "UPDATE initiative SET combat_active = 0, round_number = 0, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
    )
    await db.execute("DELETE FROM combat_state")
    await db.commit()
    await db.close()
    print("[OK] Combat ended, state cleared\n")

    # Test 11: Verify combat ended
    print("--- Test 11: Verify Combat Cleared ---")
    db = await get_db()

    async with db.execute(
        "SELECT combat_active, turn_order_json FROM initiative WHERE id = 1"
    ) as cursor:
        row = await cursor.fetchone()
        is_active = row[0]
        turn_order = json.loads(row[1])

    async with db.execute("SELECT COUNT(*) FROM combat_state") as cursor:
        combat_state_count = (await cursor.fetchone())[0]

    await db.close()

    if is_active == 0 and len(turn_order) == 0 and combat_state_count == 0:
        print("[OK] Combat fully cleared")
    else:
        print("[FAIL] Combat not properly cleared")

    print()
    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
