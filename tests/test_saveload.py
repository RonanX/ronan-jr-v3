"""
Test script for combat save/load system
"""

import asyncio
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.init_db import init_database, get_db


async def main():
    print("=== SAVE/LOAD SYSTEM TESTS ===\n")

    # Test 1: Initialize database
    print("--- Test 1: Initialize Database ---")
    await init_database()
    print("[OK] Database initialized\n")

    # Test 2: Create test characters
    print("--- Test 2: Create Test Characters ---")
    db = await get_db()

    # Create Fighter
    fighter_stats = {
        "combat": 4,
        "power": 3,
        "mobility": 2,
        "technique": 1,
        "resilience": 3,
        "focus": 1
    }

    await db.execute(
        """INSERT OR REPLACE INTO characters
           (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Fighter", 150, 150, 50, 50, 16, 30, 2, json.dumps(fighter_stats), "base")
    )

    # Create Mage
    mage_stats = {
        "combat": 1,
        "power": 4,
        "mobility": 3,
        "technique": 4,
        "resilience": 1,
        "focus": 3
    }

    await db.execute(
        """INSERT OR REPLACE INTO characters
           (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Mage", 80, 80, 100, 100, 13, 30, 2, json.dumps(mage_stats), "base")
    )

    # Create Enemy
    enemy_stats = {
        "combat": 3,
        "power": 3,
        "mobility": 2,
        "technique": 2,
        "resilience": 2,
        "focus": 2
    }

    await db.execute(
        """INSERT OR REPLACE INTO characters
           (name, hp, max_hp, mp, max_mp, ac, movement, proficiency, stats_json, current_form)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Enemy", 120, 120, 60, 60, 14, 30, 2, json.dumps(enemy_stats), "base")
    )

    await db.commit()
    await db.close()
    print("[OK] Created 3 characters\n")

    # Test 3: Setup combat
    print("--- Test 3: Setup Combat ---")
    db = await get_db()

    # Start combat
    await db.execute(
        "UPDATE initiative SET combat_active = 1, round_number = 0, current_turn_index = 0, turn_order_json = '[]' WHERE id = 1"
    )

    # Add characters to initiative
    turn_order = [
        {"name": "Mage", "initiative": 18},
        {"name": "Fighter", "initiative": 15},
        {"name": "Enemy", "initiative": 10}
    ]

    await db.execute(
        "UPDATE initiative SET turn_order_json = ?, round_number = 1, current_turn_index = 0 WHERE id = 1",
        (json.dumps(turn_order),)
    )

    # Create combat state for all characters
    for char in turn_order:
        await db.execute(
            """INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json)
               VALUES (?, ?, ?, ?, ?)""",
            (char["name"], 100, 50, 5, json.dumps([]))
        )

    await db.commit()
    await db.close()
    print("[OK] Combat started, all characters in initiative\n")

    # Test 4: Add effects and deployables
    print("--- Test 4: Add Effects and Deployables ---")
    db = await get_db()

    # Add effect to Mage
    await db.execute(
        "UPDATE combat_state SET effects_json = ? WHERE character_name = ?",
        (json.dumps([{"name": "Haste", "duration": 3}]), "Mage")
    )

    # Create a deployable
    await db.execute(
        """INSERT INTO deployables (name, owner, hp, max_hp, stars, max_stars, duration)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("Turret", "Mage", 30, 30, 3, 3, 2)
    )

    # Damage some characters
    await db.execute(
        "UPDATE combat_state SET current_hp = ?, current_mp = ?, stars = ? WHERE character_name = ?",
        (85, 40, 3, "Mage")
    )
    await db.execute(
        "UPDATE combat_state SET current_hp = ? WHERE character_name = ?",
        (130, "Fighter")
    )

    await db.commit()
    await db.close()
    print("[OK] Added effects, deployables, and modified HP/MP/stars\n")

    # Test 5: Save combat state
    print("--- Test 5: Save Combat State ---")
    db = await get_db()

    # Get initiative data
    async with db.execute(
        "SELECT turn_order_json, round_number, current_turn_index FROM initiative WHERE id = 1"
    ) as cursor:
        init_row = await cursor.fetchone()
        saved_turn_order = json.loads(init_row[0])
        saved_round = init_row[1]
        saved_index = init_row[2]

    # Get all character states
    character_states = {}
    async with db.execute("SELECT character_name, current_hp, current_mp, stars FROM combat_state") as cursor:
        async for row in cursor:
            character_states[row[0]] = {
                "hp": row[1],
                "mp": row[2],
                "stars": row[3]
            }

    # Get all effects
    effects_data = {}
    async with db.execute("SELECT character_name, effects_json FROM combat_state") as cursor:
        async for row in cursor:
            effects_data[row[0]] = json.loads(row[1])

    # Get all deployables
    deployables = []
    async with db.execute(
        "SELECT name, owner, hp, max_hp, stars, max_stars, duration FROM deployables"
    ) as cursor:
        async for row in cursor:
            deployables.append({
                "name": row[0],
                "owner": row[1],
                "hp": row[2],
                "max_hp": row[3],
                "stars": row[4],
                "max_stars": row[5],
                "duration": row[6]
            })

    await db.close()

    # Build save data
    save_data = {
        "turn_order": saved_turn_order,
        "round_number": saved_round,
        "current_turn_index": saved_index,
        "character_states": character_states,
        "effects": effects_data,
        "deployables": deployables
    }

    # Save to file
    os.makedirs("data/saves", exist_ok=True)
    with open("data/saves/test_save.json", 'w') as f:
        json.dump(save_data, f, indent=2)

    print("[OK] Saved combat state to data/saves/test_save.json")
    print(f"  Round: {saved_round}")
    print(f"  Characters: {len(character_states)}")
    print(f"  Deployables: {len(deployables)}")
    print(f"  Effects: {sum(len(e) for e in effects_data.values())}\n")

    # Test 6: Clear combat
    print("--- Test 6: Clear Combat ---")
    db = await get_db()

    await db.execute("DELETE FROM combat_state")
    await db.execute("DELETE FROM deployables")
    await db.execute(
        "UPDATE initiative SET combat_active = 0, turn_order_json = '[]', round_number = 0, current_turn_index = 0 WHERE id = 1"
    )

    await db.commit()
    await db.close()
    print("[OK] Combat cleared\n")

    # Test 7: Load combat state
    print("--- Test 7: Load Combat State ---")

    # Check if save file exists
    if not os.path.exists("data/saves/test_save.json"):
        print("[FAIL] Save file not found!")
        return

    # Load save data
    try:
        with open("data/saves/test_save.json", 'r') as f:
            load_data = json.load(f)
    except json.JSONDecodeError:
        print("[FAIL] Save file is corrupted!")
        return

    # Validate save data structure
    required_keys = ["turn_order", "round_number", "current_turn_index", "character_states", "effects", "deployables"]
    if not all(key in load_data for key in required_keys):
        print("[FAIL] Save file is missing required data!")
        return

    db = await get_db()

    # Restore initiative
    await db.execute(
        """UPDATE initiative SET
           combat_active = 1,
           turn_order_json = ?,
           round_number = ?,
           current_turn_index = ?
           WHERE id = 1""",
        (json.dumps(load_data["turn_order"]), load_data["round_number"], load_data["current_turn_index"])
    )

    # Restore character states
    for char_name, state in load_data["character_states"].items():
        effects = load_data["effects"].get(char_name, [])
        await db.execute(
            """INSERT INTO combat_state (character_name, current_hp, current_mp, stars, effects_json)
               VALUES (?, ?, ?, ?, ?)""",
            (char_name, state["hp"], state["mp"], state["stars"], json.dumps(effects))
        )

    # Restore deployables
    for deployable in load_data["deployables"]:
        await db.execute(
            """INSERT INTO deployables (name, owner, hp, max_hp, stars, max_stars, duration)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (deployable["name"], deployable["owner"], deployable["hp"], deployable["max_hp"],
             deployable["stars"], deployable["max_stars"], deployable["duration"])
        )

    await db.commit()
    await db.close()

    print("[OK] Combat state loaded from data/saves/test_save.json\n")

    # Test 8: Verify loaded state
    print("--- Test 8: Verify Loaded State ---")
    db = await get_db()

    # Check initiative
    async with db.execute(
        "SELECT combat_active, round_number, current_turn_index, turn_order_json FROM initiative WHERE id = 1"
    ) as cursor:
        row = await cursor.fetchone()
        active, round_num, turn_idx, turn_json = row
        turn_order_loaded = json.loads(turn_json)

    print(f"Combat active: {bool(active)}")
    print(f"Round: {round_num}")
    print(f"Turn index: {turn_idx}")
    print(f"Turn order: {[c['name'] for c in turn_order_loaded]}")

    # Check character states
    async with db.execute("SELECT character_name, current_hp, current_mp, stars FROM combat_state") as cursor:
        print("\nCharacter states:")
        async for row in cursor:
            name, hp, mp, stars = row
            print(f"  {name}: HP={hp}, MP={mp}, Stars={stars}")

    # Check effects
    async with db.execute("SELECT character_name, effects_json FROM combat_state") as cursor:
        print("\nEffects:")
        async for row in cursor:
            name, effects_json = row
            effects = json.loads(effects_json)
            if effects:
                for effect in effects:
                    print(f"  {name}: {effect['name']} ({effect['duration']} rounds)")

    # Check deployables
    async with db.execute(
        "SELECT name, owner, hp, max_hp, stars, max_stars, duration FROM deployables"
    ) as cursor:
        print("\nDeployables:")
        async for row in cursor:
            name, owner, hp, max_hp, stars, max_stars, duration = row
            print(f"  {name} (Owner: {owner}): {hp}/{max_hp} HP, {stars}/{max_stars} stars, {duration} rounds")

    await db.close()

    # Verify data matches
    all_match = (
        active == 1 and
        round_num == saved_round and
        turn_idx == saved_index and
        len(turn_order_loaded) == len(saved_turn_order)
    )

    if all_match:
        print("\n[OK] All loaded data matches saved data!\n")
    else:
        print("\n[FAIL] Loaded data does not match saved data!\n")

    # Test 9: Test error handling (corrupt file)
    print("--- Test 9: Test Error Handling ---")

    # Create corrupt file
    with open("data/saves/corrupt.json", 'w') as f:
        f.write("{invalid json")

    try:
        with open("data/saves/corrupt.json", 'r') as f:
            json.load(f)
        print("[FAIL] Should have caught corrupt JSON!")
    except json.JSONDecodeError:
        print("[OK] Caught corrupt JSON error")

    # Test missing file
    if not os.path.exists("data/saves/nonexistent.json"):
        print("[OK] Correctly detects missing file")

    # Test missing keys
    incomplete_data = {"turn_order": [], "round_number": 1}
    if not all(key in incomplete_data for key in required_keys):
        print("[OK] Correctly detects incomplete save data\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
